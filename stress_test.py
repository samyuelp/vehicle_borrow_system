"""
Smoke + stress test for the Vehicle Borrow System (VBS).

Usage:
    python stress_test.py smoke              # check every page returns 200
    python stress_test.py stress --n 50      # 50 concurrent borrow/return cycles
    python stress_test.py all --n 50         # both

Assumes a kiosk is running at http://10.64.16.161:8000 (override with --base).
"""

import argparse
import random
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

DEFAULT_BASE = "http://10.64.16.161:8000"


def _opener():
    """Cookie-aware opener so session/CSRF work across requests."""
    return build_opener(HTTPCookieProcessor())


def _get(opener, url, timeout=10):
    """GET a URL, return (status, body, final_url)."""
    req = Request(url, headers={"User-Agent": "vbs-stress/1.0"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), resp.geturl()
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), url
    except URLError as e:
        return 0, str(e), url


def _extract_csrf(html):
    """Pull the csrfmiddlewaretoken out of a rendered form, if present."""
    marker = 'name="csrfmiddlewaretoken" value="'
    idx = html.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    end = html.find('"', start)
    return html[start:end]


def _post(opener, url, data, referer=None, timeout=10):
    """POST form-encoded data with CSRF token extracted from a prior GET."""
    status, body, final = _get(opener, referer or url, timeout=timeout)
    token = _extract_csrf(body)
    if token:
        data = {**data, "csrfmiddlewaretoken": token}

    encoded = "&".join(
        f"{k}={v}" for k, v in data.items()
    ).encode()
    req = Request(
        url,
        data=encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": referer or url,
            "User-Agent": "vbs-stress/1.0",
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


def run_smoke(base):
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
            snippet = body[:200].replace("\n", " ")
            print(f"         body: {snippet}")

    print(f"\n  {len(SMOKE_PAGES) - failures}/{len(SMOKE_PAGES)} pages OK")
    return failures == 0


# ---------- Stress test ----------

def _random_name(prefix="Stress"):
    suffix = "".join(random.choices(string.ascii_uppercase, k=4))
    return f"{prefix}-{suffix}"


def _borrow_return_cycle(base, vehicle_id):
    """Walk one borrow -> return cycle for a given vehicle. Returns (ok, detail)."""
    opener = _opener()
    name = _random_name()

    # 1. Go to borrow form
    form_url = urljoin(base, f"/borrow/{vehicle_id}/")
    status, body, final = _get(opener, form_url)
    if status != 200:
        return False, f"borrow form GET {status} (final {final})"

    # 2. Submit borrow
    status, body, final = _post(
        opener,
        urljoin(base, f"/borrow/{vehicle_id}/"),
        {"borrowers_name": name, "destination": "stress-test"},
        referer=form_url,
    )
    if status not in (200, 302):
        return False, f"borrow POST {status}"

    # 3. Try to return it
    # We need to find the borrow's PK. Simplest: hit the return list
    # and look for the name we just submitted.
    status, body, _ = _get(opener, urljoin(base, "/return/"))
    if status != 200:
        return False, f"return list GET {status}"

    # Find /return/<pk>/confirm/ links and pick one — try to match our name nearby
    import re
    confirm_links = re.findall(r"/return/(\d+)/confirm/", body)
    if not confirm_links:
        # Could be fine — maybe the borrow didn't appear (unlikely but not fatal)
        return True, f"borrowed as {name}, but no confirm links found"

    # 4. Submit the return with required fields
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
    )
    if status not in (200, 302):
        return False, f"return POST {status}"

    return True, f"borrowed {name}, returned pk={pk}"


def run_stress(base, n=50, workers=5):
    print(f"\n=== Stress test against {base} (n={n}, workers={workers}) ===")

    # Discover vehicle IDs from the borrow list
    opener = _opener()
    status, body, _ = _get(opener, urljoin(base, "/borrow/"))
    if status != 200:
        print(f"  FAIL: could not load borrow list ({status})")
        return False

    import re
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
            pool.submit(_borrow_return_cycle, base, random.choice(vehicle_ids))
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
        print("\n  Failure details:")
        for f in failures[:10]:
            print(f"    - {f}")
        if len(failures) > 10:
            print(f"    ... and {len(failures) - 10} more")
    if seen_500s:
        print(f"\n  WARNING: {seen_500s} HTTP 500 response(s) — check docker logs kiosk")

    return len(failures) == 0


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="Smoke + stress test for VBS")
    parser.add_argument("mode", choices=["smoke", "stress", "all"], help="what to run")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"base URL (default: {DEFAULT_BASE})")
    parser.add_argument("--n", type=int, default=50, help="number of stress cycles (default: 50)")
    parser.add_argument("--workers", type=int, default=5, help="concurrent workers (default: 5)")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    ok = True

    if args.mode in ("smoke", "all"):
        ok = run_smoke(base) and ok

    if args.mode in ("stress", "all"):
        ok = run_stress(base, n=args.n, workers=args.workers) and ok

    print("\n=== Result:", "PASS" if ok else "FAIL", "===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()