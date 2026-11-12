"""Build the published prediction summary PDF (blog/exports/).

Run from the repository root:  python blog/build_pdf.py
Requires reportlab (pip install reportlab) and the figures in blog/figures/ (make_figures.py).

Every number typed here was cross-checked against the committed artefacts it cites:
reports/refresh_2026-10-29/{band_changes_vs_seal.csv, senate_specification_gate.json,
refresh_summary.json, chronological_evaluation.json, projection_seats.csv} and
reports/preregistration_2026-11-03.json. The seat tables are read from
blog/exports/contestable_seats_2026-10-29.csv, which blog/figures/make_figures.py writes
from projection_seats.csv via load_contestable(). If a run is re-frozen, re-check every
literal below before rebuilding; this file is deliberately not a live template."""

import csv as _csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = str(ROOT / "blog" / "exports" / "savepoint_2026_midterm_prediction_2026-11-03.pdf")
FIG = str(ROOT / "blog" / "figures") + "/"

INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#52514e")
MUTED = colors.HexColor("#898781")
GRID = colors.HexColor("#e1e0d9")
S1 = colors.HexColor("#2a78d6")
S2 = colors.HexColor("#eb6834")
CRIT = colors.HexColor("#d03b3b")
SURF = colors.HexColor("#f4f3ef")


def st(name, **kw):
    base = dict(
        fontName="Helvetica", fontSize=9.3, leading=12.6, textColor=INK, alignment=TA_LEFT, spaceAfter=5
    )
    base.update(kw)
    return ParagraphStyle(name, **base)


H0 = st("H0", fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=2)
SUB = st("SUB", fontSize=10.5, leading=14, textColor=INK2, spaceAfter=8)
H1 = st("H1", fontName="Helvetica-Bold", fontSize=12.5, leading=15, spaceBefore=9, spaceAfter=4)
H2 = st(
    "H2", fontName="Helvetica-Bold", fontSize=10.2, leading=13, spaceBefore=6, spaceAfter=3, textColor=INK2
)
P = st("P")
SMALL = st("SMALL", fontSize=8.2, leading=10.8, textColor=INK2)
TINY = st("TINY", fontSize=7.4, leading=9.6, textColor=MUTED)
BUL = st("BUL", leftIndent=10, bulletIndent=0)
BANNER = st("BANNER", fontName="Helvetica-Bold", fontSize=8.6, leading=11, textColor=colors.white)


def banner(text):
    t = Table([[Paragraph(text, BANNER)]], colWidths=[7.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), INK),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


TH = st("TH", fontName="Helvetica-Bold", fontSize=8.0, leading=9.6, textColor=INK2, spaceAfter=0)
TC = st("TC", fontSize=8.4, leading=10.4, spaceAfter=0)


def table(data, widths, header=True, align_right_from=1, font=8.6, zebra=True, pad=3):
    data = [
        [
            Paragraph(str(c), TH) if i == 0 and header else (Paragraph(str(c), TC) if len(str(c)) > 28 else c)
            for c in row
        ]
        for i, row in enumerate(data)
    ]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font),
        ("LEADING", (0, 0), (-1, -1), font + 2.4),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK2),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ("ALIGN", (align_right_from, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if header:
        style += [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), INK2),
            ("ALIGN", (align_right_from, 0), (-1, 0), "RIGHT"),
        ]
    if zebra:
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), SURF))
    t.setStyle(TableStyle(style))
    return t


def fig(name, width=7.0 * inch):
    im = Image(FIG + name)
    r = im.imageHeight / im.imageWidth
    im.drawWidth = width
    im.drawHeight = width * r
    return im


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        0.75 * inch,
        0.5 * inch,
        "Savepoint Analytics · US Election Analysis · modelled projection, published as a band on 2026-11-03 · nonpartisan",
    )
    canvas.drawRightString(7.75 * inch, 0.5 * inch, f"p. {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(
    OUT,
    pagesize=letter,
    leftMargin=0.75 * inch,
    rightMargin=0.75 * inch,
    topMargin=0.7 * inch,
    bottomMargin=0.8 * inch,
    title="2026 US Midterm Prediction — Savepoint Analytics",
    author="Alex Oswald, Savepoint Analytics",
    subject="House and Senate projection, published as a sensitivity band on 2026-11-03",
)
S = []

