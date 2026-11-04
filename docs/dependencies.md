# Intake Dependencies

Registered 2026-10-20, before use. Owner: Alex Oswald. Optional `intake` extra only;
no change to the forecasting stack or restricted-data boundary.

| Library | License | Use |
|---|---|---|
| pypdf | BSD-3-Clause | Extract factual public candidate/aggregate-result tables from official PDFs |
| openpyxl | MIT | Read official election-authority XLSX workbooks; never edit raw files |
| beautifulsoup4 | MIT | Parse official public candidate tables with a structured HTML parser |
| lxml | BSD-3-Clause | HTML/XML parser for published aggregate feeds |

Keep original documents immutable and checksummed. Text extraction is not independent
verification of a malformed table: validate district completeness, party fields and
certified aggregate totals before promotion. Do not acquire voter/contact lists.
