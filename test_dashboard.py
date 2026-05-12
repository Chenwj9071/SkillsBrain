#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web Dashboard API Test Script"""
import json
import requests
import sys
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://127.0.0.1:8765"

def test_api(name, url, method="GET", data=None, expected_status=200):
    """Test single API endpoint"""
    print(f"\n{'='*50}")
    print(f"Test: {name}")
    print(f"URL: {url}")
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        elif method == "POST":
            resp = requests.post(url, json=data, timeout=10)

        status = "[OK]" if resp.status_code == expected_status else "[FAIL]"
        print(f"Status: {status} ({resp.status_code})")

        if resp.status_code == 200:
            try:
                result = resp.json()
                if isinstance(result, dict):
                    for k, v in result.items():
                        if k == "skills" and isinstance(v, list):
                            print(f"  {k}: [{len(v)} items]")
                        elif k == "logs" and isinstance(v, list):
                            print(f"  {k}: [{len(v)} items]")
                        elif isinstance(v, (str, int, float, bool)):
                            print(f"  {k}: {v}")
                elif isinstance(result, list):
                    print(f"  Returns: [{len(result)} items]")
                return True
            except json.JSONDecodeError:
                print(f"  Response: {resp.text[:200]}")
        else:
            print(f"  Error: {resp.text[:200]}")
        return resp.status_code == expected_status
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return False

def main():
    print(f"SkillsBrain Web Dashboard API Test")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"URL: {BASE_URL}")

    results = {}

    # 1. Health checks
    results["health"] = test_api("Health Check", f"{BASE_URL}/health")
    results["ready"] = test_api("Ready Check", f"{BASE_URL}/health/ready")

    # 2. Dashboard HTML
    results["dashboard"] = test_api("Dashboard HTML", f"{BASE_URL}/")

    # 3. Statistics
    results["stats"] = test_api("Skills Stats", f"{BASE_URL}/api/skill/stats")

    # 4. Skills list
    results["skill_list"] = test_api("Skills List", f"{BASE_URL}/api/skill/list?limit=5")

    # 5. Log dates
    results["log_dates"] = test_api("Log Dates", f"{BASE_URL}/api/logs/dates")

    # 6. Call logs
    results["call_logs"] = test_api("Call Logs", f"{BASE_URL}/api/logs/calls?limit=5")

    # 7. Sources list
    results["sources"] = test_api("Sources List", f"{BASE_URL}/api/source/list")

    # 8. Skill match
    results["match"] = test_api("Skill Match", f"{BASE_URL}/api/skill/match",
                                method="POST",
                                data={"query": "Android", "top_k": 3})

    # 9. Admin status
    results["admin_status"] = test_api("Admin Status", f"{BASE_URL}/api/admin/status")

    # Summary
    print(f"\n{'='*50}")
    print("Test Results Summary:")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\nAll tests passed! Web Dashboard is working correctly.")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed. Please check.")
        return 1

if __name__ == "__main__":
    exit(main())
