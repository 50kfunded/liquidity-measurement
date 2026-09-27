import json
from datetime import datetime
from pathlib import Path


def read_observations(directory):
    with (Path(directory) / "observations.jsonl").open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def plot_series(rows, output, title="BTC/USD displayed liquidity"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as dates
    import matplotlib.pyplot as plt

    expanded = []
    for row in rows:
        if expanded and (datetime.fromisoformat(row["time"]) - datetime.fromisoformat(expanded[-1]["time"])).total_seconds() > 1.5:
            expanded.append({"time": row["time"], "venues": {}})
        expanded.append(row)
    rows = expanded
    figure, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, layout="constrained")
    keys = (("spread_bps", "Spread (bps)"), ("depth_usd", "Depth within 10 bps (USD)"))
    colours = {"kraken": "#3267ce", "coinbase": "#cf7541"}
    times = [datetime.fromisoformat(r["time"].replace("Z", "+00:00")) for r in rows]
    venues = sorted({v for r in rows for v in r["venues"]})
    for venue in venues:
        values = [r["venues"].get(venue, {}) for r in rows]
        for axis, (key, label) in zip(axes, keys):
            axis.plot(times, [v.get(key) if v.get("status") == "valid" else None for v in values],
                      label=venue, color=colours.get(venue), linewidth=1.5)
            axis.set_ylabel(label)
        axes[2].step(times, [int(v.get("status") == "valid") for v in values],
                     where="post", label=venue, color=colours.get(venue))
    axes[0].set_title(title, loc="left", fontweight="bold")
    axes[0].legend(frameon=False)
    axes[2].set_yticks([0, 1], ["unusable", "valid"])
    axes[2].set_ylabel("Feed checks")
    axes[2].xaxis.set_major_formatter(dates.DateFormatter("%H:%M:%S"))
    axes[2].set_xlabel("UTC · gaps mean unavailable, never zero liquidity")
    for axis in axes:
        axis.grid(alpha=.2)
        axis.spines[["top", "right"]].set_visible(False)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=160)
    plt.close(figure)


def plot_costs(rows, output, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as dates
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True, layout="constrained")
    times = [datetime.fromisoformat(r["time"].replace("Z", "+00:00")) for r in rows]
    for axis, size in zip(axes, ("1000", "5000", "10000")):
        for venue, colour in (("kraken", "#3267ce"), ("coinbase", "#cf7541")):
            for side, style in (("buy", "-"), ("sell", "--")):
                values = []
                for index, row in enumerate(rows):
                    value = row["venues"].get(venue, {})
                    cost = value.get("displayed_cost", {}).get(size, {}).get(side, {}).get("cost_bps")
                    gap = index > 0 and (times[index] - times[index - 1]).total_seconds() > 1.5
                    values.append(cost if value.get("status") == "valid" and not gap else None)
                axis.plot(times, values, label=f"{venue} {side}", color=colour, linestyle=style, linewidth=1.4)
        axis.set_ylabel(f"Cost (bps)\n${int(size):,}")
        axis.grid(alpha=.2)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_title(title + " · displayed cost by order size", loc="left", fontsize=12, fontweight="bold")
    axes[0].legend(frameon=False, ncols=4, fontsize=9)
    axes[-1].xaxis.set_major_formatter(dates.DateFormatter("%H:%M:%S"))
    axes[-1].set_xlabel("UTC · solid: buy, dashed: sell · unavailable fills are gaps")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=160)
    plt.close(figure)
