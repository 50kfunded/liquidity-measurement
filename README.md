# Liquidity Measurement and Market Data Quality

i made a BTC/USD market monitor that measures spread, nearby depth, and displayed execution cost on Kraken and Coinbase. it checks whether each data feed is usable, then saves the evidence behind unusual liquidity events so they can be inspected and replayed.

the question is: did liquidity change, or did the data feed fail?

## the first result

the included live evaluation recording is **0.0835 hours**, with **99.33% valid-feed coverage on each venue**. it produced **zero events** under rules fixed on a separate pilot sample. that is a recording and replay check, not enough evidence to estimate event frequencies or compare recovery times.

the pilot did not have enough complete 10 bps depth observations, so depth alerts were disabled for that evaluation. the research note explains this limitation.

![artificial liquidity event](report/synthetic/syntheti-001.png)

**the figure above is a synthetic example.** it shows a 20-second change on one venue while both feeds remain healthy. the repo also includes a separate artificial checksum-failure case. these are software checks, not market findings.

[read the research note](report/research-note.md) · [live sample report](report/live/report.md) · [artificial case studies](report/synthetic/report.md)

## what it shows

- current spread, mid-price, complete near-mid depth, and displayed buy/sell cost for $1,000, $5,000, and $10,000.
- whether a feed is valid, recovering, delayed, disconnected, or has failed validation.
- grouped events with trigger values, frozen thresholds, both venues' feed checks, and a timeline.
- spread and depth recovery, peak displayed-cost changes, and cases where recovery was not observed.

| event label | what the evidence supports |
|---|---|
| `feed_problem` | the observation is unusable because a feed or validation check failed. |
| `corroborated_liquidity_change` | both usable venues show a comparable change within the comparison window. |
| `venue_specific_liquidity_change` | both feeds are usable, but the comparable change appears on one venue. |
| `uncertain` | coverage or evidence is insufficient to choose a stronger label. |

these labels do not establish cause. “corroborated” does not mean proved market-wide, and displayed cost is not an actual execution price.

## setup

Python 3.11 or later is required. no exchange account, paid data service, or API key is needed.

```powershell
git clone https://github.com/50kfunded/liquidity-measurement.git
cd liquidity-measurement
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

on macOS or Linux, activate the environment with `source .venv/bin/activate` instead. if activation is unavailable on Windows, use `.\.venv\Scripts\python.exe` in place of `python` in the commands below.

## try it without a live feed

```text
python -m liquidity_measurement.cli demo --output results/my-demo
python -m liquidity_measurement.cli monitor results/my-demo/measures
```

open [the local monitor](http://127.0.0.1:8765). click an event to inspect spread, depth, price, feed checks, and displayed cost. the buy/sell control shows how the three order sizes compare. a saved recording is labelled as saved; old observations are never presented as a live feed.

## record a session

start with a development recording:

```text
python -m liquidity_measurement.cli record --output data/development-01 --seconds 120
```

raw messages go into `data/development-01`. sampled observations and the live view go into `data/development-01-measures`. in another terminal, with the environment active:

```text
python -m liquidity_measurement.cli monitor data/development-01-measures
```

then use a separate pilot to choose thresholds:

```text
python -m liquidity_measurement.cli record --output data/pilot-02 --phase pilot --seconds 1800
python -m liquidity_measurement.cli calibrate data/pilot-02 --output data/pilot-02-rules.json
```

calibration requires at least 60 usable spread samples per venue. depth needs 60 complete-band samples or its rule remains disabled. thresholds use pilot percentiles with minimum-change guards. choose a new rules file each time; existing frozen rules are not overwritten.

record later data using those fixed rules:

```text
python -m liquidity_measurement.cli record --output data/evaluation-02 --phase evaluation --rules data/pilot-02-rules.json --seconds 3600
```

evaluation requires a pilot rules file. synthetic thresholds cannot be used in a live session. each recording has its own connection IDs and starts from fresh snapshots. recorded failures request a rebuild; time outside a recording is unknown.

## replay and reproduce the report

reproduce the included live sample and both artificial case studies with one command:

```text
python scripts/reproduce.py --output results/reproduced
```

or analyse your own recording:

```text
python -m liquidity_measurement.cli replay data/evaluation-02 --output results/evaluation-02
python -m liquidity_measurement.cli report results/evaluation-02 --output results/evaluation-02-report
```

the output includes figures, a Markdown report, a coverage summary, event records, and a manual-review CSV template. fill in `reviewed_label`, `reviewer`, and `reason` for the events you inspect, then include it with:

```text
python -m liquidity_measurement.cli report results/evaluation-02 --output results/reviewed-report --reviews results/evaluation-02-report/manual-review-template.csv
```

manual reviews are counted separately and do not overwrite automatic labels. replay checks that evaluation rules were fixed before the session, came from a different pilot, and did not mix synthetic and live periods.

## the calculations and checks

the comparable measurement limit is 100 price levels per side. full-band depth is unavailable if those levels do not reach 10 bps from the mid-price. hypothetical fills stop at recorded depth rather than estimating extra quantity.

Kraken's CRC32 checks the top 10 levels. prices and quantities retain decimal precision, updates are applied in order, and out-of-scope levels are removed after each message. Coinbase's public `level2_batch` channel supplies snapshots and absolute size changes; its full book is retained locally. Coinbase has no equivalent checksum in this project.

checks also cover crossed or empty books, missing snapshots, reconnects, quiet feeds, book age, local processing delay, and exchange event-time order. the quiet-feed and delay limits are usability rules, not proof of the cause of a feed problem. keep the computer's clock synchronised when collecting data.

alerts persist for three sampled seconds and merge within 60 seconds. classification compares both feeds within five seconds of the event start. recovery needs 60 consecutive one-second samples within 20% of a pre-event baseline; event records also show 10% and 30% tolerances.

## checks

```text
python -m unittest discover -s tests -v
```

the suite uses known and artificial messages. it checks the published Kraken checksum, absolute size changes, corrupted books, dropped top-level updates, reconnections, processing backlog, missing snapshots, insufficient fills, classification, recovery gaps, recording failure, manual reviews, and repeatable replay. it makes no external network calls.

## files

| path | contents |
|---|---|
| `src/liquidity_measurement/` | collectors, book reconstruction, measurements, rules, events, replay, and local monitor. |
| `tests/` | deterministic book, feed-fault, measurement, event, and replay checks. |
| `recordings/` | the short live pilot, frozen rules, and later evaluation recording. |
| `report/` | research note, generated reports, case figures, and a monitor screenshot. |
| `scripts/reproduce.py` | one command to rebuild the release reports. |

new local recordings, environments, and generated results are ignored by Git. the published sample recordings are included separately so the report can be reproduced.

## limits

i have not measured real execution prices, trading profits, or classification accuracy on a large reviewed sample. public books cannot reveal hidden liquidity or guarantee the price a later order would receive. two venues and a home connection cannot establish a market-wide cause or professional trading-system performance.

the first live sample is deliberately small. more recording time, complete depth coverage, and manual review are needed before making a research claim about liquidity shocks.

## sources

- [Kraken checksum and book maintenance](https://docs.kraken.com/exchange/guides/websockets/book-checksum-v2)
- [Kraken book channel](https://docs-legacy.kraken.com/api/docs/websocket-v2/book/)
- [Coinbase Exchange WebSocket channels](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels)