# ---------------- Page 1 ----------------
S += [
    Paragraph("What the Model Says, and How I Will Grade It", H0),
    Paragraph(
        "2026 US House and Senate projection · final run frozen 2026-10-29 · published 2026-11-03, before any vote was counted",
        SUB,
    ),
    banner(
        "MODELLED PROJECTION, PUBLISHED AS A BAND, NOT A POINT · The key parameter cannot be estimated from available data, so the model is run at five values of it (a sweep) and every row is published. Reading one row without the others is the error this design exists to prevent."
    ),
    Spacer(1, 8),
    Paragraph("The short version", H1),
    Paragraph(
        "<b>House:</b> Democrats favoured to take control under every assumption in the band: P(Democratic control) 0.58 to 0.83. The majority line is 218 seats. The model’s plausible range crosses that line at every assumption.  It cannot fully rule out either party winning the House, because 135 seats sit on new boundaries the model has no history for.",
        P,
    ),
    Paragraph(
        "<b>Senate:</b> leans Democratic, but not enough to call it: P(Democratic control) 0.48 to 0.79.  It's a coin flip at the most conservative assumption. The seats nearest even at the middle assumption: North Carolina 0.58, Iowa 0.50, Texas 0.49, Maine 0.49, Montana 0.44.",
        P,
    ),
    Paragraph("The prediction, every row", H1),
    Paragraph(
        "The national environment comes from eight special elections (Apr 2025 – Jun 2026) in which Democratic candidates beat their district's 2024 presidential baseline by 21.2 points of margin on average. Special electorates are not general electorates, so some fraction of that, referred to as <i>shrinkage</i>, carries into November. One cycle cannot identify it; four historical cycles do not narrow it. So the model does not estimate shrinkage; it <b>sweeps</b> it. A sweep is a modelling term that amounts to \"try every answer\": I don't know how much of that 21 points carries into November, so instead of guessing, I ran the model five times, assuming a quarter of it carries, a third, half, three-quarters, or potentially all of it. Every row below is one of those runs.",
        P,
    ),
]
band = [
    [
        "Shrinkage",
        "Implied nat. Dem share",
        "House mean seats",
        "House 90% range",
        "P(Dem House)",
        "Senate Dem seats /100",
        "P(Dem Senate)",
    ],
    ["0.25", "0.524", "234.7", "123 – 355", "0.584", "51.1", "0.481"],
    ["0.33", "0.532", "240.3", "129 – 361", "0.616", "51.7", "0.517"],
    ["0.50", "0.550", "252.3", "142 – 373", "0.681", "53.0", "0.591"],
    ["0.75", "0.577", "270.0", "160 – 389", "0.762", "55.0", "0.698"],
    ["1.00", "0.603", "287.8", "177 – 402", "0.832", "56.9", "0.791"],
]
S += [
    table(band, [0.8 * inch, 1.2 * inch, 1.0 * inch, 1.05 * inch, 0.95 * inch, 1.15 * inch, 0.85 * inch]),
    Paragraph(
        "Final pre-election run 2026-10-29 (reports/refresh_2026-10-29/). 2024 House national input, contested races total-vote weighted: 0.497; each row adds a shrinkage multiple of the specials swing. 435 House seats; 35 Senate races up, 34 Democratic and 31 Republican holdovers, 100 seats reconciled to the official roster.",
        TINY,
    ),
    Paragraph("What the House forecast is standing on", H1),
]
comp = [
    ["House seats by prior source", "Seats", "Sigma", "Note"],
    ["Model (own 2024 result, boundaries unchanged)", "262", "0.112", "Fitted residual sigma"],
    [
        "Model, transferred (Texas, precinct vote transfer onto 2026 plan)",
        "38",
        "0.122",
        "Measured on a 2020→2022 backtest, not assumed",
    ],
    [
        "Fallback: state presidential lean (redrawn, no transfer yet)",
        "135",
        "0.146",
        "Least-informed seats; should score visibly worse",
    ],
    ["Total", "435", "", ""],
]
S += [
    table(comp, [3.3 * inch, 0.6 * inch, 0.6 * inch, 2.6 * inch]),
    Paragraph(
        "Nine states use a different congressional map in 2026 than in 2024, affecting 173 seats: AL, CA, FL, LA, NC, OH, TN, TX, UT. Litigation is live in nine of the ten states with map activity (Missouri votes its 2022 map and keeps its priors). The register records the plan in effect as of its last verification; a recheck on 2026-11-03 found no change since.",
        SMALL,
    ),
    PageBreak(),
]

