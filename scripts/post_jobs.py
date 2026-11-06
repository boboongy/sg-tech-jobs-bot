#!/usr/bin/env python3
"""
SG Tech Jobs daily poster.

Pulls IT job listings from MyCareersFuture (MCF), picks:
  1. "main"   - one zero-experience-required job for Junior Executive / Non-executive levels
  2. "intern" - one internship-titled job (any level)

and posts each (if found and not already posted today) to the
@sgtechjob Telegram channel. State (dedup + daily lock) is kept in
data/state.json, which the GitHub Actions workflow commits back after
each run so the bot never double-posts.
"""

import html
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "data" / "state.json"

MCF_SEARCH_URL = "https://api.mycareersfuture.gov.sg/v2/search"
MCF_JOB_URL = "https://api.mycareersfuture.gov.sg/v2/jobs/{job_id}"

DEVPOST_SEARCH_URL = "https://devpost.com/api/hackathons"
FX_API_URL = "https://api.frankfurter.dev/v1/latest"

# Devpost's prize_amount field prefixes the number with either a currency
# symbol or a 3-letter ISO code, inconsistently. Map the symbols we actually
# see in practice to ISO codes so we can look up a live rate. "$" alone is
# ambiguous (Devpost is US-based) so it defaults to USD.
CURRENCY_SYMBOL_MAP = {
    "$": "USD",
    "₹": "INR",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₩": "KRW",
    "C$": "CAD",
    "A$": "AUD",
    "S$": "SGD",
}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@sgtechjob")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

# Baked into every caption so the channel survives being screenshotted or
# copy-pasted into a group chat, not just forwarded (forwards carry their own
# "Forwarded from" attribution automatically; copies and screenshots don't).
CHANNEL_HANDLE = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID.startswith("@") else "@sgtechjob"
CHANNEL_PROMO_LINE = f"\U0001f4e2 More SG tech jobs, hackathons &amp; events: t.me/{CHANNEL_HANDLE.lstrip('@')}"

TIMEOUT = 40
BLURB_LIMIT = 650  # keeps full caption safely under Telegram's 1024-char photo caption limit

CLEAN_STEPS = [
    (re.compile(r"<br\s*/?>", re.I), "\n"),
    (re.compile(r"</p\s*>", re.I), "\n\n"),
    (re.compile(r"</h[1-6]\s*>", re.I), "\n\n"),
    (re.compile(r"</li\s*>", re.I), "\n"),
    (re.compile(r"</div\s*>", re.I), "\n"),
    (re.compile(r"<[^>]+>"), ""),
]

ENTITY_MAP = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&#39;": "'",
    "&rsquo;": "'",
    "&quot;": '"',
}


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"posted": {}, "daily_lock": {}}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def clean_description(raw_html: str) -> str:
    """Turn job-description HTML into clean, paragraph-separated plain text."""
    if not raw_html:
        return ""
    text = raw_html
    for pattern, repl in CLEAN_STEPS:
        text = pattern.sub(repl, text)
    for entity, repl in ENTITY_MAP.items():
        text = text.replace(entity, repl)
    text = re.sub(r"[ \t]+", " ", text)      # collapse runs of spaces/tabs, keep newlines
    text = re.sub(r"\n[ \t]+", "\n", text)   # strip leading spaces on wrapped lines
    text = re.sub(r"\n{3,}", "\n\n", text)   # collapse 3+ blank lines to one
    return text.strip()


