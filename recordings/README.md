# included recordings

these are public BTC/USD feed messages collected on 27 september 2026.

- `pilot-01`: a separate 90-second pilot used to freeze the thresholds.
- `pilot-01-rules.json`: the exact frozen rules. a copy is embedded in the evaluation metadata.
- `evaluation-01`: a later five-minute recording using those rules.

the pilot's original sampled observations are saved in `pilot-01/observations-at-calibration.jsonl`. their SHA256 matches `pilot_observations_sha256` in the rules file. the original live collector for evaluation was commit `7e12f59`.

each compressed journal stores original messages, receive times, connection events, processing delays, and sampling ticks in ordinal order. exchange timestamps remain in the wire messages. newer recordings also copy message type and exchange time into the envelope and save an implementation fingerprint.

the recordings include market data only. no exchange account credentials are used. intervals outside these sessions have unknown coverage.

the artificial case studies are generated separately by `python -m liquidity_measurement.cli demo`. their 2023 timestamps use a simulated clock; they were not collected from exchanges at those times.
