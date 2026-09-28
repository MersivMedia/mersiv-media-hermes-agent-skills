#!/usr/bin/env python3
"""Generate client-facing ROI charts for the ai-opportunity-discovery skill.

Input is a small JSON file the agent writes alongside analysis/selected.md.

Schema:
{
  "company": "Acme Co",
  "currency": "$",
  "opportunities": [
    {"name": "Invoice intake",
     "hours_per_year": 1019,
     "dollars_per_year": 48900,
     "effort_weeks": 6,
     "one_time_cost": 45000,
     "monthly_run_cost": 900,
     "start_month": 1}
  ]
}

Usage:
  python3 make_charts.py --input roi.json --outdir charts/
"""

import argparse
import json
import os
import sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
except ImportError:
    sys.exit("matplotlib not installed. Run: pip install matplotlib")

PALETTE = ["#2E5E8A", "#4A9D7E", "#C8873D", "#8A5A8C", "#5A6B7A", "#B05656"]
GRID = {"color": "#DDDDDD", "linewidth": 0.8}


def _style(ax, title, xlabel="", ylabel=""):
    ax.set_title(title, fontsize=13, fontweight="bold", pad=14, color="#222222")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10, color="#555555")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color="#555555")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#BBBBBB")
    ax.tick_params(colors="#555555", labelsize=9)


def _money(cur):
    def fmt(x, _pos):
        if abs(x) >= 1_000_000:
            return f"{cur}{x / 1_000_000:.1f}M"
        if abs(x) >= 1_000:
            return f"{cur}{x / 1_000:.0f}k"
        return f"{cur}{x:.0f}"
    return FuncFormatter(fmt)


def _save(fig, outdir, name):
    path = os.path.join(outdir, name)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor="white")
    plt.close(fig)
    print(f"wrote {path}")


def chart_savings(data, outdir):
    opps = data["opportunities"]
    cur = data.get("currency", "$")
    names = [o["name"] for o in opps]
    dollars = [o["dollars_per_year"] for o in opps]
    hours = [o.get("hours_per_year", 0) for o in opps]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    y = range(len(names))

    ax1.barh(list(y), dollars, color=PALETTE[: len(names)] * 3, height=0.6)
    ax1.set_yticks(list(y))
    ax1.set_yticklabels(names, fontsize=10)
    ax1.invert_yaxis()
    ax1.xaxis.set_major_formatter(_money(cur))
    ax1.xaxis.grid(True, **GRID)
    ax1.set_axisbelow(True)
    _style(ax1, "Estimated annual savings", "Per year")
    for i, v in enumerate(dollars):
        ax1.text(v, i, f"  {cur}{v:,.0f}", va="center", fontsize=9, color="#333333")

    ax2.barh(list(y), hours, color="#4A9D7E", height=0.6)
    ax2.set_yticks(list(y))
    ax2.set_yticklabels(names, fontsize=10)
    ax2.invert_yaxis()
    ax2.xaxis.grid(True, **GRID)
    ax2.set_axisbelow(True)
    _style(ax2, "Hours returned to the team", "Hours per year")
    for i, v in enumerate(hours):
        ax2.text(v, i, f"  {v:,.0f}", va="center", fontsize=9, color="#333333")

    fig.suptitle(data.get("company", ""), fontsize=10, color="#888888", y=0.99)
    _save(fig, outdir, "savings_by_opportunity.png")


def chart_payback(data, outdir, months=36):
    opps = data["opportunities"]
    cur = data.get("currency", "$")
    cum_sav, cum_cost = [], []
    s = c = 0.0
    for m in range(months + 1):
        for o in opps:
            start = o.get("start_month", 1)
            if m == start:
                c += o.get("one_time_cost", 0)
            if m >= start:
                c += o.get("monthly_run_cost", 0)
                s += o["dollars_per_year"] / 12.0
        cum_sav.append(s)
        cum_cost.append(c)

    net = [a - b for a, b in zip(cum_sav, cum_cost)]
    payback = next((m for m, v in enumerate(net) if v > 0), None)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = list(range(months + 1))
    ax.plot(x, cum_sav, color="#4A9D7E", lw=2.5, label="Cumulative savings")
    ax.plot(x, cum_cost, color="#B05656", lw=2.5, ls="--", label="Cumulative cost")
    ax.fill_between(x, cum_cost, cum_sav, where=[a > b for a, b in zip(cum_sav, cum_cost)],
                    color="#4A9D7E", alpha=0.15, interpolate=True)

    if payback is not None:
        ax.axvline(payback, color="#C8873D", lw=1.5, ls=":")
        ax.annotate(f"Pays for itself\nmonth {payback}",
                    xy=(payback, cum_sav[payback]),
                    xytext=(payback + 1.5, cum_sav[payback] * 0.55),
                    fontsize=10, color="#C8873D", fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#C8873D"))

    ax.yaxis.set_major_formatter(_money(cur))
    ax.yaxis.grid(True, **GRID)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=10)
    _style(ax, "When this pays for itself", "Months from start", "Cumulative")
    _save(fig, outdir, "payback.png")
    return payback


