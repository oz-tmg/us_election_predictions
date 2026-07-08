# Methodology

This document describes the statistical and machine learning methods used or worth evaluating for U.S. election prediction, explanation, and post-election analysis. It covers forecasting, multilevel regression with poststratification (MRP), turnout modeling, persuasion analysis, election-night modeling, and post-election diagnostics.

## Method Landscape: Who Uses What

| Actor / Community | Common Methods | Where It Fits |
|---|---|---|
| The Economist / Gelman-style models | Dynamic multilevel Bayesian models, state correlations, polling adjustments, informative priors, simulations | Presidential state and Electoral College forecasting. |
| FiveThirtyEight / Silver-style models | Poll aggregation, pollster ratings, fundamentals, time decay, correlated errors, simulations | President, Senate, House, governor forecasts. Historical benchmark even though the original 538 brand has changed/closed. |
| Cook Political Report, Sabato's Crystal Ball, Inside Elections, Split Ticket | Expert race ratings, district partisanship, incumbency, candidate quality, fundraising, local reporting | House, Senate, governor, state-level qualitative forecasting. |
| AP, Decision Desk HQ, NEP, network decision desks | Live vote tabulation, remaining-vote estimates, historical precinct/county patterns, exit polls or voter surveys, manual verification | Election-night projections and calls. |
| Catalist, TargetSmart, L2, DataTrust, Civis, BlueLabs, campaign analytics teams | Voter-file models, turnout propensity, support scores, persuasion scores, MRP-like post-election composition, experiments, uplift modeling | Campaign targeting, turnout, persuasion, and post-election electorate analysis. |
| Academic political science / statistics | Bayesian hierarchical models, MRP, ecological inference, causal inference, synthetic control, survey modeling, redistricting ensembles | Public opinion estimation, election explanation, redistricting diagnostics, causal effects. |
| Civic data projects | Open returns, precinct shapefiles, district crosswalks, data validation, reproducible pipelines | Data infrastructure and public-good datasets. |

## Forecasting Architecture

The project should separate the forecasting stack into five layers:

1. **Data layer:** election returns, polling, geography, demographics, candidate metadata, campaign finance, race ratings, and election administration data.
2. **Prior layer:** race baseline from past vote, incumbency, district/state partisanship, national environment, and office-specific fundamentals.
3. **Signal layer:** polling, fundraising, advertising, candidate quality, special-election results, early vote, and local context.
4. **Error layer:** state/district correlation, pollster house effects, undecided allocation, polling misses, turnout error, and redistricting mismatch.
5. **Simulation layer:** vote-share distributions, winner probabilities, Electoral College results, seat counts, chamber control, and scenario tests.

## General Forecast Model

A generic pre-election model can be represented as:

```text
vote_share[race, candidate] =
    national_environment
  + office_environment[office]
  + geography_baseline[state/district]
  + incumbency_effect
  + candidate_quality_effect
  + fundraising_or_spending_effect
  + polling_signal
  + turnout_adjustment
  + residual_error
```

The output should be a posterior predictive distribution, not a point estimate. Race-level outputs should include:

- expected two-party vote share;
- credible interval or prediction interval;
- probability of each candidate winning;
- simulated seat count or Electoral College contribution;
- explanation of the top model drivers;
- uncertainty decomposition, if feasible.

## Presidential Forecasting

Presidential forecasting should be state-centered and nationally correlated.

Recommended components:

- national popular vote latent trend;
- state-level lean relative to national vote;
- state polling averages with pollster house effects;
- national polls as a noisy signal for all states;
- economic and political fundamentals such as incumbency, approval, GDP/income, inflation, consumer sentiment, and party tenure;
- demographic and educational composition;
- historical polling error distribution;
- correlated state errors based on geography, demography, and past election behavior;
- Electoral College simulation.

Important distinction:

- The model should not simulate each state independently. A three-point polling miss in Pennsylvania is likely informative about Michigan and Wisconsin.

## Senate, House, and Governor Forecasting

Senate and governor races are statewide but more candidate-specific than presidential races. House races are district-level and heavily shaped by incumbency, district partisanship, fundraising, redistricting, and local candidate quality.

Recommended features:

