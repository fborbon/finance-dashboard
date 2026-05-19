"""
Generate a self-contained static HTML dashboard from Bank1/2/3 dummy data.
Usage:  python generate_static.py
Output: static/index.html
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio

from data_loader import load_bank1, load_bank2, load_bank3
from predictor import predict_next_month

OUT = Path(__file__).parent / "static"
OUT.mkdir(exist_ok=True)

BANK_COLORS = {"Bank1": "#1f77b4", "Bank2": "#ff7f0e", "Bank3": "#9467bd"}
TRANSFER_CATS = {"own transfer", "transfer"}

PLOTLY_THEME = dict(
    paper_bgcolor="#13131f",
    plot_bgcolor="#13131f",
    font_color="#e8e8f0",
    xaxis=dict(gridcolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    yaxis=dict(gridcolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    legend=dict(bgcolor="#13131f"),
    margin=dict(l=10, r=10, t=30, b=10),
)


def dark(fig):
    fig.update_layout(**PLOTLY_THEME)
    return fig


def chart(fig, first=False) -> str:
    return pio.to_html(
        dark(fig),
        full_html=False,
        include_plotlyjs="cdn" if first else False,
        config={"displayModeBar": False},
    )


# ── Load data ─────────────────────────────────────────────────────────────────

print("Loading Bank1 / Bank2 / Bank3 …")
df = pd.concat([load_bank1(), load_bank2(), load_bank3()], ignore_index=True)
df["amount"]  = pd.to_numeric(df["amount"],  errors="coerce")
df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
df["date"]    = pd.to_datetime(df["date"]).dt.tz_localize(None)
df = df.sort_values("date").reset_index(drop=True)

filtered = df[~df["category"].isin(TRANSFER_CATS)].copy()
all_banks = sorted(df["bank"].unique())

# ── Overview charts ───────────────────────────────────────────────────────────

print("Building overview charts …")
plots = {}
is_first = True

# 1. Balance over time
bal = df.dropna(subset=["balance"]).copy()
bal["day"] = bal["date"].dt.normalize()
daily = (bal.groupby(["bank", "day"])["balance"].last()
           .reset_index().rename(columns={"day": "date"}))
fig = px.line(daily, x="date", y="balance", color="bank",
              color_discrete_map=BANK_COLORS, line_shape="hv",
              labels={"balance": "€", "date": ""}, title="Balance over time")
fig.update_layout(legend_title_text="")
plots["ov_balance"] = chart(fig, first=True)
is_first = False

# 2. Monthly net cash flow
monthly = (
    filtered.assign(month=filtered["date"].dt.to_period("M").dt.to_timestamp())
    .groupby(["bank", "month"])["amount"].sum().reset_index()
)
fig2 = px.bar(monthly, x="month", y="amount", color="bank",
              color_discrete_map=BANK_COLORS, barmode="group",
              labels={"amount": "€", "month": ""}, title="Monthly net cash flow")
fig2.add_hline(y=0, line_width=1, line_color="#7a7a9a")
fig2.update_layout(legend_title_text="")
plots["ov_monthly"] = chart(fig2)

# 3. Expenses by category & year
exp = filtered[filtered["amount"] < 0].copy()
exp["year"] = exp["date"].dt.year.astype(str)
by_cat = exp.groupby(["category", "year"])["amount"].sum().abs().reset_index()
fig3 = px.bar(by_cat, x="amount", y="category", color="year",
              orientation="h", height=500,
              labels={"amount": "€", "category": ""}, title="Expenses by category & year")
fig3.update_layout(barmode="stack", yaxis={"categoryorder": "total descending"})
plots["ov_expenses"] = chart(fig3)

# 4. Income by category & year
inc = filtered[filtered["amount"] > 0].copy()
inc["year"] = inc["date"].dt.year.astype(str)
by_cat2 = inc.groupby(["category", "year"])["amount"].sum().reset_index()
fig4 = px.bar(by_cat2, x="amount", y="category", color="year",
              orientation="h", height=400,
              labels={"amount": "€", "category": ""}, title="Income by category & year")
fig4.update_layout(barmode="stack", yaxis={"categoryorder": "total descending"})
plots["ov_income"] = chart(fig4)

# ── Per-bank charts ────────────────────────────────────────────────────────────

bank_plots = {}
for bank in all_banks:
    print(f"Building {bank} charts …")
    color = BANK_COLORS.get(bank, "#555")
    bdf = filtered[filtered["bank"] == bank].copy()

    # Balance
    b2 = bdf.dropna(subset=["balance"]).copy()
    b2["day"] = b2["date"].dt.normalize()
    d2 = b2.groupby("day")["balance"].last().reset_index().rename(columns={"day": "date"})
    f1 = px.line(d2, x="date", y="balance", line_shape="hv",
                 color_discrete_sequence=[color], labels={"balance": "€", "date": ""},
                 title="Balance over time")
    p_balance = chart(f1)

    # Expenses pie
    exp2 = bdf[bdf["amount"] < 0]
    if not exp2.empty:
        bc = exp2.groupby("category")["amount"].sum().abs().reset_index()
        f2 = px.pie(bc, values="amount", names="category", hole=0.35, height=380,
                    title="Expenses by category")
        f2.update_traces(textposition="inside", textinfo="percent+label")
        f2.update_layout(showlegend=False)
        p_pie = chart(f2)
    else:
        p_pie = "<p style='color:#7a7a9a'>No expenses.</p>"

    # Monthly cash flow
    mo = (bdf.assign(month=bdf["date"].dt.to_period("M").dt.to_timestamp())
            .groupby("month")["amount"].sum().reset_index())
    f3 = px.bar(mo, x="month", y="amount", color_discrete_sequence=[color],
                labels={"amount": "€", "month": ""}, title="Monthly cash flow")
    f3.add_hline(y=0, line_width=1, line_color="#7a7a9a")
    p_monthly = chart(f3)

    # Predictions
    preds = predict_next_month(df[df["bank"] == bank])
    next_month = (pd.Timestamp.now().to_period("M") + 1).to_timestamp().strftime("%B %Y")

    if preds["income"]:
        inc_df = (pd.DataFrame(preds["income"].items(), columns=["category", "amount"])
                  .sort_values("amount", ascending=True))
        f4 = px.bar(inc_df, x="amount", y="category", orientation="h",
                    color_discrete_sequence=["#2ca02c"],
                    labels={"amount": "€", "category": ""},
                    title=f"Predicted income — {next_month}")
        f4.update_layout(margin={"l": 0, "r": 0, "t": 40, "b": 0})
        p_pred_inc = chart(f4)
    else:
        p_pred_inc = "<p style='color:#7a7a9a'>Not enough history.</p>"

    if preds["expenses"]:
        exp_df = (pd.DataFrame(preds["expenses"].items(), columns=["category", "amount"])
                  .sort_values("amount", ascending=True))
        f5 = px.bar(exp_df, x="amount", y="category", orientation="h",
                    color_discrete_sequence=["#d62728"],
                    labels={"amount": "€", "category": ""},
                    title=f"Predicted expenses — {next_month}")
        f5.update_layout(margin={"l": 0, "r": 0, "t": 40, "b": 0})
        p_pred_exp = chart(f5)
    else:
        p_pred_exp = "<p style='color:#7a7a9a'>Not enough history.</p>"

    bank_plots[bank] = {
        "balance": p_balance, "pie": p_pie, "monthly": p_monthly,
        "pred_inc": p_pred_inc, "pred_exp": p_pred_exp,
    }

# ── Metrics ───────────────────────────────────────────────────────────────────

metrics = {}
for bank in all_banks:
    last = df[df["bank"] == bank].dropna(subset=["balance"]).sort_values("date")
    metrics[bank] = f"€{last['balance'].iloc[-1]:,.2f}" if not last.empty else "—"
total_in  = f"€{filtered[filtered['amount'] > 0]['amount'].sum():,.0f}"
total_out = f"€{abs(filtered[filtered['amount'] < 0]['amount'].sum()):,.0f}"

# ── HTML ──────────────────────────────────────────────────────────────────────

print("Writing static/index.html …")

# Build bank tab headers and panels
tab_headers = '<button class="tab-btn active" data-tab="overview">📊 Overview</button>\n'
for bank in all_banks:
    icon = {"Bank1": "🏦", "Bank2": "💰", "Bank3": "💳"}.get(bank, "🏦")
    tab_headers += f'<button class="tab-btn" data-tab="{bank}">{icon} {bank}</button>\n'

metric_html = ""
for bank in all_banks:
    metric_html += f'<div class="metric"><div class="metric-label">🏦 {bank}</div><div class="metric-value">{metrics[bank]}</div></div>\n'
metric_html += f'<div class="metric"><div class="metric-label">📥 Income</div><div class="metric-value">{total_in}</div></div>\n'
metric_html += f'<div class="metric"><div class="metric-label">📤 Expenses</div><div class="metric-value">{total_out}</div></div>\n'

overview_panel = f"""
<div id="tab-overview" class="tab-panel active">
  <div class="metrics">{metric_html}</div>
  <div class="grid-2">
    <div class="chart-box">{plots["ov_balance"]}</div>
    <div class="chart-box">{plots["ov_monthly"]}</div>
  </div>
  <div class="grid-2">
    <div class="chart-box">{plots["ov_expenses"]}</div>
    <div class="chart-box">{plots["ov_income"]}</div>
  </div>