# ---------------- Page 2 ----------------
S += [fig("fig-09-sealed-vs-current.png", 4.0 * inch), Spacer(1, 2)]
S += [
    Paragraph("Two frozen runs: the September seal beside the October run", H1),
    Paragraph(
        "<b>The difference between the two runs doesn't reflect an increasingly souring view of the Republican party. The difference is due to the correction of recorded data and specification defects, each gated or documented before the election.</b>",
        P,
    ),
    Paragraph(
        "A second prediction was sealed on 2026-09-30 (SHA-256 of predictions <font face='Courier'>4de09ecf82f218ee…</font>) and is the registered holdout. It is scored beside the October run, by the same rules, never replaced by it.",
        P,
    ),
]
cmp = [
    [
        "Shrinkage",
        "House P(Dem) sealed → Oct 29",
        "House mean seats sealed → Oct 29",
        "Senate P(Dem) sealed → Oct 29",
        "Senate seats sealed → Oct 29",
    ],
    ["0.25", "0.536 → 0.584", "228.2 → 234.7", "0.272 → 0.481", "47.8 → 51.1"],
    ["0.33", "0.562 → 0.616", "233.1 → 240.3", "0.298 → 0.517", "48.3 → 51.7"],
    ["0.50", "0.620 → 0.681", "243.6 → 252.3", "0.357 → 0.591", "49.2 → 53.0"],
    ["0.75", "0.701 → 0.762", "259.3 → 270.0", "0.450 → 0.698", "50.7 → 55.0"],
    ["1.00", "0.770 → 0.832", "275.1 → 287.8", "0.545 → 0.791", "52.1 → 56.9"],
]
S += [
    table(cmp, [0.8 * inch, 1.55 * inch, 1.7 * inch, 1.55 * inch, 1.5 * inch]),
    Paragraph("Source: reports/refresh_2026-10-29/band_changes_vs_seal.csv.", TINY),
    Paragraph("Why the House moved a little", H2),
    Paragraph(
        "+6 to +13 mean seats. About 4.6 at every row from restoring New York's 26 districts, which an over-strict validator had quarantined (findings F-2, F-3); the rest from a refreshed specials baseline that raised the measured swing from 18.8 to 21.2 points.",
        P,
    ),
    Paragraph("Why the Senate moved a lot and why none of it is new evidence about the environment", H2),
    Paragraph(
        "<b>1. An open-seat term.</b> The September specification credited every seat with its incumbent's advantage, including seats the incumbent is leaving. A specification that treats an open seat as held by its party, without the personal incumbency term, was promoted by a chronological backtest over 661 held-out Senate races (230 open): MAE 0.0645 → 0.0638, open-seat MAE 0.0663 → 0.0638, 90% coverage 0.935 → 0.944. Seven Republican-held open seats (AL, IA, KY, MT, NC, TX, WY) moved 13–17 points toward the Democratic candidate; four Democratic-held open seats (IL, MI, MN, NH) moved 5–7 points the other way.",
        P,
    ),
    Paragraph(
        "<b>2. The party crosswalk reconciles.</b> The seal derived party from certified returns and came up two seats short of the actual Democratic caucus. The October run uses the official roster: 34 Democratic holdovers, 47-seat caucus, 100 seats accounted for.",
        P,
    ),
    Paragraph(
        "<b>3. Two more races.</b> The Florida and Ohio special Senate elections join the universe: 33 → 35 races. October's Senate is therefore better specified, not better informed; the environment is as unidentified as it was in September.",
        P,
    ),
    PageBreak(),
]

# ---------------- Seat-by-seat pages ----------------

_rows = list(_csv.DictReader(open(ROOT / "blog" / "exports" / "contestable_seats_2026-10-29.csv")))
_sen = [r for r in _rows if r["office"] == "us_senate"]
_hou = [r for r in _rows if r["office"] == "us_house"]
_hold = {"D": "Dem", "R": "Rep", "O": "Other"}
_sen_c = [r for r in _sen if 0.25 <= float(r["p_dem_shrinkage_0.5"]) <= 0.75]
_above = ", ".join(r["seat"] for r in _sen if float(r["p_dem_shrinkage_0.5"]) > 0.75)
_below = ", ".join(r["seat"] for r in _sen if float(r["p_dem_shrinkage_0.5"]) < 0.25)

