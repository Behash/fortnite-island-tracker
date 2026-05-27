import urllib.request
import json
import argparse
import urllib.parse
import csv
import sys
import os
from datetime import date, datetime, timedelta, timezone

ISLAND_CODE = "9642-0223-9671"
BASE_URL = "https://api.fortnite.com/ecosystem/v1/islands"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def write_csv(metrics, island_code, destination, fetched_at=None):
    if fetched_at is None:
        now = datetime.now(timezone.utc)
        fetched_at = now.strftime("%Y-%m-%dT%H:00:00")

    columns = [
        ("minutesPlayed",          "minutes_played"),
        ("uniquePlayers",          "unique_players"),
        ("plays",                  "plays"),
        ("peakCCU",                "peak_ccu"),
        ("averageMinutesPerPlayer","avg_minutes_per_player"),
        ("favorites",              "favorites"),
        ("recommendations",        "recommendations"),
    ]

    by_date = {}
    for api_key, _ in columns:
        for entry in metrics.get(api_key, []):
            d = entry["timestamp"][:10]
            by_date.setdefault(d, {})
            by_date[d][api_key] = entry["value"]

    for entry in metrics.get("retention", []):
        d = entry["timestamp"][:10]
        by_date.setdefault(d, {})
        by_date[d]["retention_d1"] = round(entry.get("d1", 0) * 100, 1)
        by_date[d]["retention_d7"] = round(entry.get("d7", 0) * 100, 1)

    fieldnames = ["fetched_at", "date", "island_code"] + [col for _, col in columns] + ["retention_d1_pct", "retention_d7_pct"]

    def make_row(d, row):
        return {
            "fetched_at": fetched_at,
            "date": d,
            "island_code": island_code,
            **{col: row.get(api_key, "") for api_key, col in columns},
            "retention_d1_pct": row.get("retention_d1", ""),
            "retention_d7_pct": row.get("retention_d7", ""),
        }

    if destination == "-":
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        for d in sorted(by_date):
            writer.writerow(make_row(d, by_date[d]))
    else:
        # Load existing (island_code, fetched_at) pairs to deduplicate
        existing = set()
        file_exists = os.path.isfile(destination) and os.path.getsize(destination) > 0
        if file_exists:
            with open(destination, newline="") as f:
                for row in csv.DictReader(f):
                    existing.add((row.get("island_code", ""), row.get("fetched_at", "")))

        new_rows = [
            make_row(d, by_date[d])
            for d in sorted(by_date)
            if (island_code, fetched_at) not in existing
        ]

        if not new_rows:
            print(f"Skipped (already have data for {island_code} at {fetched_at})")
            return

        with open(destination, "a", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_rows)
        print(f"CSV appended to: {destination}  ({len(new_rows)} row(s), fetched_at={fetched_at})")


def print_timeseries(label, entries, value_key="value", fmt=lambda v: v):
    print(f"\n  {label}:")
    for entry in entries:
        ts = entry["timestamp"][:10]
        val = fmt(entry[value_key])
        print(f"    {ts}: {val}")


def parse_args():
    today = date.today()
    default_end = today.isoformat()
    default_start = (today - timedelta(days=6)).isoformat()

    parser = argparse.ArgumentParser(
        description="Fetch Fortnite island info and metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 fortnite_island.py                          # last 7 days (default)
  python3 fortnite_island.py --start 2026-05-01       # from May 1 to today
  python3 fortnite_island.py --start 2026-05-01 --end 2026-05-20
  python3 fortnite_island.py --island 1234-5678-9012  # different island
""",
    )
    parser.add_argument(
        "--island",
        default=ISLAND_CODE,
        metavar="CODE",
        help=f"Island code (default: {ISLAND_CODE})",
    )
    parser.add_argument(
        "--start",
        default=default_start,
        metavar="YYYY-MM-DD",
        help=f"Start date (default: 7 days ago, {default_start})",
    )
    parser.add_argument(
        "--end",
        default=default_end,
        metavar="YYYY-MM-DD",
        help=f"End date (default: today, {default_end})",
    )
    parser.add_argument(
        "--csv",
        metavar="FILE",
        nargs="?",
        const="-",
        help="Export metrics to a CSV file (use '-' or omit filename to print to stdout)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    island_code = args.island

    print(f"Island:     {island_code}")
    print(f"Date range: {args.start} → {args.end}\n")

    info = fetch(f"{BASE_URL}/{island_code}")

    params = urllib.parse.urlencode({"startDate": args.start, "endDate": args.end})
    metrics = fetch(f"{BASE_URL}/{island_code}/metrics?{params}")

    print("=" * 50)
    print("ISLAND INFO")
    print("=" * 50)
    print(f"  Title:        {info.get('title')}")
    print(f"  Creator Code: {info.get('creatorCode')}")
    print(f"  Created In:   {info.get('createdIn')}")
    print(f"  Tags:         {', '.join(info.get('tags', []))}")

    days_returned = len(metrics.get("plays", []))
    print(f"\n{'=' * 50}")
    print(f"METRICS ({days_returned} day(s) with data)")
    print("=" * 50)

    print_timeseries("Minutes Played",         metrics["minutesPlayed"],          fmt=lambda v: f"{v:,}")
    print_timeseries("Unique Players",          metrics["uniquePlayers"],           fmt=lambda v: f"{v:,}")
    print_timeseries("Plays (sessions)",        metrics["plays"],                   fmt=lambda v: f"{v:,}")
    print_timeseries("Peak Concurrent (CCU)",   metrics["peakCCU"],                 fmt=lambda v: f"{v:,}")
    print_timeseries("Avg Minutes / Player",    metrics["averageMinutesPerPlayer"], fmt=lambda v: f"{v:.2f} min")
    print_timeseries("Favorites",               metrics["favorites"],               fmt=lambda v: f"{v:,}")
    print_timeseries("Recommendations",         metrics["recommendations"],         fmt=lambda v: f"{v:,}")

    print("\n  Retention:")
    for entry in metrics["retention"]:
        ts = entry["timestamp"][:10]
        d1 = entry.get("d1", 0) * 100
        d7 = entry.get("d7", 0) * 100
        print(f"    {ts}: D1={d1:.1f}%  D7={d7:.1f}%")

    print()

    if args.csv is not None:
        write_csv(metrics, island_code, args.csv)


if __name__ == "__main__":
    main()
