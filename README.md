# SG Tech Jobs Bot

Posts one zero-experience-required IT job and one internship listing from
[MyCareersFuture](https://www.mycareersfuture.gov.sg/), plus an open online
hackathon from [Devpost](https://devpost.com/) on days with no new job/intern
post, to the [@sgtechjob](https://t.me/sgtechjob) Telegram channel, via
GitHub Actions.

## How it works

- `scripts/post_jobs.py` searches MCF for Information Technology jobs,
  picks one zero-experience "Junior Executive / Non-executive" role and
  one internship-titled role, cleans up the description, and posts each
  to Telegram.
- If neither a job nor an internship post happens on a given run (MCF had
  nothing new), the script falls back to posting one open, online,
  non-invite-only hackathon from Devpost. This keeps the channel active
  without flooding it with 3 guaranteed posts a day.
- `data/state.json` tracks which jobs/hackathons have already been posted
  (so nothing posts twice) and a daily lock per post type (so each type
  posts at most once per day). The workflow commits this file back to the
  repo after every run.
- `.github/workflows/daily-post.yml` runs the script every day at 9:00 AM
  Singapore time, and can also be triggered manually from the **Actions**
  tab ("Run workflow").

## One-time setup

1. Go to the repo's **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Name: `TELEGRAM_BOT_TOKEN`. Value: your bot's token from Telegram's
   `@BotFather`.
4. Save. That's the only manual step — everything else runs on its own.

## Running it manually

Go to the **Actions** tab → **Daily Job Post** → **Run workflow**, to post
immediately instead of waiting for the daily schedule.