S += [
    Paragraph(
        "Seat by seat with three tiers, because the model knows different amounts about different seats", H1
    ),
    Paragraph(
        "Each bar runs from P(Democratic win) at shrinkage 0.25 to 1.0; the dot is 0.5. Colour is the party holding the seat. The Senate panel is every race on the ballot. The House panel is the 47 seats projected from their own district history (or Texas's measured transfer) that sit inside 0.25–0.75 at the middle assumption. The 135 redrawn seats without a transferred prior are excluded from the chart and shown by state on the next page: their number is a state average and says nothing about the district.",
        P,
    ),
    fig("fig-10-contestable-seats.png", 6.2 * inch),
    PageBreak(),
]


def _trow(r, house=False):
    third = (
        ("transfer" if r["prior_source"] == "model_transferred" else "own history")
        if house
        else r["candidacy_verified"]
    )
    return [
        r["seat"],
        _hold[r["holder"]],
        third,
        f"{float(r['p_dem_shrinkage_0.25']):.2f}",
        f"{float(r['p_dem_shrinkage_0.5']):.2f}",
        f"{float(r['p_dem_shrinkage_1.0']):.2f}",
    ]


sen_tbl = [["State", "Held by", "Candidacy", "P(D) @0.25", "P(D) @0.5", "P(D) @1.0"]] + [
    _trow(r) for r in _sen_c
]
hh = ["Seat", "Held by", "Prior", "@0.25", "@0.5", "@1.0"]
half = (len(_hou) + 1) // 2
h1 = [hh] + [_trow(r, True) for r in _hou[:half]]
h2 = [hh] + [_trow(r, True) for r in _hou[half:]]
hw = [0.55 * inch, 0.5 * inch, 0.75 * inch, 0.5 * inch, 0.45 * inch, 0.45 * inch]
side = Table(
    [[table(h1, hw, font=7.4, pad=1.2), table(h2, hw, font=7.4, pad=1.2)]],
    colWidths=[3.45 * inch, 3.45 * inch],
)
side.setStyle(
    TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
    )
)
S += [
    Paragraph("The Senate: 15 races inside 0.25–0.75 at the middle assumption", H2),
    Paragraph(
        f"The other twenty sit above 0.75 ({_above}) or below 0.25 ({_below}). Candidacy: whether the sitting member's ballot status was verified from an official source or assumed.",
        SMALL,
    ),
    table(
        sen_tbl, [0.6 * inch, 0.7 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch], font=7.6, pad=1.5
    ),
    Paragraph("The House's 47 contestable seats the model can see (sorted by P(D) at 0.5)", H2),
    Paragraph(
        "Favoured party differs from the current holder in 4 of the 300 model-informed seats at the middle assumption (MI-10, TX-23, TX-32, TX-09) and in 24 at the top of the band. The list is almost entirely Republican-held because every row of the band assumes a Democratic-leaning environment; the model has no race-level inputs, so a Democratic seat vulnerable for local reasons is invisible to it.",
        SMALL,
    ),
    side,
    Spacer(1, 6),
]
fb = [
    [
        "State",
        "Fallback seats",
        "Held D / R / other",
        "Rep-held seats, P(D) @0.25 / 0.5 / 1.0",
        "Dem-held seats, P(D) @0.25 / 0.5 / 1.0",
    ],
    ["AL", "7", "2 / 5 / 0", "0.18 / 0.22 / 0.33", "0.57 / 0.63 / 0.74"],
    ["CA", "52", "43 / 8 / 1", "0.51–0.87 / 0.58–0.90 / 0.70–0.95", "0.71–0.87 / 0.76–0.90 / 0.85–0.95"],
    ["FL", "28", "7 / 20 / 1", "0.27–0.47 / 0.33–0.53 / 0.46–0.66", "0.46–0.69 / 0.53–0.75 / 0.65–0.84"],
    ["LA", "6", "2 / 4 / 0", "0.22 / 0.27 / 0.39", "0.63 / 0.69 / 0.79"],
    ["NC", "14", "4 / 10 / 0", "0.34–0.54 / 0.40–0.60 / 0.53–0.72", "0.75 / 0.80 / 0.88"],
    ["OH", "15", "5 / 10 / 0", "0.29 / 0.34 / 0.47", "0.70 / 0.75 / 0.84"],
    ["TN", "9", "1 / 8 / 0", "0.18 / 0.22 / 0.33", "0.57 / 0.64 / 0.75"],
    ["UT", "4", "0 / 4 / 0", "0.22 / 0.27 / 0.39", "—"],
]
S += [
    KeepTogether(
        [
            Paragraph("The House's 135 seats the model cannot see, by state", H2),
            Paragraph(
                "These redrawn seats have no transferred prior. Each takes its state's 2024 presidential lean plus an incumbency term, so every Republican-held seat in a state gets roughly the same number and every Democratic-held seat another. A range comes from the incumbency term (open seats and verified candidacies), not from anything known about the district. What this construction cannot see is a seat whose new territory favours the other party: the incumbency term credits the holder as if the lines had not moved, so a seat that changes hands because of a redraw is, by construction, one this tier will have called wrong (compare Texas, where the transfer puts three Democratic-held seats at or below even). No district map is shown: 2026 boundaries for eight of the nine redrawn states are not yet in the project's geography layer, and a map on last cycle's shapes would be exactly the error the register exists to prevent.",
                SMALL,
            ),
            table(fb, [0.5 * inch, 0.9 * inch, 1.2 * inch, 2.2 * inch, 2.2 * inch], font=7.8),
        ]
    ),
    Spacer(1, 8),
]

