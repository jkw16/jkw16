#!/usr/bin/env python3
"""Scrape the public contributions calendar for a GitHub user.

Writes data/contributions.json with raw days plus streaks, best day,
and monthly totals. No auth — GitHub's public contributions HTML page.

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

HEADERS = {"User-Agent": "Mozilla/5.0 (profile-readme-refresh)"}


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
    return days if days else None


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
    resp = requests.get(PAGE_URL.format(user=user), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = BeautifulSoup(resp.text, "html.parser")

    raw = _embedded_json(html)
    if raw is not None:
        days = flatten_days(raw)
    else:
        days = _fallback_days(html)
    if not days:
        sys.exit("no contribution days parsed — GitHub markup may have changed")

    payload = {
        "user": user,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
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