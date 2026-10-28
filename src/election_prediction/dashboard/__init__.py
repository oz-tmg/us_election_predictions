"""Dashboard: run bundles, their exporter, and the Plotly Dash app that reads them.

The dashboard never reads the medallion layers directly. Every number it shows comes from
a *run bundle* — a small, versioned, checksummed snapshot written by ``export.py`` from
committed build artefacts — so a chart re-derives from a clean checkout (CLAUDE.md §2.4)
and the deployed app never needs the 13 GB data lake. See ``docs/deployment-plan.md``.
"""
