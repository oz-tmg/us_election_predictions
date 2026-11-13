# 2026 extraction cross-checks (2026-11-13)

These states publish 2026 results in a different layout from 2024. Their 2026 parser
is checked against a summary the state publishes separately, which is weaker than a
test against certified returns. Counts were unofficial when checked.

| State | Status | 2024 layout vs certified 2024 | 2026 parser vs state summary |
|---|---|---|---|
| AL | `parser_cross_checked_2026` | {'exact': 7} | {'exact': 8} |
| CA | `parser_cross_checked_2026` | {'exact': 53} | {'exact': 52} |
| ID | `parser_cross_checked_2026` | {'exact': 2} | {'exact': 3} |
| MD | `parser_tested_2024` | {'exact': 9} | {'exact': 8} |
| ND | `parser_cross_checked_2026` | {'exact': 2} | {'exact': 1} |
| NE | `parser_cross_checked_2026` | {'exact': 4} | {'exact': 4} |
| WA | `parser_cross_checked_2026` | {'exact': 11} | {'exact': 10} |
