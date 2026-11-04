# LinkedIn post — 2026-11-03 (publish before polls close, ~15:00 Pacific at the latest)

Tonight I find out how wrong I was. I decided that on September 30.

For the past year I've been building a US House and Senate forecasting model from certified returns, census geography and campaign filings — nonpartisan, fully reproducible, and built to refuse to produce a number when it can't justify one.

Here is what it says, frozen October 29, before a single vote was counted:

🏛 House: Democrats favoured under every assumption I'm willing to make about the national environment — P(control) from 58% to 83% across the band. The 90% seat range straddles 218 at every assumption, because 135 of 435 seats sit on newly drawn territory the model has no history for.

🏛 Senate: leans Democratic, but crosses the coin flip at the most conservative assumption — P(control) 48% to 79%. A lean, not a call.

Why a band and not a number? Because the key parameter — how much of the special-election overperformance carries into a general election — can't be estimated from the data that exists. So I sweep it and publish every row. Picking the row that did best afterwards is forbidden by the scoring rules I wrote in September.

The scorecard goes up when the states certify: both frozen runs, every row, Brier scores, calibration, interval coverage, against fixed comparators. If it did badly, that post will be longer than this one.

Full prediction, methodology and the seven things I expect to be wrong: [link to alexoswald.ca post]

Summary PDF attached — including every Senate race and the 47 contestable House seats, each shown as its own band rather than a single number.

Data: MIT Election Data and Science Lab; U.S. Census Bureau; Federal Election Commission (aggregate use only).

#DataScience #Forecasting #Elections #Analytics

---
Word count (body, excluding header/notes): ~245
