#!/usr/bin/env python3
import json
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


def get_events(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    html = resp.text
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None, f"no __NEXT_DATA__ (status {resp.status_code})"
    data = json.loads(m.group(1))
    place_data = data["props"]["pageProps"]["initialData"]["data"]
    return place_data.get("events", []), f"event_count claimed={place_data.get('place', {}).get('event_count')}, returned={len(place_data.get('events', []))}"


for label, url in [
    ("SINGAPORE (city feed)", "https://luma.com/singapore"),
    ("TECH category", "https://luma.com/tech"),
    ("SG + hack search attempt", "https://luma.com/singapore?k=hackathon"),
]:
    print(f"\n===== {label}: {url} =====")
    events, meta = get_events(url)
    print(meta)
    if events:
        hack_matches = [e["event"]["name"] for e in events if "hack" in e["event"].get("name", "").lower()]
        print(f"hack-matching names in this batch: {hack_matches}")
        print("all names:", [e["event"].get("name") or e["event"]["name"] for e in events][:20])
