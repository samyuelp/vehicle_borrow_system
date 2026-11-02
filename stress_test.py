"""
Smoke + stress test for the Vehicle Borrow System (VBS).
"""

import argparse
import random
import re
import string
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

DEFAULT_BASE = "http://localhost:8000"


def _opener():
    return build_opener(HTTPCookieProcessor())


def _get(opener, url, timeout=10):
    req = Request(url, headers={"User-Agent": "vbs-stress/3.0"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), resp.geturl()
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), url
    except URLError as e:
        return 0, str(e), url


def _extract_csrf(html):
    if not html:
        return None
    patterns = [
        r'name="csrfmiddlewaretoken"\s+value="([^"]+)"',
        r'value="([^"]+)"\s+name="csrfmiddlewaretoken"',
        r"name='csrfmiddlewaretoken'\s+value='([^']+)'",
        r"value='([^']+)'\s+name='csrfmiddlewaretoken'",
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def _post_with_token(opener, form_url, post_url, data, timeout=10, debug=False):
    """GET form_url to get cookie+token, then POST to post_url."""
    status, body, _ = _get(opener, form_url, timeout=timeout)

    if debug:
        print(f"\n[DEBUG] GET {form_url} -> {status}")

    token = _extract_csrf(body)
    if debug:
        print(f"[DEBUG] extracted token: {token!r}")

    if not token:
        return 0, f"No CSRF token found on {form_url}", form_url

    data = {**data, "csrfmiddlewaretoken": token}
    encoded = urlencode(data).encode()

    req = Request(
        post_url,
        data=encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": form_url,
            "User-Agent": "vbs-stress/3.0",
        },
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), resp.geturl()
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace", ), post_url
    except URLError as e:
        return 0, str(e), post_url


# ---------- Smoke test ----------

SMOKE_PAGES = [
    ("/", "Home"),
    ("/borrow/", "Borrow list"),
    ("/return/", "Return list"),
    ("/reserve/", "Reserve list"),
    ("/admin/", "Admin login"),
]


def run_smoke(base, debug=False):
    print(f"\n=== Smoke test against {base} ===")
    opener = _opener()
    failures = 0

    for path, label in SMOKE_PAGES:
        url = urljoin(base + "/", path.lstrip("/"))
        status, body, _ = _get(opener, url)
        ok = status == 200
        print(f"  [{'OK ' if ok else 'FAIL'}] {label:20s} {url}  -> {status}")
        if not ok:
            failures += 1
            print(f"         body: {body[:300]}")

    print(f"\n  {len(SMOKE_PAGES) - failures}/{len(SMOKE_PAGES)} pages OK")
    return failures == 0


# ---------- Stress test ----------

def _random_name(prefix="Stress"):
    suffix = "".join(random.choices(string.ascii_uppercase, k=4))
    return f"{prefix}-{suffix}"


def _borrow_return_cycle(base, vehicle_id, debug=False):
    opener = _opener()
    name = _random_name()

    # 1. Borrow: GET form page, POST to same URL
    form_url = urljoin(base, f"/borrow/{vehicle_id}/")
    status, body, _ = _get(opener, form_url)
    if status != 200:
        return False, f"borrow form GET {status}"

    status, body, final = _post_with_token(
        opener,
        form_url=form_url,
        post_url=urljoin(base, f"/borrow/{vehicle_id}/"),
        data={"borrowers_name": name, "destination": "stress-test"},
        debug=debug,
    )
    if status not in (200, 302):
        snippet = " [CSRF]" if "csrf" in body.lower() else ""
        return False, f"borrow POST {status}{snippet}"

    # 2. Find the borrow on the return list
    status, body, _ = _get(opener, urljoin(base, "/return/"))
    if status != 200:
        return False, f"return list GET {status}"

    confirm_links = re.findall(r"/return/(\d+)/confirm/", body)
    if not confirm_links:
        return True, f"borrowed as {name}, no confirm links (maybe already returned?)"

    pk = confirm_links[0]

    # 3. GET the return confirm page (link page, no form) — just a sanity check
    status, _, _ = _get(opener, urljoin(base, f"/return/{pk}/confirm/"))
    if status != 200:
        return False, f"return confirm GET {status}"

    # 4. GET the actual return form (has CSRF), then POST
    return_form_url = urljoin(base, f"/return/{pk}/")
    status, body, final = _post_with_token(
        opener,
        form_url=return_form_url,
        post_url=return_form_url,
        data={
            "fuel_percent": "50",
            "current_mileage": "50000",
            "notes": "stress-test return",
            "key_returned": "on",
        },
        debug=debug,
    )
    if status not in (200, 302):
        snippet = " [CSRF]" if "csrf" in body.lower() else ""
        return False, f"return POST {status}{snippet}"

    return True, f"borrowed {name}, returned pk={pk}"


def run_stress(base, n=50, workers=5, debug=False):
    print(f"\n=== Stress test against {base} (n={n}, workers={workers}) ===")

    opener = _opener()
    status, body, _ = _get(opener, urljoin(base, "/borrow/"))
    if status != 200:
        print(f"  FAIL: could not load borrow list ({status})")
        return False

    vehicle_ids = sorted(set(int(v) for v in re.findall(r"/borrow/(\d+)/", body)))
    if not vehicle_ids:
        print("  FAIL: no vehicles found on borrow list")
        return False

    print(f"  Found {len(vehicle_ids)} vehicle(s): {vehicle_ids}")
    print(f"  Firing {n} cycles across {workers} workers...\n")

    start = time.time()
    successes = 0
    failures = []
    seen_500s = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_borrow_return_cycle, base, random.choice(vehicle_ids), debug)
            for _ in range(n)
        ]
        for i, fut in enumerate(as_completed(futures), 1):
            ok, detail = fut.result()
            if ok:
                successes += 1
            else:
                failures.append(detail)
                if "500" in detail:
                    seen_500s += 1
            if i % 10 == 0 or i == n:
                print(f"  ... {i}/{n} done (ok={successes}, fail={len(failures)})")

    elapsed = time.time() - start
    print(f"\n  Completed {n} cycles in {elapsed:.2f}s")
    print(f"  Successes: {successes}")
    print(f"  Failures:  {len(failures)}")
    if failures:
        print("\n  Failure breakdown:")
        for msg, count in Counter(failures).most_common():
            print(f"    {count}x  {msg}")
    if seen_500s:
        print(f"\n  WARNING: {seen_500s} HTTP 500 response(s) — check docker logs kiosk")

    return len(failures) == 0


def main():
    parser = argparse.ArgumentParser(description="Smoke + stress test for VBS")
    parser.add_argument("mode", choices=["smoke", "stress", "all"])
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    ok = True

    if args.mode in ("smoke", "all"):
        ok = run_smoke(base, debug=args.debug) and ok
    if args.mode in ("stress", "all"):
        ok = run_stress(base, n=args.n, workers=args.workers, debug=args.debug) and ok

    print("\n=== Result:", "PASS" if ok else "FAIL", "===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()