def chart_effort_impact(data, outdir):
    opps = data["opportunities"]
    cur = data.get("currency", "$")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    xs = [o.get("effort_weeks", 8) for o in opps]
    ys = [o["dollars_per_year"] for o in opps]
    mx = max(xs) * 1.25 or 1
    my = max(ys) * 1.25 or 1

    ax.axvspan(0, mx / 2, 0, 1, color="#4A9D7E", alpha=0.05)
    ax.axhline(my / 2, color="#CCCCCC", lw=1)
    ax.axvline(mx / 2, color="#CCCCCC", lw=1)

    for i, o in enumerate(opps):
        ax.scatter(xs[i], ys[i], s=260, color=PALETTE[i % len(PALETTE)],
                   alpha=0.85, edgecolor="white", zorder=3, linewidth=1.5)
        ax.annotate(o["name"], (xs[i], ys[i]), xytext=(0, 16),
                    textcoords="offset points", ha="center", fontsize=9.5,
                    color="#333333")

    ax.text(mx * 0.02, my * 0.96, "QUICK WINS", fontsize=9,
            color="#4A9D7E", fontweight="bold")
    ax.text(mx * 0.72, my * 0.96, "BIG BETS", fontsize=9,
            color="#888888", fontweight="bold")
    ax.set_xlim(0, mx)
    ax.set_ylim(0, my)
    ax.yaxis.set_major_formatter(_money(cur))
    ax.grid(True, alpha=0.3, **GRID)
    ax.set_axisbelow(True)
    _style(ax, "Where to start: effort vs. impact",
           "Weeks to first results", "Annual savings")
    _save(fig, outdir, "effort_impact.png")


def chart_timeline(data, outdir):
    opps = data["opportunities"]
    fig, ax = plt.subplots(figsize=(11, 1.4 + 0.9 * len(opps)))
    for i, o in enumerate(opps):
        start = o.get("start_month", 1)
        weeks = o.get("effort_weeks", 8)
        ax.barh(i, weeks / 4.33, left=start, height=0.45,
                color=PALETTE[i % len(PALETTE)], alpha=0.9)
        ax.text(start + weeks / 4.33 + 0.15, i, f"{weeks} wks",
                va="center", fontsize=9, color="#555555")
    ax.set_yticks(range(len(opps)))
    ax.set_yticklabels([o["name"] for o in opps], fontsize=10)
    ax.invert_yaxis()
    ax.xaxis.grid(True, **GRID)
    ax.set_axisbelow(True)
    _style(ax, "Delivery timeline", "Month")
    _save(fig, outdir, "timeline.png")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="path to roi.json")
    p.add_argument("--outdir", default="charts", help="output directory")
    a = p.parse_args()

    with open(a.input) as f:
        data = json.load(f)
    if not data.get("opportunities"):
        sys.exit("no opportunities in input")
    os.makedirs(a.outdir, exist_ok=True)

    chart_savings(data, a.outdir)
    payback = chart_payback(data, a.outdir)
    chart_effort_impact(data, a.outdir)
    chart_timeline(data, a.outdir)

    total_d = sum(o["dollars_per_year"] for o in data["opportunities"])
    total_h = sum(o.get("hours_per_year", 0) for o in data["opportunities"])
    print(json.dumps({"total_dollars_per_year": total_d,
                      "total_hours_per_year": total_h,
                      "payback_month": payback}, indent=2))


if __name__ == "__main__":
    main()
