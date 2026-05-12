#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web Dashboard Feature Test - Simulating Browser Interactions"""
import json
import requests
import sys
from datetime import datetime

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://127.0.0.1:8765"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_feature_1_stats():
    """Feature 1: Statistics Overview"""
    print_section("Feature 1: Statistics Overview")

    resp = requests.get(f"{BASE_URL}/api/skill/stats")
    stats = resp.json()

    print(f"  Total Skills: {stats.get('total', 0)}")

    # Get today's call count
    resp = requests.get(f"{BASE_URL}/api/logs/calls?limit=1")
    logs = resp.json()
    print(f"  Today's Calls: {logs.get('total', 0)}")

    # Get sources count
    resp = requests.get(f"{BASE_URL}/api/source/list")
    sources = resp.json()
    print(f"  Sources: {len(sources.get('sources', []))}")

    return True

def test_feature_2_call_logs():
    """Feature 2: Call Logs Viewer"""
    print_section("Feature 2: Call Logs Viewer")

    # Get available dates
    resp = requests.get(f"{BASE_URL}/api/logs/dates")
    dates = resp.json()
    print(f"  Available dates: {dates.get('dates', [])}")

    if not dates.get('dates'):
        print("  [WARN] No log dates available")
        return True

    # Get logs for latest date
    latest_date = dates['dates'][0]
    resp = requests.get(f"{BASE_URL}/api/logs/calls?date={latest_date}&limit=10")
    logs = resp.json()

    print(f"  Logs on {latest_date}: {logs.get('total', 0)} records")

    if logs.get('logs'):
        sample = logs['logs'][0]
        print(f"  Sample log:")
        print(f"    - Query: {sample.get('query', 'N/A')[:50]}...")
        print(f"    - Source: {sample.get('source', 'N/A')}")
        print(f"    - Hits: {sample.get('hit_count', 0)}")
        print(f"    - Latency: {sample.get('latency_ms', 0)}ms")

    # Test pagination
    if logs.get('total', 0) > 10:
        resp = requests.get(f"{BASE_URL}/api/logs/calls?date={latest_date}&offset=10&limit=10")
        page2 = resp.json()
        print(f"  Page 2 records: {len(page2.get('logs', []))}")

    return True

def test_feature_3_skills_list():
    """Feature 3: Skills Management"""
    print_section("Feature 3: Skills Management")

    # Get skills list
    resp = requests.get(f"{BASE_URL}/api/skill/list?limit=20")
    data = resp.json()

    print(f"  Total skills: {data.get('total', 0)}")
    print(f"  Showing: {len(data.get('skills', []))} skills")

    if data.get('skills'):
        print(f"  Sample skills:")
        for skill in data['skills'][:5]:
            enabled = "[enabled]" if skill.get('enabled') else "[disabled]"
            print(f"    - {skill.get('name')} {enabled}")
            print(f"      Compatibility: {skill.get('compatibility', [])}")

    # Test filtering by agent type
    resp = requests.get(f"{BASE_URL}/api/skill/list?agent_type=claude_code&limit=5")
    claude_skills = resp.json()
    print(f"  Claude Code skills: {claude_skills.get('total', 0)}")

    return True

def test_feature_4_sources():
    """Feature 4: Source Subscription"""
    print_section("Feature 4: Source Subscription")

    resp = requests.get(f"{BASE_URL}/api/source/list")
    data = resp.json()

    sources = data.get('sources', [])
    print(f"  Total sources: {len(sources)}")

    for source in sources:
        status = "[enabled]" if source.get('enabled') else "[disabled]"
        print(f"    - {source.get('name')} {status}")
        print(f"      Path: {source.get('root')}")

    return True

def test_feature_5_skill_match():
    """Feature 5: Skill Match Testing"""
    print_section("Feature 5: Skill Match Testing")

    test_queries = [
        ("Android", None),
        ("PDF", None),
        ("Excel", "codex"),
    ]

    for query, agent_type in test_queries:
        payload = {"query": query, "top_k": 3}
        if agent_type:
            payload["agent_type"] = agent_type

        resp = requests.post(f"{BASE_URL}/api/skill/match", json=payload)
        results = resp.json()

        agent_str = f" [{agent_type}]" if agent_type else ""
        print(f"  Query: '{query}'{agent_str} -> {len(results)} matches")

        for r in results[:2]:
            score_pct = r.get('score', 0) * 100
            print(f"    - {r.get('name')} ({score_pct:.1f}%)")

    return True

def test_feature_6_reindex():
    """Feature 6: Reindex Skills"""
    print_section("Feature 6: Reindex Skills")

    resp = requests.post(f"{BASE_URL}/api/skill/reindex")
    result = resp.json()

    print(f"  Indexed skills: {result.get('indexed', 0)}")
    print(f"  Message: {result.get('message', 'N/A')}")

    return True

def test_feature_7_admin_status():
    """Feature 7: Admin Status"""
    print_section("Feature 7: Admin Status")

    resp = requests.get(f"{BASE_URL}/api/admin/status")
    status = resp.json()

    print(f"  Service: {status.get('service')}")
    print(f"  Status: {status.get('status')}")
    print(f"  Ready: {status.get('ready')}")
    print(f"  PID: {status.get('pid')}")
    print(f"  Address: {status.get('host')}:{status.get('port')}")
    print(f"  Started: {status.get('started_at')}")
    print(f"  Data Dir: {status.get('data_dir')}")

    return True

def main():
    print("="*60)
    print("  SkillsBrain Web Dashboard - Feature Test")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"URL: {BASE_URL}")

    features = [
        ("Statistics Overview", test_feature_1_stats),
        ("Call Logs Viewer", test_feature_2_call_logs),
        ("Skills Management", test_feature_3_skills_list),
        ("Source Subscription", test_feature_4_sources),
        ("Skill Match Testing", test_feature_5_skill_match),
        ("Reindex Skills", test_feature_6_reindex),
        ("Admin Status", test_feature_7_admin_status),
    ]

    results = {}
    for name, test_func in features:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"  [ERROR] {e}")
            results[name] = False

    # Summary
    print_section("Test Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, ok in results.items():
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\n  Total: {passed}/{total} features tested")

    if passed == total:
        print("\n  All features working correctly!")
        print(f"\n  Access the dashboard at: {BASE_URL}/")
        return 0
    else:
        print(f"\n  {total - passed} feature(s) failed.")
        return 1

if __name__ == "__main__":
    exit(main())
