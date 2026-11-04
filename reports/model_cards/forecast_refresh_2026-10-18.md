# House/Senate Baseline Refresh - 2026-10-18

- **Model/version:** OLS fundamentals baselines, October 18 working-tree refresh; git/input
  fingerprint in `reports/refresh_2026-10-18/refresh_summary.json`.
- **Owner/review:** Alex Oswald; review before any public forecast and after certified results.
- **Scope/target:** 435 voting House seats and 35 Senate contests; expected two-party Democratic
  share, then correlated draws for seat/control probabilities. Senate includes FL/OH specials
  and 34 Democratic-caucus holdovers. Independents' caucus and ballot party are distinct.
- **Sources:** governed MEDSL 1976-2024 returns, cached ACS, official Senate roster, explicit
  candidacy evidence, special-election compilation, Census/TLC geography; all public aggregate
  or public professional officeholder facts (Tier 0). No personal political modeling.
- **Features:** House previous-map-aware lean, assumed national environment and incumbency;
  Senate state presidential lean, incumbency and midterm term. Known non-running holders
  receive no incumbency bonus. Missing candidacy is flagged, not declared verified.
- **Training/evaluation:** current model fits all available historical cycles; separate
  forward-only benchmark uses at least four prior cycles, prior-only national estimates,
  no single-vintage ACS and strictly previous presidential evidence for Senate. See detailed
  per-cycle metrics/predictions in the dated report. Historical candidates lack as-of archives.
- **Performance:** chronological House MAE 0.0654 (persistence 0.0796), Senate 0.0645 (0.0838);
  nominal 90% vote-share coverage 0.913/0.935. One-sided major-party outcomes are excluded
  even when a minor-party opponent made `uncontested_flag=False`. These are covered-race benchmarks,
  not validation of 2026 chamber probabilities. Presidential diagnostic loses to persistence
  (0.0467 vs 0.0321) and is not promoted as a national forecast estimator.
- **Assumptions:** unidentified national-environment shrinkage sweep 0.25-1.0; no best row
  selected. Asserted correlation variance shares 45/25/30 national/regional/unit retained
  (legacy parameter `state` is a per-seat shock in House simulations, not a shared state shock). Measured alternative
  remains experimental because full-chamber validation is absent.
- **Geography:** 262 unchanged-model seats, 38 Texas transferred seats, 135 state-lean fallback
  seats. Transfer population allocation and measured sigma 0.1223 are explicit; the latter
  includes cross-office error and is added in quadrature. No basis mapping is applied.
- **Exclusions/failure modes:** nonvoting delegates excluded; training uncontested races
  excluded; known incomplete precinct sources flagged. Stale maps, incomplete candidacy,
  noisy specials, missing polls/candidate quality, weak national identification and few
  independent cycles can dominate apparent precision. NJ baseline share remains weak and
  no longer supports a turnout ratio. No macro or live poll signal was added.
- **Release status:** internal scenarios only. Original September 30 sealed predictions are
  unchanged and remain the 2026 holdout; the refresh is not substituted for that registration.
