# Data Governance and Privacy

This project can involve sensitive political data even when the source is public. Voter files, donor records, campaign CRM exports, inferred demographics, survey responses, contact history, and judicial-election spending data can create privacy, legal, ethical, and reputational risks.

## Governance Goals

1. Keep the project nonpartisan, lawful, and privacy-aware.
2. Prevent misuse of personal political data.
3. Maintain clear data lineage from raw source to model output.
4. Separate public research artifacts from restricted operational datasets.
5. Avoid publishing individualized predictions, inferred ideology, contact lists, or sensitive voter attributes.
6. Ensure every dataset has a documented license, permitted use, retention rule, and access tier.

## Data Classification

| Tier | Name | Examples | Storage / Access Rule |
|---:|---|---|---|
| 0 | Public aggregate | certified election returns, district-level results, ACS tables, TIGER boundaries | Can be used in public reports with citation and versioning. |
| 1 | Public but sensitive aggregate | precinct returns, small-area demographics, judicial retention by precinct | Public reporting allowed, but suppress tiny cells and document limitations. |
| 2 | Public personal data | FEC itemized donors, some state voter-file fields, candidate filings | Restricted analysis; do not repurpose for solicitation, harassment, or commercial targeting. |
| 3 | Licensed personal data | state voter files, L2, TargetSmart, Catalist, DataTrust, consumer append data | Private encrypted storage, role-based access, no public export, license review required. |
| 4 | Campaign operational data | VAN/CRM exports, canvass responses, persuasion survey answers, contact history, volunteer notes | Highest restriction; use only for documented lawful purpose; never publish. |
| 5 | Derived sensitive data | modeled partisanship, race/ethnicity inference, turnout score, persuasion score, support score | Treat at least as sensitive as the input data; public release only after aggregation and review. |

## Dataset Intake Checklist

Before acquiring or loading a dataset, complete this checklist:

- Source owner and URL/vendor.
- Acquisition date and cycle.
- Legal basis or license.
- Permitted uses.
- Prohibited uses.
- Geography covered.
- Offices covered.
- Personal data fields.
- Sensitive fields.
- Data retention requirement.
- Redistribution rules.
- Required attribution.
- Update cadence.
- Cost.
- Responsible owner.
- Privacy classification tier.
- Deletion process.

## Voter Files

Voter-file access rules vary by state. Some states allow broad access; others limit access to political, governmental, election-related, scholarly, or noncommercial purposes. Many states suppress or protect fields such as Social Security number, driver’s license number, full date of birth, signatures, and information for Address Confidentiality Program participants or other protected groups.

Project rules:

- Do not acquire voter files until a state-specific legal review is completed.
- Store raw voter files outside the public repository.
- Never commit voter files, voter IDs, voter contact fields, or derived voter-level scores to Git.
- Use encryption at rest and in transit.
- Use role-based access.
- Hash internal person IDs where possible.
- Aggregate before reporting.
- Document whether the file can be used for research, journalism, campaign activity, or only official/election purposes.
- Do not combine voter files with consumer data without explicit legal and ethical review.
- Do not publish individual-level turnout propensity, support, persuasion, party, race/ethnicity inference, religion, or issue scores.

## Donor Data

Federal campaign-finance data are public but restricted in use. Contributor information from FEC reports must not be sold or used to solicit contributions or for commercial purposes, except for limited committee-name/address usage. State donor-data rules can differ and should be reviewed separately.

Project rules:

- Use donor data for aggregate analysis of fundraising, spending, donor geography, and candidate support networks.
- Do not use contributor names or addresses for solicitation, marketing, list building, or commercial targeting.
- Aggregate donor geography to ZIP, county, district, media market, or state for public reporting.
- Suppress small cells where re-identification risk is high.
- Separate federal donor data from state donor data because legal rules and fields differ.

## Campaign CRM and Contact Data

Campaign CRM data is operationally sensitive and may contain:

- voter contact history;
- canvass responses;
- volunteer notes;
- issue preference;
- support IDs;
- turnout plan;
- phone/email/address;
- internal tags;
- donation history;
- event attendance;
- opt-out status.

Project rules:

- Do not ingest campaign CRM data into the public project.
- If used in a private fork, create a separate restricted environment.
- Require written authorization from the data owner.
- Respect opt-outs and suppression lists.
- Delete exports after use when no longer needed.
- Do not use CRM data to train public models unless outputs are fully aggregated and approved.