- prior election results for the office;
- presidential vote by state or district;
- Cook PVI-style district lean or internally derived partisanship score;
- incumbency status, open seat, scandal, retirement, primary challenge;
- candidate elected-office experience;
- fundraising totals, cash on hand, burn rate, outside spending;
- race ratings from multiple forecasters, encoded as ordinal features;
- generic ballot and presidential approval;
- state or district demographic structure;
- redistricting changes and crosswalk uncertainty;
- polling where available.

Model family:

- baseline: regularized regression or Bayesian hierarchical regression;
- intermediate: hierarchical Bayesian model by office and cycle;
- machine learning benchmark: gradient boosted trees or random forests for feature screening and nonlinear effects;
- final public forecast: probabilistic hierarchical model, calibrated on historical cycles.

## State Legislative Forecasting

State legislative forecasting is more data-constrained than federal forecasting. Many races are uncontested, polling is rare, candidate metadata is inconsistent, and district boundaries change.

Recommended approach:

1. Build clean historical district results by chamber, district, state, and cycle.
2. Crosswalk old district results into current districts after redistricting.
3. Model uncontested races carefully instead of treating missing two-party vote as 100-0 truth.
4. Use state-level national environment, presidential/governor top-of-ticket results, incumbency, candidate filing data, and chamber-specific effects.
5. Simulate district outcomes jointly to estimate chamber control.

Special handling:

- uncontested races;
- multi-member districts;
- fusion voting;
- jungle primaries and top-two runoffs;
- ranked-choice jurisdictions where applicable;
- appointment and special-election cycles.

## Judicial Election Forecasting

Judicial races require different modeling assumptions because they may be partisan, nonpartisan, or retention elections.

### Partisan Judicial Elections

Useful features:

- state partisanship and recent statewide vote;
- candidate party;
- incumbency;
- court seat type;
- campaign finance and outside spending;
- endorsements;
- high-salience issues such as abortion, redistricting, crime, election law, labor, and education;
- ballot position;
- county-level partisan baseline.

### Nonpartisan Judicial Elections

Useful features:

- inferred partisan support from endorsements and donors;
- prior appointment source;
- bar association ratings;
- candidate occupation and judicial experience;
- local legal-community support;
- spending and media attention;
- ballot order;
- county-level partisan and turnout patterns.

### Retention Elections

Forecast target is usually `yes_share`, `no_share`, and `rolloff`, not a two-candidate vote share.

Useful features:

- appointment governor and party context;
- court level;
- years on bench;
- judicial performance commission recommendation;
- scandal or disciplinary history;
- major rulings that became campaign issues;
- organized opposition spending;
- state partisanship;
- ballot roll-off;
- historical retention baseline in that state.

Retention elections often have high yes-share baselines and low-information electorates, so models should emphasize uncertainty and identify when a race departs from the normal retention pattern.

## MRP

MRP stands for multilevel regression with poststratification. It is useful when survey data are too sparse to directly estimate opinion or vote preference for every district, state, or subgroup.

MRP workflow:

1. Collect survey responses with vote choice, approval, issue position, or turnout intent.
2. Fit a multilevel model using demographics and geography.
3. Build a poststratification frame from Census, ACS, voter file, or modeled electorate data.
4. Predict response for each cell in the frame.
5. Weight predictions by the population or expected electorate count in each cell.
6. Aggregate to district, state, media market, or other geography.

Common predictors:

- age group;
- gender;
- race and ethnicity;
- education;
- income;
- religion where available and lawful;
- party registration or modeled partisanship where lawful;
- past vote or precinct baseline;
- geography: state, district, county, metro/rural, media market.

MRP is especially useful for:

- district-level House estimates from national surveys;
- state legislative districts with little polling;
- judicial races where direct polling is rare;
- issue salience and candidate awareness;
- post-election composition estimates.

MRP limitations:

- poststratification frames can be wrong or stale;
- survey nonresponse can remain biased even after weighting;
- very granular cells create sparse-data problems;
- voter-file-enhanced MRP has privacy and legal constraints;
- results can look more precise than they are if uncertainty is under-modeled.

## Turnout Modeling

Turnout can be modeled at two levels: aggregate geography and individual voter file.

### Aggregate Turnout

Use when only public data are available.

Features:

- previous turnout by office and election type;
- registration counts by party where available;
- voting-age population and citizen voting-age population;
- age, education, income, race/ethnicity, urbanicity;
- competitiveness;
- ballot measures;
- weather and election administration features where relevant;
- early vote and mail ballot returns, with caution.

