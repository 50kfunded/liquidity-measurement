# Liquidity Measurement and Market Data Quality

did displayed liquidity change, or did the feed become unreliable?

this is a small live recording. it does not establish event frequencies across markets.

phase: evaluation. recorded time: 0.0835 hours.

![spread, depth, and feed checks](liquidity.png)

| venue | valid time | complete 10 bps depth |
|---|---:|---:|
| kraken | 99.33% | 177.4 seconds |
| coinbase | 99.33% | 1.0 seconds |

events: 0. checksum failures: 0. reconnections: 0.

## event records

no events were detected with these fixed rules in this recording. there are insufficient events to compare spread and depth recovery.

## manual review

no manual classification reviews have been recorded in this output. automated fault tests are a software check and are reported separately.


## method and limits

measurements use the first 100 levels per side. depth within 10 bps is unavailable unless both recorded sides reach the band boundary. displayed costs walk these levels for $1,000, $5,000, and $10,000 converted to BTC at the current mid-price.

pilot rules use the 99th spread percentile and 1st depth percentile with minimum-change guards. liquidity triggers persist for 3 sampled seconds; neighbouring alerts merge within 60 seconds. classification compares both feeds within 5 seconds of the event start. recovery requires 60 consecutive one-second samples within 20% of the baseline; gaps break that run. 10% and 30% tolerances are also saved in each event record.

Kraken CRC32 verifies the top 10 levels, not every recorded level. Coinbase has no equivalent book checksum here. heartbeat sequence numbers are not used as level2 update sequence numbers. neither feed proves that silent loss of every deeper-level update can be detected.

the book can change before an order arrives. no fees, hidden liquidity, queue position, or actual fills are modelled. two healthy venues can corroborate a change, but they cannot prove a market-wide cause. periods outside recorded sessions have unknown coverage.

full trigger values, thresholds, feed reasons, baselines, and timelines are saved in events.json.