# ---------------- Page 3 ----------------
S += [
    Paragraph("Modelling Weaknesses", H1),
    Paragraph(
        "A prediction is only as honest as its list of known weaknesses. These are on the record before any vote is counted; a post-mortem that discovers them afterwards proves nothing.",
        P,
    ),
]
for b in [
    "<b>135 House seats have no prior on their 2026 boundaries.</b> They use their state's presidential lean (sigma 0.146 vs modelled 0.112). Expect visibly worse per-seat scores here.",
    "<b>In those 135 seats the error has a known direction: toward whoever holds the seat.</b> The fallback is the state lean plus an incumbency term for the current holder, so it assumes the territory still favours the party that won it in 2024.  A redraw breaks the assumption. Texas, with a real transfer, puts three Democratic-held seats at or below even (TX-09 0.47, TX-32 0.49, TX-35 0.55). The eight states without a transfer cannot show this: 21 Democratic-held seats in AL, FL, LA, NC, OH, TN are projected at 0.53–0.80 and 8 Republican-held seats in CA at 0.58+, whatever happened to their lines. Seats that change hands because of redrawn maps are where this model will have missed, for holders of both parties.",
    "<b>Renomination is assumed for 267 of 470 seats.</b> Candidacy was verified from official general-election ballots for 203 seats; 52 seats are recorded as not contested by the sitting member; the remainder assume the sitting member is on the ballot.",
    "<b>The national environment is unidentified.</b> Shrinkage is an assumption swept over, not an estimate; no historical calibration exists.",
    "<b>No race-level inputs.</b> District history, the national environment and incumbency only; no polls, candidate quality or fundraising enter the projection. A seat competitive for local reasons the model cannot see is projected as safe, which is more likely in seats held by the party the environment favours.",
    "<b>The correlated-error split</b> (45% national / 25% regional / 30% state) is asserted, not estimated from residuals. Chamber-level interval width depends on it.",
    "<b>Litigation is live</b> in AL, CA, FL, LA, MO, NC, TN, TX, UT. A late court order would invalidate the affected seats' boundaries.",
    "<b>Specials are a non-random sample</b> of seats with a non-general electorate; overperformance is an association with the environment, not a measurement of it, and the swing is measured against presidential baselines and applied to a House basis.",
]:
    S.append(Paragraph(b, BUL, bulletText="•"))
S += [Paragraph("How this will be graded by rules fixed on 2026-09-30, binding on both runs", H1)]
for b in [
    "<b>Certified returns only.</b> Not election-night calls, not unofficial counts. Runoffs and recounts are followed to their conclusion.",
    "<b>Every row is scored and reported.</b> Selecting the best-performing assumption afterwards is forbidden and would void the registration.",
    "<b>Per seat:</b> Brier and log score on win probability; calibration over the backtest's ten bins; MAE on two-party share; 90% and 95% interval coverage.",
    "<b>Per chamber:</b> absolute error on mean seats; whether the realised count fell inside the 90% interval; whether the directional claim held.",
    "<b>Split evaluation:</b> 262 model seats, 38 transferred seats and 135 fallback seats reported separately. A pooled number would hide which part of the chamber the model knows anything about.",
    "<b>Comparators fixed in advance:</b> naive persistence (every seat repeats its 2024 share); the state-lean fallback applied everywhere; the backtest's leave-one-cycle-out House MAE of 0.0787 as in-sample reference.",
    "<b>Pre-declared failure condition:</b> if the realised Democratic seat count falls outside the 90% interval under every row, the model's stated uncertainty was too narrow.",
]:
    S.append(Paragraph(b, BUL, bulletText="•"))
