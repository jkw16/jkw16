#!/usr/bin/env python3
"""Fetch the contributions calendar for a GitHub user.

Primary path is the GraphQL API with a token (GITHUB_TOKEN) — always fresh.
Falls back to scraping GitHub's public contributions HTML page, which GitHub
serves from a cache that can lag several days.

Writes data/contributions.json with raw days plus streaks, best day,
and monthly totals.

Usage: fetch_contributions.py [username]   (default: GITHUB_USER or 'jkw16')
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"
PAGE_URL = "https://github.com/users/{user}/contributions"
GRAPHQL_URL = "https://api.github.com/graphql"

HEADERS = {"User-Agent": "Mozilla/5.0 (profile-readme-refresh)"}

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            color
          }
        }
      }
    }
  }
}
"""


def fetch_graphql(user, token):
    """Authenticity-fresh path: GraphQL contributionsCollection."""
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": GRAPHQL_QUERY, "variables": {"login": user}},
        headers={"Authorization": f"Bearer {token}", **HEADERS},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"GraphQL error: {body['errors'][0].get('message')}")
    calendar = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    raw = {"weeks": calendar["weeks"]}
    return flatten_days(raw)


def parse_days_from_html(html_text):
    """HTML path: parse either the embedded React JSON or the <td> calendar."""
    html = BeautifulSoup(html_text, "html.parser")
    raw = _embedded_json(html)
    if raw is not None:
        return flatten_days(raw)
    return _fallback_days(html)


def _embedded_json(html):
    """GitHub embeds the calendar as JSON for its React app."""
    for tag in html.select("script[type='application/json']"):
        try:
            blob = json.loads(tag.string or "")
        except Exception:  # noqa: BLE001
            continue
        found = _walk_for_weeks(blob)
        if found is not None:
            return found
    return None


def _walk_for_weeks(node):
    """Find the first dict-shaped object containing 'weeks' (defensive)."""
    if isinstance(node, dict):
        if "weeks" in node and isinstance(node["weeks"], list) and node["weeks"]:
            return node
        for value in node.values():
            found = _walk_for_weeks(value)
            if found is not None:
                return found
    return None


def _fallback_days(html):
    """Current markup: <td data-date data-level> cells + <tool-tip for=id> text
    ("No contributions on October 5th." / "5 contributions on ...")."""
    tooltips = {
        t.get("for"): t.get_text(" ", strip=True)
        for t in html.find_all("tool-tip", attrs={"for": True})
    }
    days = []
    for cell in html.find_all("td", attrs={"data-date": True}):
        tip = tooltips.get(cell.get("id"), "")
        head = tip.split(" contributions", 1)[0]
        count = 0 if "No contributions" in head else (int(head) if head.isdigit() else 0)
        days.append(
            {"date": cell["data-date"], "count": count, "level": int(cell.get("data-level") or 0)}
        )
    # GitHub's calendar table is written column-major (one <tr> per weekday);
    # restore date order and drop any duplicates before returning.
    days.sort(key=lambda d: d["date"])
    deduped = {d["date"]: d for d in days}
    return list(deduped.values()) if days else None


def flatten_days(raw):
    days = []
    for week in raw.get("weeks", []):
        candidates = week["contributionDays"] if "contributionDays" in week else week
        if isinstance(candidates, dict):
            candidates = [candidates]
        for day in candidates:
            if isinstance(day, dict):
                day = {
                    "date": day.get("date", ""),
                    "count": day.get("contributionCount", day.get("count", 0)),
                    "color": day.get("color", day.get("fill")),
                }
            try:
                days.append(
                    {
                        "date": day["date"][:10],
                        "count": int(day.get("count", 0)),
                        "color": day.get("color"),
                    }
                )
            except (KeyError, TypeError):
                continue
    return sorted(days, key=lambda d: d["date"])


def compute_stats(days):
    valid = [d for d in days if d["date"]]
    total = sum(d["count"] for d in valid)
    best = max(valid, key=lambda d: d["count"]) if valid else {"date": None, "count": 0}

    current_streak = 0  # trailing run of >0 days, walking backwards from today/last
    for day in reversed(valid):
        if day["count"] > 0:
            current_streak += 1
        elif datetime.now(timezone.utc).strftime("%Y-%m-%d") == day["date"]:
            continue  # today still in progress, doesn't break a live streak
        else:
            break

    longest_streak = run = 0
    for day in valid:
        run = run + 1 if day["count"] > 0 else 0
        longest_streak = max(longest_streak, run)

    monthly = {}
    for day in valid:
        monthly.setdefault(day["date"][:7], 0)
        monthly[day["date"][:7]] += day["count"]

    return {
        "total": total,
        "best_day": best,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "monthly_totals": monthly,
    }


def main():
    user = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_USER", "jkw16")

    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        try:
            days = fetch_graphql(user, token)
            source = "graphql"
        except Exception as exc:  # noqa: BLE001
            print(f"GraphQL fetch failed ({exc}); falling back to HTML scrape", file=sys.stderr)
    else:
        days = None

    if not days:
        resp = requests.get(PAGE_URL.format(user=user), headers=HEADERS, timeout=30)
        resp.raise_for_status()
        days = parse_days_from_html(resp.text)
        source = "html-scrape"
    if not days:
        sys.exit("no contribution days parsed — GitHub markup may have changed")

    payload = {
        "user": user,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "days": days,
        **compute_stats(days),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "contributions.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out} ({len(days)} days, total={payload['total']}, "
          f"streak={payload['current_streak']}, best={payload['best_day']['count']})")


if __name__ == "__main__":
    main()