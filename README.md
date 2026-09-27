# Liquidity Measurement and Market Data Quality

i’m building a BTC/USD market monitor that measures spread, nearby depth, and displayed execution cost on Kraken and Coinbase. it checks the data feed before classifying a liquidity change, then saves the evidence so each event can be inspected and replayed.

the question is: did liquidity change, or did the data feed fail?

## current stage

project setup. the feeds, measurements, and event analysis will follow in separate stages.
