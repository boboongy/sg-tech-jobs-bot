# SG Tech Jobs Bot

Posts one zero-experience-required IT job and one internship listing from
[MyCareersFuture](https://www.mycareersfuture.gov.sg/) to the
[@sgtechjob](https://t.me/sgtechjob) Telegram channel, once a day, via
GitHub Actions.

## How it works

- `scripts/post_jobs.py` searches MCF for Information Technology jobs,
  picks one zero-experience "Junior Executive / Non-executive" role and
  one internship-titled role, cleans up the description, and posts each
  to Telegram.
- `data/state.json` tracks which jobs have already been posted (so the
  same job never posts twice) and a daily lock (so only one of each type
  posts per day). The workflow commits this file back to the repo after
  every run.
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
