#!/usr/bin/env python3
"""One-off diagnostic: print the exact raw prize_amount strings Devpost's API
actually returns, so the parser can be fixed against real bytes instead of
WebFetch's paraphrased rendering. Deleted once the real fix is in."""
import sys
sys.path.insert(0, "scripts")
import post_jobs as p

results = p.devpost_search(challenge_type="online", status="open")
for h in results:
    raw = h.get("prize_amount", "")
    code, amount = p.parse_prize_amount(raw)
    print(f"{h.get('title')!r}")
    print(f"  raw repr: {raw!r}")
    print(f"  parsed: code={code} amount={amount}")