</div>
"""

bank_panels = ""
for bank in all_banks:
    bp = bank_plots[bank]
    bank_panels += f"""
<div id="tab-{bank}" class="tab-panel">
  <div class="grid-2">
    <div class="chart-box">{bp["balance"]}</div>
    <div class="chart-box">{bp["pie"]}</div>
  </div>
  <div class="chart-box full">{bp["monthly"]}</div>
  <div class="section-label">Next month predictions</div>
  <div class="grid-2">
    <div class="chart-box">{bp["pred_inc"]}</div>
    <div class="chart-box">{bp["pred_exp"]}</div>
  </div>
</div>
"""

generated_on = pd.Timestamp.now().strftime("%Y-%m-%d")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Personal Finance Dashboard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --gold: #E1C340; --bg: #0c0c12; --card: #13131f;
      --border: #1e1e2e; --text: #e8e8f0; --muted: #7a7a9a;
    }}
    body {{ background: var(--bg); color: var(--text);
            font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}

    header {{ display: flex; align-items: center; gap: 14px;
              padding: 20px 40px; border-bottom: 1px solid var(--border); }}
    header a {{ color: var(--gold); text-decoration: none; font-size: .9rem; margin-left: auto;
                opacity: .8; }}
    header a:hover {{ opacity: 1; }}
    h1 {{ font-size: 1.2rem; font-weight: 700; color: var(--gold); }}
    .subtitle {{ font-size: .8rem; color: var(--muted); margin-top: 2px; }}

    .tabs {{ display: flex; gap: 6px; padding: 24px 40px 0; flex-wrap: wrap; }}
    .tab-btn {{ background: var(--card); border: 1px solid var(--border); color: var(--muted);
                padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: .9rem;
                transition: all .2s; }}
    .tab-btn:hover {{ border-color: var(--gold); color: var(--text); }}
    .tab-btn.active {{ border-color: var(--gold); color: var(--gold); background: rgba(225,195,64,.08); }}

    .tab-panel {{ display: none; padding: 28px 40px 48px; }}
    .tab-panel.active {{ display: block; }}

    .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
    .metric {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px;
               padding: 16px 24px; min-width: 150px; flex: 1; }}
    .metric-label {{ font-size: .8rem; color: var(--muted); margin-bottom: 6px; }}
    .metric-value {{ font-size: 1.4rem; font-weight: 700; color: var(--text); }}

    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
    @media (max-width: 900px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
    .chart-box {{ background: var(--card); border: 1px solid var(--border);
                  border-radius: 12px; padding: 16px; overflow: hidden; }}
    .chart-box.full {{ margin-bottom: 20px; }}

    .section-label {{ font-size: .85rem; font-weight: 600; letter-spacing: .08em;
                      text-transform: uppercase; color: var(--muted); margin: 8px 0 16px; }}

    footer {{ text-align: center; padding: 20px; color: var(--muted); font-size: .8rem;
              border-top: 1px solid var(--border); }}
    footer span {{ color: var(--gold); }}
  </style>
</head>
<body>

<header>
  <div>
    <h1>💳 Personal Finance Dashboard</h1>
    <div class="subtitle">Bank1 · Bank2 · Bank3 &nbsp;·&nbsp; Demo data &nbsp;·&nbsp; Generated {generated_on}</div>
  </div>
  <a href="/">← forwardforecasting.eu</a>
</header>

<nav class="tabs">
  {tab_headers}
</nav>

{overview_panel}
{bank_panels}

<footer>Built by <span>fborbon</span> · <span>Forward Forecasting</span> © 2026 · Demo data only</footer>

<script>
  document.querySelectorAll('.tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    }});
  }});
</script>

</body>
</html>"""

(OUT / "index.html").write_text(html, encoding="utf-8")
size_kb = (OUT / "index.html").stat().st_size / 1024
print(f"\nDone → static/index.html  ({size_kb:.0f} KB)")