Model targets:

- total votes cast;
- turnout rate among voting-age or voting-eligible population;
- party composition proxy;
- roll-off between top-of-ticket and down-ballot races.

### Voter-File Turnout

Use only when legally permitted and appropriately governed.

Features:

- vote history;
- registration date;
- party registration where available;
- age and geography;
- household composition where lawful;
- contact history in campaign CRM data;
- absentee/mail status where lawful;
- modeled demographics.

Methods:

- logistic regression baseline;
- gradient boosted trees;
- hierarchical models by state and election type;
- survival or hazard-style models for early-vote timing;
- calibration by precinct or county totals.

Do not publish individual turnout scores.

## Persuasion and Mobilization Methods

Persuasion modeling belongs in a stricter governance tier than public forecasting because it can directly affect voter contact decisions.

Recommended methods:

- randomized controlled trials for canvassing, mail, SMS, phone, or digital ads;
- intent-to-treat and treatment-on-treated estimates;
- uplift modeling / heterogeneous treatment effects;
- causal forests or Bayesian hierarchical treatment models;
- pre/post matched comparisons only when experiments are impossible;
- geo experiments for media markets or precinct clusters;
- message testing with strict consent and privacy rules.

Key distinction:

- **Support model:** estimates candidate preference.
- **Turnout model:** estimates probability of voting.
- **Persuasion/uplift model:** estimates who changes because of contact.
- **Mobilization/uplift model:** estimates who votes because of contact.

The project should treat persuasion methods as research documentation unless there is a lawful, consented, non-deceptive, and access-controlled campaign use case.

## Election-Night Methods

Election-night modeling estimates the final result from partial returns.

Inputs:

- reported votes by county, precinct, or batch;
- expected vote remaining;
- mail, early, absentee, provisional, and Election Day categories;
- historical reporting order;
- precinct partisanship and turnout history;
- county/district demographics;
- state rules on counting and late-arriving ballots;
- official election office feeds and AP/DDHQ feeds where licensed.

Core methods:

1. **Expected vote model:** estimates how much vote remains.
2. **Composition model:** estimates where and what type of vote remains.
3. **Swing model:** compares reporting units to their historical baseline.
4. **Batch model:** accounts for mail/early/Election Day batches that have different partisan composition.
5. **Uncertainty model:** widens intervals when reporting is biased or unclear.
6. **Call rule:** call only when the trailing candidate has no realistic path given remaining vote and uncertainty.

Risks:

- red mirage / blue shift from reporting order;
- county websites changing totals or formats;
- duplicated batches;
- incomplete precinct labels;
- underestimated provisional or late mail ballots;
- using unofficial results as if certified.

The public product should describe election-night estimates as provisional and separate them from certified results.

## Post-Election Methods

Post-election analysis should explain what happened, why the model missed or succeeded, and how the electorate changed.

Methods:

- forecast error decomposition by geography and office;
- poll error decomposition by pollster, mode, population, state, and timing;
- ecological inference for demographic vote estimates;
- MRP using post-election surveys and certified returns;
- cast vote record analysis where available;
- ticket-splitting analysis;
- roll-off analysis for down-ballot and judicial races;
- precinct swing maps;
- turnout composition using voter files where lawful;
- counterfactual scenarios such as turnout-neutral swing or uniform-swing benchmarks.

Evaluation metrics:

- mean absolute error for vote share;
- Brier score and log score for win probability;
- calibration curve;
- coverage of prediction intervals;
- rank correlation of competitiveness;
- chamber-control accuracy;
- seat-count distribution error;
- county/precinct residual maps;
- subgroup uncertainty for MRP and ecological inference.

## Recommended Model Progression

1. Fundamentals-only baseline.
2. Polling average with time decay and pollster effects.
3. Hierarchical race model by office and cycle.
4. Correlated simulation layer.
5. MRP module for survey-rich problems.
6. Turnout module.
7. Election-night partial-return model.
8. Post-election decomposition and calibration report.
9. Judicial-specific models for retention, partisan, and nonpartisan races.

## Minimum Model Card

Every model should publish:

- model name and version;
- office and geography covered;
- training cycles;
- data sources and snapshot dates;
- target variable;
- core features;
- excluded features;
- assumptions;
- known failure modes;
- privacy classification;
- backtest results;
- calibration results;
- owner and review date.
