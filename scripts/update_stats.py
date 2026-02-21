"""
Spider-Verse Stats Updater
Fetches real GitHub stats via API and writes them into stats-card.svg
"""

import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
USERNAME  = "AkishRaj"
TOKEN     = os.environ["GH_TOKEN"]          # set as GitHub Actions secret
SVG_PATH  = "stats-card.svg"
# ─────────────────────────────────────────────────────────────────────────────


def gh_request(url):
    """GET request to GitHub REST API."""
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def graphql_request(query):
    """POST request to GitHub GraphQL API."""
    data = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


# ── 1. Total Contributions ────────────────────────────────────────────────────
def get_total_contributions():
    query = """
    {
      user(login: "%s") {
        contributionsCollection {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """ % USERNAME
    result = graphql_request(query)
    return result["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


# ── 2. Repo count ─────────────────────────────────────────────────────────────
def get_repo_count():
    data = gh_request(f"https://api.github.com/users/{USERNAME}")
    return data.get("public_repos", 0)


# ── 3. Contribution dates for streak calculation ──────────────────────────────
def get_contribution_dates():
    """Returns a set of date strings (YYYY-MM-DD) where user made contributions."""
    query = """
    {
      user(login: "%s") {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """ % USERNAME
    result = graphql_request(query)
    weeks = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    active_days = set()
    for week in weeks:
        for day in week["contributionDays"]:
            if day["contributionCount"] > 0:
                active_days.add(day["date"])
    return active_days


def calculate_streaks(active_days):
    """Calculate current streak and longest streak from a set of contribution dates."""
    if not active_days:
        return 0, 0, "N/A", "N/A", "N/A"

    sorted_days = sorted(active_days)
    today = datetime.now(timezone.utc).date()
    yesterday = today.replace(day=today.day - 1) if today.day > 1 else today

    # ── Current streak ────────────────────────────────────────────────────────
    current_streak = 0
    current_start  = None
    check_date     = today

    # Start from today; if today has no contribution, start from yesterday
    if str(today) not in active_days:
        check_date = yesterday

    if str(check_date) in active_days:
        current_streak = 1
        current_start  = check_date
        d = check_date
        while True:
            prev = d.toordinal() - 1
            prev_date = datetime.fromordinal(prev).date()
            if str(prev_date) in active_days:
                current_streak += 1
                current_start   = prev_date
                d = prev_date
            else:
                break

    current_end_str   = str(check_date) if current_streak > 0 else "N/A"
    current_start_str = str(current_start) if current_start else "N/A"

    # ── Longest streak ────────────────────────────────────────────────────────
    longest_streak     = 0
    longest_start      = None
    longest_end        = None
    run_streak         = 1
    run_start          = sorted_days[0]

    for i in range(1, len(sorted_days)):
        prev_ord = datetime.strptime(sorted_days[i - 1], "%Y-%m-%d").toordinal()
        curr_ord = datetime.strptime(sorted_days[i],     "%Y-%m-%d").toordinal()
        if curr_ord - prev_ord == 1:
            run_streak += 1
        else:
            if run_streak > longest_streak:
                longest_streak = run_streak
                longest_start  = run_start
                longest_end    = sorted_days[i - 1]
            run_streak = 1
            run_start  = sorted_days[i]

    # Last run
    if run_streak > longest_streak:
        longest_streak = run_streak
        longest_start  = run_start
        longest_end    = sorted_days[-1]

    def fmt(d):
        if d is None:
            return "N/A"
        return datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d, %Y")

    return (
        current_streak,
        longest_streak,
        fmt(current_start_str) if current_start_str != "N/A" else "N/A",
        fmt(longest_start),
        fmt(longest_end),
    )


# ── 4. Build SVG ──────────────────────────────────────────────────────────────
def build_svg(total_commits, current_streak, longest_streak,
              streak_start, longest_start, longest_end, repo_count):

    # Streak ring: dasharray based on streak (max visual = 30 days = full ring ~289)
    ring_fill = min(int((current_streak / 30) * 270), 270)
    ring_gap  = 289 - ring_fill

    updated = datetime.now(timezone.utc).strftime("%b %-d, %Y")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="210" viewBox="0 0 900 210">
  <defs>
    <linearGradient id="cardBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0D0221"/>
      <stop offset="100%" style="stop-color:#1A0515"/>
    </linearGradient>
    <linearGradient id="barGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#E10600"/>
      <stop offset="100%" style="stop-color:#FF4500"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="redGlow">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <pattern id="dots" x="0" y="0" width="8" height="8" patternUnits="userSpaceOnUse">
      <circle cx="4" cy="4" r="1" fill="#E10600" opacity="0.07"/>
    </pattern>
    <pattern id="web" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
      <line x1="30" y1="0" x2="30" y2="60" stroke="#E10600" stroke-width="0.3" opacity="0.1"/>
      <line x1="0" y1="30" x2="60" y2="30" stroke="#E10600" stroke-width="0.3" opacity="0.1"/>
      <line x1="0" y1="0" x2="60" y2="60" stroke="#E10600" stroke-width="0.3" opacity="0.07"/>
      <line x1="60" y1="0" x2="0" y2="60" stroke="#E10600" stroke-width="0.3" opacity="0.07"/>
      <circle cx="30" cy="30" r="10" fill="none" stroke="#E10600" stroke-width="0.3" opacity="0.09"/>
      <circle cx="30" cy="30" r="20" fill="none" stroke="#E10600" stroke-width="0.3" opacity="0.06"/>
    </pattern>
  </defs>

  <!-- Background -->
  <rect width="900" height="210" rx="16" fill="url(#cardBg)"/>
  <rect width="900" height="210" rx="16" fill="url(#dots)"/>
  <rect width="900" height="210" rx="16" fill="url(#web)"/>
  <rect width="900" height="210" rx="16" fill="none" stroke="#E10600" stroke-width="2" opacity="0.8" filter="url(#glow)"/>
  <rect width="900" height="210" rx="16" fill="none" stroke="#E10600" stroke-width="0.5"/>

  <!-- ── SECTION 1: Total Commits ── -->
  <text x="62" y="44" text-anchor="middle" font-size="22" fill="#E10600" filter="url(#glow)">🕷️</text>
  <text x="62" y="90" text-anchor="middle"
    font-family="Arial Black, Impact, sans-serif"
    font-size="50" font-weight="900" fill="#FFFFFF" filter="url(#glow)">{total_commits}</text>
  <text x="62" y="116" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="11" font-weight="700"
    fill="#CCCCCC" letter-spacing="1">TOTAL COMMITS</text>
  <text x="62" y="135" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="9" fill="#888888">Feb 2023 – Present</text>
  <rect x="15" y="148" width="94" height="3" rx="2" fill="#1A0A2E"/>
  <rect x="15" y="148" width="{min(94, int(94 * min(total_commits/500, 1)))}" height="3" rx="2" fill="url(#barGrad)" opacity="0.9"/>

  <!-- Divider 1 -->
  <line x1="155" y1="20" x2="155" y2="190" stroke="#E10600" stroke-width="0.8" opacity="0.4"/>

  <!-- ── SECTION 2: Current Streak (ring) ── -->
  <text x="328" y="38" text-anchor="middle" font-size="20" fill="#FF4500" filter="url(#redGlow)">🔥</text>
  <circle cx="328" cy="108" r="52" fill="none" stroke="#E10600" stroke-width="1" opacity="0.2" filter="url(#redGlow)"/>
  <circle cx="328" cy="108" r="46" fill="#0D0221"/>
  <circle cx="328" cy="108" r="46" fill="none" stroke="#2A0A0A" stroke-width="6"/>
  <circle cx="328" cy="108" r="46" fill="none" stroke="#E10600" stroke-width="6"
    stroke-dasharray="{ring_fill} {ring_gap}" stroke-dashoffset="-10"
    stroke-linecap="round" filter="url(#redGlow)"/>
  <circle cx="328" cy="108" r="39" fill="none" stroke="#E10600" stroke-width="1" opacity="0.3"/>
  <text x="328" y="102" text-anchor="middle"
    font-family="Arial Black, Impact, sans-serif"
    font-size="40" font-weight="900" fill="#FFFFFF">{current_streak}</text>
  <text x="328" y="120" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="9" font-weight="700"
    fill="#E10600" letter-spacing="1">DAY STREAK</text>
  <text x="328" y="174" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="10" font-weight="700"
    fill="#E10600" letter-spacing="2">CURRENT STREAK</text>
  <text x="328" y="189" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="9" fill="#888888">{streak_start}</text>

  <!-- Divider 2 -->
  <line x1="502" y1="20" x2="502" y2="190" stroke="#E10600" stroke-width="0.8" opacity="0.4"/>

  <!-- ── SECTION 3: Longest Streak ── -->
  <text x="600" y="44" text-anchor="middle" font-size="22" fill="#E10600" filter="url(#glow)">⚡</text>
  <text x="600" y="90" text-anchor="middle"
    font-family="Arial Black, Impact, sans-serif"
    font-size="50" font-weight="900" fill="#FFFFFF" filter="url(#glow)">{longest_streak}</text>
  <text x="600" y="116" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="11" font-weight="700"
    fill="#CCCCCC" letter-spacing="1">LONGEST STREAK</text>
  <text x="600" y="135" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="9" fill="#888888">{longest_start} – {longest_end}</text>
  <rect x="553" y="148" width="94" height="3" rx="2" fill="#1A0A2E"/>
  <rect x="553" y="148" width="{min(94, int(94 * min(longest_streak/30, 1)))}" height="3" rx="2" fill="url(#barGrad)" opacity="0.9"/>

  <!-- Divider 3 -->
  <line x1="748" y1="20" x2="748" y2="190" stroke="#E10600" stroke-width="0.8" opacity="0.4"/>

  <!-- ── SECTION 4: Repos ── -->
  <text x="825" y="44" text-anchor="middle" font-size="20" fill="#E10600" filter="url(#glow)">🕸️</text>
  <text x="825" y="90" text-anchor="middle"
    font-family="Arial Black, Impact, sans-serif"
    font-size="50" font-weight="900" fill="#FFFFFF" filter="url(#glow)">{repo_count}</text>
  <text x="825" y="116" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="11" font-weight="700"
    fill="#CCCCCC" letter-spacing="1">REPOSITORIES</text>
  <text x="825" y="135" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="9" fill="#888888">Public Projects</text>
  <rect x="779" y="148" width="94" height="3" rx="2" fill="#1A0A2E"/>
  <rect x="779" y="148" width="94" height="3" rx="2" fill="url(#barGrad)" opacity="0.9"/>

  <!-- Bottom tagline + last updated -->
  <text x="450" y="200" text-anchor="middle"
    font-family="Arial Black, Impact, sans-serif"
    font-size="8" font-weight="900" fill="#E10600"
    letter-spacing="3" opacity="0.6">🕷️  WITH GREAT POWER COMES GREAT RESPONSIBILITY  🕷️</text>
  <text x="450" y="208" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="7"
    fill="#444444">last updated: {updated} UTC</text>

</svg>"""
    return svg


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🕷️  Fetching GitHub stats for", USERNAME)

    total_commits = get_total_contributions()
    print(f"   Total contributions : {total_commits}")

    repo_count = get_repo_count()
    print(f"   Public repos        : {repo_count}")

    active_days = get_contribution_dates()
    current_streak, longest_streak, streak_start, longest_start, longest_end = calculate_streaks(active_days)
    print(f"   Current streak      : {current_streak} day(s) — from {streak_start}")
    print(f"   Longest streak      : {longest_streak} day(s) — {longest_start} → {longest_end}")

    svg = build_svg(
        total_commits, current_streak, longest_streak,
        streak_start, longest_start, longest_end, repo_count
    )

    with open(SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"✅  {SVG_PATH} updated successfully!")
