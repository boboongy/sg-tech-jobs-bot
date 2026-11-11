#!/usr/bin/env python3
"""
One-off diagnostic: inspect luma.com's real page structure so we can build
a real scraper against confirmed facts instead of guesses. Not part of the
bot - deleted once Luma integration is built or ruled out.

Run via GitHub Actions (sandbox dev environment can't reach luma.com).
"""
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


def main():
    url = "https://luma.com/singapore"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    print(f"status: {resp.status_code}, length: {len(resp.text)}")
    html = resp.text

    # Does it carry a Next.js data payload?
    next_data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    print(f"__NEXT_DATA__ present: {bool(next_data)}")
    if next_data:
        print(f"__NEXT_DATA__ length: {len(next_data.group(1))}")
        print("--- first 2000 chars of __NEXT_DATA__ ---")
        print(next_data.group(1)[:2000])

    # Any other embedded JSON blobs (self.__next_f.push patterns used by newer Next.js app router)
    push_blobs = re.findall(r'self\.__next_f\.push\(\[\d+,\s*"(.*?)"\]\)', html, re.S)
    print(f"\n__next_f.push blobs found: {len(push_blobs)}")
    for i, blob in enumerate(push_blobs[:5]):
        print(f"--- blob {i} (first 500 chars, escaped) ---")
        print(blob[:500])

    # JSON-LD structured data (schema.org Event) - common, stable, often present for SEO
    jsonld = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
    print(f"\nJSON-LD blocks found: {len(jsonld)}")
    for i, block in enumerate(jsonld[:3]):
        print(f"--- JSON-LD block {i} (first 1000 chars) ---")
        print(block[:1000])

    # Does the page mention "hackathon" anywhere in raw HTML (helps gauge keyword-filter viability)?
    hackathon_count = html.lower().count("hackathon")
    print(f"\n'hackathon' substring count in raw HTML: {hackathon_count}")


if __name__ == "__main__":
    main()