## Survey and Polling Data

Survey data may be public, purchased, or internally collected.

Rules:

- Store respondent-level data in restricted storage.
- Preserve survey weights, mode, sample frame, field dates, likely-voter screen, and pollster metadata.
- Document whether crosstabs are weighted or unweighted.
- Avoid over-reporting small demographic cells.
- Use MRP or hierarchical models to stabilize estimates, but communicate uncertainty.
- Do not publish raw respondent records.

## Derived Sensitive Attributes

Some features are sensitive because they infer traits not directly provided by a person.

Examples:

- modeled race or ethnicity;
- modeled religion;
- modeled ideology;
- modeled party support;
- turnout propensity;
- persuasion likelihood;
- issue support;
- inferred household relationships;
- inferred address stability.

Rules:

- Treat derived sensitive data as restricted even when built from public inputs.
- Public reports should aggregate to geography or group-level summaries.
- Do not publish scores at the person, household, or exact-address level.
- Document feature provenance and uncertainty.

## Public Release Rules

Before publishing a dataset, model output, or report:

- Confirm the license permits redistribution.
- Remove personal identifiers.
- Aggregate to a safe geography.
- Suppress small cells.
- Remove exact addresses and contact details.
- Remove campaign-specific strategy notes.
- Include source citations and snapshot dates.
- Include uncertainty and data-quality notes.
- Avoid claims that could mislead voters about official results.

## Access Controls

Recommended access tiers:

| Role | Allowed Data |
|---|---|
| Public reader | Aggregated reports, model cards, public source metadata. |
| Project analyst | Public aggregate and public-sensitive aggregate data. |
| Restricted analyst | Licensed personal data and derived sensitive data after approval. |
| Data steward | Raw restricted files, licenses, deletion, retention, audit logs. |
| External collaborator | Only approved extracts under a data-sharing agreement. |

## Storage Rules

- Raw data is immutable.
- Restricted raw data is stored outside the public Git repository.
- Use `.gitignore` and pre-commit secret/file-size checks.
- Encrypt restricted datasets.
- Maintain checksums for raw snapshots.
- Use manifests for source, license, acquisition time, and transformation lineage.
- Keep a deletion log for restricted datasets.
- Use synthetic or sampled fake data in tests.

## Retention Rules

Default retention proposal:

| Data Type | Retention |
|---|---|
| Public aggregate election returns | Indefinite with versioning. |
| Public geography and Census data | Indefinite with versioning. |
| Public donor records | As needed, but only for permitted analytical use. |
| Licensed voter file | Per contract or state rule; review annually. |
| Campaign CRM export | Delete after project completion or per agreement. |
| Survey respondent-level data | Delete or archive securely after analysis window. |
| Derived sensitive scores | Same or stricter retention than source data. |

## Legal and Ethical Review Triggers

Require review before:

- acquiring a voter file;
- joining voter file data to consumer, donor, location, or CRM data;
- building person-level persuasion, turnout, or support scores;
- publishing small-area demographic estimates;
- using donor records in any contact or marketing workflow;
- using AI/LLM enrichment on personal political data;
- scraping sites with restrictive terms;
- publishing judicial candidate profiles that include allegations, disciplinary records, or donor networks.

## AI and LLM Use

Allowed:

- summarizing public methodology documents;
- extracting structured fields from public candidate pages with citation and review;
- generating report drafts from approved aggregate data;
- code assistance on non-sensitive data.

Restricted:

- sending voter files, donor lists, CRM data, or survey respondent records to third-party LLMs;
- generating individualized political messages from sensitive attributes;
- using LLMs to infer protected traits without documented purpose and review;
- creating deceptive campaign content or impersonation.

## Incident Response

If restricted data is exposed:

1. Stop the pipeline or publication.
2. Remove public access immediately.
3. Record what was exposed, when, and to whom.
4. Rotate credentials if needed.
5. Notify the data owner or vendor if required.
6. Review logs and repository history.
7. Purge cached artifacts where possible.
8. Document remediation.
9. Add a prevention test or control.

## Governance Owner

Until this project has a larger team, the project owner is also the data steward. That means every restricted dataset should have a documented acquisition decision, permitted-use note, and deletion plan before modeling begins.
