import csv
import sys
import os
from datetime import date, timedelta
from collections import defaultdict

CSV_FILE = "island_metrics_history.csv"

METRICS = [
    ("plays",                  "Plays (sessions)"),
    ("unique_players",         "Unique Players"),
    ("minutes_played",         "Minutes Played"),
    ("peak_ccu",               "Peak CCU"),
    ("avg_minutes_per_player", "Avg Min / Player"),
    ("favorites",              "Favorites"),
    ("recommendations",        "Recommendations"),
    ("retention_d1_pct",       "Retention D1 %"),
    ("retention_d7_pct",       "Retention D7 %"),
]

NUMERIC = {k for k, _ in METRICS}
AVG_KEYS = {"avg_minutes_per_player", "retention_d1_pct", "retention_d7_pct", "peak_ccu"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_csv(path):
    if not os.path.isfile(path):
        print(f"No data file found at: {path}")
        print("Run: python3 fortnite_island.py --csv island_metrics_history.csv")
        sys.exit(1)

    islands = defaultdict(dict)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            code = row["island_code"]
            d = row["date"]
            islands[code][d] = row

    return {code: dict(sorted(days.items())) for code, days in sorted(islands.items())}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def pct_change(old, new):
    if old is None or new is None or old == 0:
        return None
    return (new - old) / old * 100


def agg_rows(rows_dict):
    totals = defaultdict(list)
    for row in rows_dict.values():
        for key in NUMERIC:
            v = to_float(row.get(key))
            if v is not None:
                totals[key].append(v)
    result = {}
    for key, vals in totals.items():
        result[key] = sum(vals) / len(vals) if key in AVG_KEYS else sum(vals)
    return result


def week_buckets(rows):
    buckets = defaultdict(dict)
    for d, row in rows.items():
        dt = date.fromisoformat(d)
        week_start = (dt - timedelta(days=dt.weekday())).isoformat()
        buckets[week_start][d] = row
    return dict(sorted(buckets.items()))


def fmt_val(key, val):
    if val is None:
        return "n/a"
    if key in ("retention_d1_pct", "retention_d7_pct"):
        return f"{val:.1f}%"
    if key == "avg_minutes_per_player":
        return f"{val:.2f} min"
    return f"{val:,.0f}"


def fmt_delta(pct):
    if pct is None:
        return ""
    arrow = "▲" if pct >= 0 else "▼"
    return f"{arrow} {abs(pct):.1f}%"


def divider(width=70):
    print("=" * width)


def section(title, width=70):
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print("=" * width)


# ---------------------------------------------------------------------------
# Per-island report
# ---------------------------------------------------------------------------

def report_island(code, rows):
    dates = sorted(rows.keys())
    total_days = len(dates)

    section(f"ISLAND: {code}  ({total_days} day(s) of data,  {dates[0]} → {dates[-1]})")

    # Daily table — last 14 days
    print(f"\n  {'Date':<12}" + "".join(f"{lbl:>18}" for _, lbl in METRICS[:5]))
    print("  " + "-" * 102)
    for d in dates[-14:]:
        row = rows[d]
        line = f"  {d:<12}"
        for key, _ in METRICS[:5]:
            line += f"{fmt_val(key, to_float(row.get(key))):>18}"
        print(line)

    # Day-over-day
    if total_days >= 2:
        prev_row, last_row = rows[dates[-2]], rows[dates[-1]]
        print(f"\n  Day-over-day ({dates[-2]} → {dates[-1]})")
        print(f"  {'Metric':<28} {'Prev':>12} {'Latest':>12} {'Change':>10}")
        print("  " + "-" * 64)
        for key, label in METRICS:
            old = to_float(prev_row.get(key))
            new = to_float(last_row.get(key))
            delta = fmt_delta(pct_change(old, new))
            print(f"  {label:<28} {fmt_val(key, old):>12} {fmt_val(key, new):>12} {delta:>10}")

    # Week-over-week
    buckets = week_buckets(rows)
    wk = sorted(buckets.keys())
    if len(wk) >= 2:
        prev_w, last_w = agg_rows(buckets[wk[-2]]), agg_rows(buckets[wk[-1]])
        print(f"\n  Week-over-week  (w/o {wk[-2]}  vs  w/o {wk[-1]})")
        print(f"  {'Metric':<28} {'Prev week':>14} {'This week':>14} {'Change':>10}")
        print("  " + "-" * 68)
        for key, label in METRICS:
            delta = fmt_delta(pct_change(prev_w.get(key), last_w.get(key)))
            print(f"  {label:<28} {fmt_val(key, prev_w.get(key)):>14} {fmt_val(key, last_w.get(key)):>14} {delta:>10}")
    else:
        print("\n  (Need 2+ weeks of data for week-over-week.)")


# ---------------------------------------------------------------------------
# Side-by-side comparison
# ---------------------------------------------------------------------------

def report_comparison(all_islands, top=False):
    codes = sorted(all_islands.keys())
    if len(codes) < 2:
        return

    col_w = 16
    section(f"SIDE-BY-SIDE COMPARISON  ({len(codes)} islands)")

    # Latest-day values
    print(f"\n  Latest day per island:")
    header = f"  {'Metric':<28}" + "".join(f"{c:>{col_w}}" for c in codes)
    print(header)
    print("  " + "-" * (28 + col_w * len(codes) + 2))
    latest = {code: rows[sorted(rows.keys())[-1]] for code, rows in all_islands.items()}
    for key, label in METRICS:
        line = f"  {label:<28}"
        for code in codes:
            line += f"{fmt_val(key, to_float(latest[code].get(key))):>{col_w}}"
        print(line)

    # All-time aggregates
    print(f"\n  All-time totals / averages:")
    print(header)
    print("  " + "-" * (28 + col_w * len(codes) + 2))
    agg = {code: agg_rows(rows) for code, rows in all_islands.items()}
    for key, label in METRICS:
        tag = "(avg)" if key in AVG_KEYS else "(sum)"
        line = f"  {label:<22} {tag:<6}"
        for code in codes:
            line += f"{fmt_val(key, agg[code].get(key)):>{col_w}}"
        print(line)

    # Best performer per metric
    if top:
        print(f"\n  {'Metric':<28}  {'WINNER':^22}  {'LOSER':^22}  {'Gap':>8}")
        print("  " + "-" * 86)
        for key, label in METRICS:
            vals = {code: agg[code].get(key) for code in codes if agg[code].get(key) is not None}
            if len(vals) < 2:
                continue
            ranked = sorted(vals, key=lambda c: vals[c], reverse=True)
            winner, loser = ranked[0], ranked[-1]
            gap = pct_change(vals[loser], vals[winner])
            gap_str = f"+{abs(gap):.1f}%" if gap is not None else "n/a"
            print(f"  {label:<28}  {'🏆 ' + winner:^22}  {'  ' + loser:^22}  {gap_str:>8}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="Summarise Fortnite island metrics from the history CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 summary.py                              # all islands
  python3 summary.py --island 9642-0223-9671      # one island only
  python3 summary.py --island 9642-0223-9671 --island 9752-7422-1395
""",
    )
    parser.add_argument(
        "--island",
        metavar="CODE",
        action="append",
        dest="islands",
        help="Filter to this island code (repeatable for multiple)",
    )
    parser.add_argument(
        "--top",
        action="store_true",
        help="Show winner/loser table with gap % in the comparison section",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    all_islands = load_csv(CSV_FILE)

    if args.islands:
        unknown = [c for c in args.islands if c not in all_islands]
        if unknown:
            print(f"Warning: no data found for: {', '.join(unknown)}")
        all_islands = {c: v for c, v in all_islands.items() if c in args.islands}
        if not all_islands:
            print("No matching islands in the data file.")
            sys.exit(1)

    codes = sorted(all_islands.keys())

    print(f"\nData file : {CSV_FILE}")
    print(f"Islands   : {len(codes)}  —  {', '.join(codes)}")

    for code in codes:
        report_island(code, all_islands[code])

    if len(codes) >= 2:
        report_comparison(all_islands, top=args.top)

    print()


if __name__ == "__main__":
    main()