def truncate_at_sentence(text: str, limit: int = BLURB_LIMIT) -> str:
    """Cut text at a real sentence boundary near `limit` chars. Never adds '...'."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    idx = window.rfind(". ")
    if idx == -1:
        idx = window.rfind(".\n")
    if idx == -1:
        idx = window.rfind(".")
    if idx != -1 and idx > limit * 0.3:
        return text[: idx + 1].strip()
    # no good break before the limit - look a little further ahead instead
    idx2 = text.find(".", limit)
    if idx2 != -1 and idx2 < limit + 200:
        return text[: idx2 + 1].strip()
    return text[:limit].strip()


def mcf_search(position_levels=None) -> list:
    body = {
        "categories": ["Information Technology"],
        "limit": 20,
        "page": 0,
        "sortBy": ["new_posting_date"],
    }
    if position_levels:
        body["positionLevels"] = position_levels
    resp = requests.post(MCF_SEARCH_URL, json=body, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("results", [])


def mcf_job_detail(job_details_url: str) -> dict:
    job_id = job_details_url[-32:]
    resp = requests.get(MCF_JOB_URL.format(job_id=job_id), timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def devpost_search(challenge_type="online", status="open") -> list:
    """Query Devpost's public hackathons API (no key needed)."""
    params = {
        "order_by": "recently-added",
        "status[]": status,
        "challenge_type[]": challenge_type,
    }
    resp = requests.get(DEVPOST_SEARCH_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("hackathons", [])


def esc(value) -> str:
    """HTML-escape a value for safe insertion into a Telegram HTML caption."""
    return html.escape(str(value or ""), quote=False)


def build_skills_line(skills: list) -> str:
    names = [s.get("skill") for s in (skills or []) if s.get("skill")]
    if not names:
        return "See job post"
    return ", ".join(esc(n) for n in names[:3])


def send_telegram_photo(photo_url: str, caption: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    resp = requests.post(
        TELEGRAM_API,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML",
        },
        timeout=TIMEOUT,
    )
    if not resp.ok:
        raise RuntimeError(f"Telegram API error {resp.status_code}: {resp.text}")


def logo_url_for(posted_company: dict) -> str:
    logo = (posted_company or {}).get("logoUploadPath")
    if logo:
        return logo
    name = (posted_company or {}).get("name", "Company")
    from urllib.parse import quote

    return (
        "https://ui-avatars.com/api/?size=256&background=0D47A1&color=fff"
        f"&bold=true&name={quote(name)}"
    )


# Telegram's real hard limit for a photo caption is 1024 characters, measured in
# UTF-16 code units (emoji count as 2). We render in plain Python chars, so we
# stay well under 1024 as a safety margin to absorb that difference.
CAPTION_HARD_LIMIT = 900


def build_caption(job: dict, detail: dict, header: str, footer_tags: str, extra_line: str) -> str:
    title = job.get("title", "")
    company = (job.get("postedCompany") or {}).get("name", "")
    employment_types = job.get("employmentTypes") or []
    employment = employment_types[0].get("employmentType", "") if employment_types else ""
    levels = job.get("positionLevels") or []
    level = levels[0].get("position", "") if levels else ""
    salary = job.get("salary") or {}
    salary_min = salary.get("minimum", "")
    salary_max = salary.get("maximum", "")
    salary_type = (salary.get("type") or {}).get("salaryType", "")
    job_url = (job.get("metadata") or {}).get("jobDetailsUrl", "")

    clean = clean_description(detail.get("description", ""))
    skills_line = build_skills_line(job.get("skills"))

    def render(blurb_text: str) -> str:
        return (
            f"{header}\n\n"
            f"\U0001f4bc <b>{esc(title)}</b>\n\n"
            f"\U0001f3e2 <b>Company:</b> {esc(company)}\n"
            f"\U0001f4cd Singapore\n"
            f"\U0001f4bc <b>Employment:</b> {esc(employment)}\n"
            f"⭐ <b>Level:</b> {esc(level)}\n"
            f"\U0001f4b0 <b>Salary:</b> ${esc(salary_min)} - ${esc(salary_max)} / {esc(salary_type)}\n\n"
            f"\U0001f4dd <b>About the role:</b>\n{esc(blurb_text)}\n\n"
            f"{extra_line}\n\n"
            f"\U0001f6e0 <b>Skills:</b> {skills_line}\n\n"
            f'\U0001f517 <a href="{esc(job_url)}">Apply here</a>\n\n'
            f"{footer_tags}\n"
            f"{CHANNEL_PROMO_LINE}"
        )

    # Shrink the blurb until the whole caption fits, rather than guessing a
    # fixed budget - title/company/skills length varies job to job.
    for limit in (600, 450, 300, 180, 100, 50, 0):
        blurb = truncate_at_sentence(clean, limit=limit) if limit else ""
        caption = render(blurb)
        if len(caption) <= CAPTION_HARD_LIMIT:
            return caption
    return render("")  # last-resort fallback; should never actually hit this


def run_main_pick(state: dict, today: str) -> bool:
    """Zero-experience-required pick for students/fresh grads. Returns True if posted."""
    if state["daily_lock"].get("main") == today:
        print("main: already posted today, skipping")
        return False

    results = mcf_search(position_levels=["Junior Executive", "Non-executive"])
    for job in results:
        job_url = (job.get("metadata") or {}).get("jobDetailsUrl", "")
        if not job_url or job_url in state["posted"]:
            continue
        try:
            detail = mcf_job_detail(job_url)
        except requests.RequestException as e:
            print(f"main: failed to fetch detail for {job_url}: {e}")
            continue
        if detail.get("minimumYearsExperience") != 0:
            continue

        caption = build_caption(
            job,
            detail,
            header="\U0001f31f <b>TODAY'S TOP PICK</b> \U0001f31f",
            footer_tags="#SGTechJobs #DailyPick #StudentFriendly",
            extra_line="✅ No prior experience required — perfect for students and fresh grads!",
        )
        send_telegram_photo(logo_url_for(job.get("postedCompany")), caption)

        state["posted"][job_url] = {"title": job.get("title", ""), "type": "main", "date": today}
        state["daily_lock"]["main"] = today
        print(f"main: posted '{job.get('title')}'")
        return True

    print("main: no qualifying zero-experience job found today")
    return False


def run_intern_pick(state: dict, today: str) -> bool:
    """Internship pick, detected by title. Returns True if posted."""
    if state["daily_lock"].get("intern") == today:
        print("intern: already posted today, skipping")
        return False

    results = mcf_search(position_levels=None)
    for job in results:
        title = job.get("title", "")
        if "intern" not in title.lower():
            continue
        job_url = (job.get("metadata") or {}).get("jobDetailsUrl", "")
        if not job_url or job_url in state["posted"]:
            continue
        try:
            detail = mcf_job_detail(job_url)
        except requests.RequestException as e:
            print(f"intern: failed to fetch detail for {job_url}: {e}")
            continue

        caption = build_caption(
            job,
            detail,
            header="\U0001f393 <b>TODAY'S INTERNSHIP PICK</b> \U0001f393",
            footer_tags="#SGTechJobs #InternshipPick #StudentFriendly",
            extra_line="\U0001f393 Open to students / fresh grads — internship listing",
        )
        send_telegram_photo(logo_url_for(job.get("postedCompany")), caption)

        state["posted"][job_url] = {"title": title, "type": "intern", "date": today}
        state["daily_lock"]["intern"] = today
        print(f"intern: posted '{title}'")
        return True

    print("intern: no internship listing found today")
    return False


PRIZE_AMOUNT_RE = re.compile(
    r"^\s*(?P<currency>[A-Z]{3}|\$|₹|€|£|¥|₩|C\$|A\$|S\$)\s*"
    r"<span[^>]*>(?P<number>[\d,]+(?:\.\d+)?)</span>",
)


def parse_prize_amount(raw: str) -> tuple:
    """Pulls (currency_code, numeric_value) out of Devpost's prize_amount HTML snippet.

    Returns (None, None) if it can't confidently parse the value (no prize
    listed, or an unrecognized format) - callers should fall back gracefully.
    """
    if not raw:
        return None, None
    match = PRIZE_AMOUNT_RE.match(raw.strip())
    if not match:
        return None, None
    currency = match.group("currency")
    code = currency if len(currency) == 3 and currency.isalpha() else CURRENCY_SYMBOL_MAP.get(currency)
    try:
        number = float(match.group("number").replace(",", ""))
    except ValueError:
        return None, None
    return code, number


def convert_to_sgd(code: str, amount: float) -> float | None:
    """Live FX lookup via frankfurter.dev (free, no key). Returns None on any failure."""
    if code == "SGD":
        return amount
    try:
        resp = requests.get(FX_API_URL, params={"from": code, "to": "SGD"}, timeout=TIMEOUT)
        resp.raise_for_status()
        rate = resp.json().get("rates", {}).get("SGD")
        if rate is None:
            return None
        return amount * rate
    except (requests.RequestException, ValueError, TypeError):
        return None


def format_prize_sgd(raw: str) -> str:
    """Converts Devpost's prize_amount field to a clean 'SGD X,XXX' string.

    Falls back to showing the original currency if conversion fails for any
    reason (unknown code, FX API down, zero/no prize listed), so the post
    never breaks or shows a blank field.
    """
    code, amount = parse_prize_amount(raw)
    if code is None:
        return "See event page"
    if amount == 0:
        return "Non-cash / to be announced"
    sgd_amount = convert_to_sgd(code, amount)
    if sgd_amount is None:
        # Couldn't get a live rate - show the original currency rather than guessing.
        return f"{code} {amount:,.0f} (SGD conversion unavailable)"
    return f"SGD {sgd_amount:,.0f}"


PLACEHOLDER_THUMBNAIL_MARKERS = ("thumbnail-placeholder", "/assets/defaults/")


def hackathon_photo_url(hackathon: dict) -> str:
    """Devpost's own thumbnail, or a generated avatar if it's just their generic placeholder."""
    thumb = hackathon.get("thumbnail_url") or ""
    if thumb and not any(marker in thumb for marker in PLACEHOLDER_THUMBNAIL_MARKERS):
        # Devpost serves some image URLs as protocol-relative ("//..."); Telegram needs a scheme.
        if thumb.startswith("//"):
            thumb = f"https:{thumb}"
        return thumb
    return logo_url_for({"name": hackathon.get("organization_name") or hackathon.get("title", "Hackathon")})


def build_hackathon_caption(hackathon: dict) -> str:
    title = hackathon.get("title", "")
    org = hackathon.get("organization_name", "")
    location = (hackathon.get("displayed_location") or {}).get("location", "Online")
    dates = hackathon.get("submission_period_dates", "")
    time_left = hackathon.get("time_left_to_submission", "")
    prize = format_prize_sgd(hackathon.get("prize_amount", ""))
    themes = ", ".join(esc(t.get("name")) for t in (hackathon.get("themes") or [])[:3]) or "Open theme"
    url = hackathon.get("url", "")

    return (
        f"\U0001f3c6 <b>HACKATHON ALERT</b> \U0001f3c6\n\n"
        f"\U0001f4bb <b>{esc(title)}</b>\n\n"
        f"\U0001f3e2 <b>Organizer:</b> {esc(org)}\n"
        f"\U0001f4cd {esc(location)}\n"
        f"\U0001f4c5 <b>Submissions:</b> {esc(dates)} ({esc(time_left)})\n"
        f"\U0001f3f7 <b>Themes:</b> {themes}\n"
        f"\U0001f4b0 <b>Prize pool:</b> {esc(prize)}\n\n"
        f'\U0001f517 <a href="{esc(url)}">Join on Devpost</a>\n\n'
        f"#SGTechJobs #Hackathon #StudentFriendly\n"
        f"{CHANNEL_PROMO_LINE}"
    )


def run_hackathon_pick(state: dict, today: str) -> bool:
    """Fallback pick: only runs when no job/internship posted today, so volume stays ~1/day."""
    if state["daily_lock"].get("hackathon") == today:
        print("hackathon: already posted today, skipping")
        return False

    try:
        results = devpost_search(challenge_type="online", status="open")
    except requests.RequestException as e:
        print(f"hackathon: failed to fetch Devpost listings: {e}")
        return False

    for h in results:
        if h.get("invite_only"):
            continue
        url = h.get("url", "")
        key = f"hackathon:{url}"
        if not url or key in state["posted"]:
            continue

        caption = build_hackathon_caption(h)
        send_telegram_photo(hackathon_photo_url(h), caption)

        state["posted"][key] = {"title": h.get("title", ""), "type": "hackathon", "date": today}
        state["daily_lock"]["hackathon"] = today
        print(f"hackathon: posted '{h.get('title')}'")
        return True

    print("hackathon: no open online hackathon found today")
    return False


def main() -> int:
    today = date.today().isoformat()
    state = load_state()

    posted_main = run_main_pick(state, today)
    posted_intern = run_intern_pick(state, today)

    # Hackathons are a fallback, not a 3rd guaranteed daily post - this keeps
    # the channel at ~1-2 posts/day instead of flooding it, while still never
    # going silent on a day the job scrapers come up empty.
    posted_hackathon = False
    if not posted_main and not posted_intern:
        posted_hackathon = run_hackathon_pick(state, today)

    save_state(state)

    if not posted_main and not posted_intern and not posted_hackathon:
        print("Nothing new to post today.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
