"""
Smoke + stress test for the Vehicle Borrow System (VBS).

Usage:
    python3 stress_test.py smoke              # check every page returns 200
    python3 stress_test.py stress --n 50      # 50 concurrent borrow/return cycles
    python3 stress_test.py all --n 50         # both
    python3 stress_test.py smoke --debug      # print raw HTML to diagnose CSRF issues
"""

import argparse
import random
import re
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

DEFAULT_BASE = "http://localhost:8000"


def _opener():
    return build_opener(HTTPCookieProcessor())


def _get(opener, url, timeout=10):
    req = Request(url, headers={"User-Agent": "vbs-stress/2.0"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), resp.geturl()
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), url
    except URLError as e:
        return 0, str(e), url


def _extract_csrf(html):
    """Pull csrfmiddlewaretoken out of a rendered form, tolerant of attr order/quotes."""
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


def _post(opener, url, data, referer=None, timeout=10, debug=False):
    # Fetch the form page to get a fresh CSRF cookie + token
    form_url = referer or url
    status, body, _ = _get(opener, form_url, timeout=timeout)

    if debug:
        print(f"\n[DEBUG] GET {form_url} -> {status}")
        idx = body.find("csrfmiddlewaretoken")
        if idx != -1:
            print(f"[DEBUG] csrf context: ...{body[max(0,idx-60):idx+80]}...")
        else:
            print("[DEBUG] no csrfmiddlewaretoken in response body")

    token = _extract_csrf(body)
    if debug:
        print(f"[DEBUG] extracted token: {token!r}")

    if not token:
        return 0, f"No CSRF token found on {form_url}", url

    data = {**data, "csrfmiddlewaretoken": token}

    from urllib.parse import urlencode
    encoded = urlencode(data).encode()

    req = Request(
        url,
        data=encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": form_url,
            "User-Agent": "vbs-stress/2.0",
        },
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), resp.geturl()
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), url
    except URLError as e:
        return 0, str(e), url


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
        marker = "OK " if ok else "FAIL"
        print(f"  [{marker}] {label:20s} {url}  -> {status}")
        if not ok:
            failures += 1
            print(f"         body: {body[:300]}")

    if debug:
        url = urljoin(base + "/", "borrow/1/")
        status, body, _ = _get(opener, url)
        print(f"\n[DEBUG] GET {url} -> {status}")
        print(f"[DEBUG] body length: {len(body)}")
        idx = body.find("csrfmiddlewaretoken")
        if idx != -1:
            print(f"[DEBUG] around token: ...{body[max(0,idx-100):idx+100]}...")
        else:
            print("[DEBUG] no csrfmiddlewaretoken in body")
            print(f"[DEBUG] body excerpt: {body[:500]}")

    print(f"\n  {len(SMOKE_PAGES) - failures}/{len(SMOKE_PAGES)} pages OK")
    return failures == 0


# ---------- Stress test ----------

def _random_name(prefix="Stress"):
    suffix = "".join(random.choices(string.ascii_uppercase, k=4))
    return f"{prefix}-{suffix}"


def _borrow_return_cycle(base, vehicle_id, debug=False):
    opener = _opener()
    name = _random_name()

    form_url = urljoin(base, f"/borrow/{vehicle_id}/")
    status, body, final = _get(opener, form_url)
    if status != 200:
        return False, f"borrow form GET {status} (final {final})"

    status, body, final = _post(
        opener,
        urljoin(base, f"/borrow/{vehicle_id}/"),
        {"borrowers_name": name, "destination": "stress-test"},
        referer=form_url,
        debug=debug,
    )
    if status not in (200, 302):
        # Try to show a useful error message from the response body
        snippet = ""
        if "CSRF" in body or "csrf" in body:
            snippet = " [CSRF rejected]"
        elif "errorlist" in body:
            snippet = " [form errors in response]"
        return False, f"borrow POST {status}{snippet}"

    status, body, _ = _get(opener, urljoin(base, "/return/"))
    if status != 200:
        return False, f"return list GET {status}"

    confirm_links = re.findall(r"/return/(\d+)/confirm/", body)
    if not confirm_links:
        return True, f"borrowed as {name}, no confirm links found (maybe returned already?)"

    pk = confirm_links[0]
    status, body, final = _post(
        opener,
        urljoin(base, f"/return/{pk}/"),
        {
            "fuel_percent": "50",
            "current_mileage": "50000",
            "notes": "stress-test return",
            "key_returned": "on",
        },
        referer=urljoin(base, f"/return/{pk}/confirm/"),
        debug=debug,
    )
    if status not in (200, 302):
        snippet = ""
        if "CSRF" in body or "csrf" in body:
            snippet = " [CSRF rejected]"
        elif "errorlist" in body:
            snippet = " [form errors in response]"
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
        from collections import Counter
        print("\n  Failure breakdown:")
        for msg, count in Counter(failures).most_common():
            print(f"    {count}x  {msg}")
    if seen_500s:
        print(f"\n  WARNING: {seen_500s} HTTP 500 response(s) — check docker logs kiosk")

    return len(failures) == 0


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="Smoke + stress test for VBS")
    parser.add_argument("mode", choices=["smoke", "stress", "all"])
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--debug", action="store_true", help="print CSRF extraction details")
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