S += [Paragraph("The model's record on past elections (forward-only chronological evaluation)", H1)]
bt = [
    ["Office", "Cycles", "Model MAE", "Naive persistence MAE", "90% interval coverage"],
    ["US House", "15", "0.065", "0.080", "0.913"],
    ["US Senate (open-seat spec.)", "21", "0.064", "0.084", "0.944"],
    ["Presidential", "8", "0.047", "0.032", "0.887"],
]
S += [
    table(bt, [1.9 * inch, 0.7 * inch, 1.1 * inch, 1.6 * inch, 1.7 * inch]),
    Paragraph(
        "The presidential baseline does not beat persistence, which is why there is no presidential forecast here and never has been. Source: reports/refresh_2026-10-29/chronological_evaluation.json and senate_specification_gate.json.",
        TINY,
    ),
    Spacer(1, 10),
]

# ---------------- Page 4 ----------------
S += [Paragraph("Provenance", H1)]
prov = [
    ["Input", "Source", "Snapshot / vintage"],
    ["Certified federal returns 1976–2024", "MIT Election Data and Science Lab", "2026-09-30"],
    ["Demographics", "U.S. Census Bureau, ACS 5-year", "vintage 2023"],
    [
        "Geography",
        "Census TIGER/Line, Block Assignment Files; Texas Legislative Council precinct maps",
        "2022 blocks, 2023/2024 districts; TX PLANC2333",
    ],
    [
        "Candidate filings",
        "Federal Election Commission (aggregate use only)",
        "2026-09-15; refreshed 2026-10-21",
    ],
    [
        "Congressional plan register (RD-001)",
        "Official state and court records, verified row by row",
        "2026-09-30; litigation column researched 2026-10",
    ],
    [
        "Special elections",
        "Official state aggregates, per-row sourcing",
        "11 compiled; 8 used after same-party and double-count gating",
    ],
    ["Senate roster and caucuses", "Official roster", "47 D / 53 R, 100 seats reconciled"],
    [
        "Final run",
        "reports/refresh_2026-10-29/ · git ddc23f4",
        "frozen in reports/comparison_set_2026-11-03.json (2026-10-29)",
    ],
    [
        "Registered seal",
        "reports/preregistration_2026-11-03.json · git 9e4e512",
        "2026-09-30 · predictions SHA-256 4de09ecf…4100882",
    ],
]
S += [
    table(prov, [1.9 * inch, 2.8 * inch, 2.3 * inch], align_right_from=9, font=8.2),
    KeepTogether(
        [
            Paragraph("What this is not", H1),
            Paragraph(
                "Not a call on any race. Not a poll average since no polling enters the band; a Texas poll cross-check was run for information only and is scored beside, not blended in. Not a presidential forecast. Not a map-drawing exercise: redistricting is treated as an audit and record-keeping question, and no state is grouped by motive. No individual-level data appears anywhere; every figure is at state, district or race level.",
                P,
            ),
        ]
    ),
    Paragraph("Attribution", H1),
    Paragraph(
        "MIT Election Data and Science Lab — certified U.S. federal returns, 1976–2024 (electionlab.mit.edu). U.S. Census Bureau — American Community Survey 5-year estimates (vintage 2023); TIGER/Line Shapefiles; Block Assignment Files (public domain; cited because chain of custody matters). Federal Election Commission — candidate and committee filings; aggregate use only; contributor fields are never used for solicitation, list-building or targeting. Texas Legislative Council — public precinct geography.",
        SMALL,
    ),
    Paragraph("Nonpartisan statement", H1),
    Paragraph(
        "This project models probability and uncertainty, not a preferred outcome. Close races look close; no probability has been sharpened to carry a storyline. Unofficial results, calls, estimates and certified returns are labelled distinctly and never share a sentence without one. Historical returns are certified; everything else in this document is modelled and labelled as such.",
        P,
    ),
    Paragraph("What happens next", H1),
    Paragraph(
        "Official releases are captured from election night and labelled unofficial until the authorities certify them. The scorecard — both runs, every row, the split by seat source, and the fixed comparators — is published when enough of each chamber is certified to be evaluable, and not before.",
        P,
    ),
    Spacer(1, 10),
    Paragraph(
        "Alex Oswald · Savepoint Analytics · www.alexoswald.ca · Full methodology, code references and the six-post series on the model's design are published on the site.",
        SMALL,
    ),
]

doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("wrote", OUT)
