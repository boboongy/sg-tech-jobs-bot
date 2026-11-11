#!/usr/bin/env python3
"""
One-off diagnostic: inspect luma.com's real page structure so we can build
a real scraper against confirmed facts instead of guesses. Not part of the
bot - deleted once Luma integration is built or ruled out.

Run via GitHub Actions (sandbox dev environment can't reach luma.com).
"""
import json
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


def main():
    url = "https://luma.com/singapore"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    html = resp.text

    next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not next_data_match:
        print("No __NEXT_DATA__ found")
        return

    data = json.loads(next_data_match.group(1))
    place_data = data["props"]["pageProps"]["initialData"]["data"]
    place = place_data.get("place", {})
    events = place_data.get("events", [])

    print(f"place.event_count (claimed total): {place.get('event_count')}")
    print(f"events array length (actually returned): {len(events)}")
    print()

    for i, item in enumerate(events):
        ev = item.get("event", {})
        name = ev.get("name", "")
        cover = ev.get("cover_url", "")
        start = ev.get("start_at", "")
        api_id = ev.get("api_id", "")
        # look for any url/slug-like field
        url_fields = {k: v for k, v in ev.items() if "url" in k.lower() and "cover" not in k.lower() and "social" not in k.lower() and "image" not in k.lower()}
        is_hack = "hack" in name.lower()
        flag = " <<<< HACKATHON-ish" if is_hack else ""
        print(f"[{i}] {name}{flag}")
        print(f"    api_id={api_id} start={start}")
        print(f"    cover_url={cover[:80]}")
        print(f"    url-like fields: {url_fields}")

    # Dump full keys of the first event object so we see everything available
    if events:
        print("\n--- ALL KEYS on first event object ---")
        print(json.dumps(events[0].get("event", {}), indent=2)[:3000])

        print("\n--- ALL KEYS on first item wrapper (not just .event) ---")
        print(json.dumps({k: v for k, v in events[0].items() if k != "event"}, indent=2)[:2000])


if __name__ == "__main__":
    main()
