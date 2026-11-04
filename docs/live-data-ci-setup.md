# Live-Data CI Handoff

Owner: Alex Oswald. Prepared October 21; **not deployed or registered**. This machine
has no `gh` executable. No token was requested in chat, no secret printed, and no runner
was installed. Workflows are local changes until reviewed and pushed by the operator.

## Security Boundary

This repository is public. GitHub recommends self-hosted runners for private repositories
because public contributions can execute hostile code. Use a dedicated isolated/ephemeral
runner, not the workstation containing `.env`, SSH keys or personal files. Give it a
read-only copy of public registered data and no FEC/Census/FRED secrets. The manual live
job only reconciles cached inputs; it does not need acquisition credentials.
[GitHub runner guidance](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)

The workflow permits live reconciliation only on an explicit dispatch of the repository's
default branch. Hosted PR jobs run synthetic unit/integration tests. This guard reduces
exposure; it does not make arbitrary default-branch code or a compromised account safe.

## Registration

1. Review/push the workflow and this preflight. Provision the isolated host under a
   dedicated unprivileged account with Python 3.12 or later.
2. In `oz-tmg/us_election_predictions`, open Settings > Actions > Runners > New
   self-hosted runner. Select the host OS/architecture and follow GitHub's displayed
   download/configuration instructions. Use its short-lived registration token locally,
   not in this repository or chat. Add the label `elections-data`.
3. Stage a read-only `data/` lake outside the runner's disposable checkout. Set repository
   Actions variable `ELECTION_DATA_ROOT` to that absolute data-directory path, not the
   project root. It must contain `raw/`, `silver/` and `gold/` and match source manifests.
4. Start the runner; verify GitHub displays it online. Dispatch Quality Gates with
   `live_data=true` on the trusted default branch and inspect the first result.

Registration requires repository administration and a token that expires after one hour.
[GitHub registration steps](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)

## Local Preflight

```bash
EP_DATA_ROOT=/absolute/public-data-copy python scripts/check_live_runner.py
EP_REQUIRE_LIVE_DATA=1 EP_DATA_ROOT=/absolute/public-data-copy python -m pytest -q tests/data_quality
```

Missing inputs must fail, not skip. Known explicitly quarantined source defects do not
become accepted because this suite passes. Do not point the workflow at a data directory
inside `GITHUB_WORKSPACE`: checkout cleaning could erase that lake, and preflight refuses it.
Runner activation and the first GitHub execution remain pending operator authorization.
