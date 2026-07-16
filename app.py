import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import load_all
from predictor import predict_next_month

st.set_page_config(page_title="Bank Dashboard", layout="wide", page_icon="💳")

BASE = Path(__file__).parent
CATEGORIES_FILE = BASE / "categories.json"
OVERRIDES_FILE = BASE / "category_overrides.json"

BANK_COLORS = {
    "Bank1": "#1f77b4", "Bank2": "#ff7f0e", "Bank3": "#9467bd",
    "Rural": "#1f77b4", "Caixa": "#ff7f0e", "Revo": "#9467bd",
}
TRANSFER_CATS = {"own transfer", "transfer"}

HTPASSWD_FILE = Path("/etc/nginx/.htpasswd_banking")

BANK_DIRS = {
    "Bank1": (BASE / "Bank1", ["xlsx", "xls"]),
    "Bank2": (BASE / "Bank2", ["xlsx", "xls"]),
    "Bank3": (BASE / "Bank3", ["csv"]),
    "Rural": (BASE / "Rural", ["xlsx", "xls"]),
    "Caixa": (BASE / "Caixa", ["xlsx", "xls"]),
    "Revo":  (BASE / "Revo",  ["csv"]),
}

# ── Persistence helpers ───────────────────────────────────────────────────────

def load_categories() -> list[str]:
    if CATEGORIES_FILE.exists():
        return json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
    return ["otros"]


def save_categories(cats: list[str]):
    CATEGORIES_FILE.write_text(
        json.dumps(sorted(cats), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_overrides() -> dict:
    if OVERRIDES_FILE.exists():
        return json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    return {}


def save_overrides(overrides: dict):
    OVERRIDES_FILE.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def tx_id(bank: str, date, concept: str, amount: float) -> str:
    s = f"{bank}|{pd.Timestamp(date).isoformat()}|{concept}|{amount}"
    return hashlib.md5(s.encode()).hexdigest()


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def get_raw_data() -> pd.DataFrame:
    return load_all()


def apply_overrides(raw: pd.DataFrame, overrides: dict) -> pd.DataFrame:
    df = raw.copy()
    df["tx_id"] = df.apply(
        lambda r: tx_id(r["bank"], r["date"], r["concept"], r["amount"]), axis=1
    )
    for tid, cat in overrides.items():
        df.loc[df["tx_id"] == tid, "category"] = cat
    return df


# ── Session state init ────────────────────────────────────────────────────────

if "categories" not in st.session_state:
    st.session_state.categories = load_categories()
if "overrides" not in st.session_state:
    st.session_state.overrides = load_overrides()

raw_df = get_raw_data()
df = apply_overrides(raw_df, st.session_state.overrides)
all_banks = sorted(df["bank"].unique())

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.header("Filters")
date_min = df["date"].min().date()
date_max = df["date"].max().date()
date_range = st.sidebar.date_input("Date range", value=[date_min, date_max])
start_date = date_range[0] if len(date_range) > 0 else date_min
end_date = date_range[1] if len(date_range) > 1 else date_max
hide_transfers = st.sidebar.checkbox("Hide own inter-bank transfers", value=True)


def apply_filters(source: pd.DataFrame) -> pd.DataFrame:
    mask = (source["date"].dt.date >= start_date) & (source["date"].dt.date <= end_date)
    if hide_transfers:
        mask &= ~source["category"].isin(TRANSFER_CATS)
    return source[mask].copy()


# ── Bank subtab: movements table ──────────────────────────────────────────────

def render_movements(bank_df: pd.DataFrame, bank: str):
    cats = st.session_state.categories

    bank_dir, accepted = BANK_DIRS.get(bank, (None, []))
    if bank_dir is not None:
        with st.expander("📤 Upload bank export", expanded=False):
            ext_list = ", ".join(f".{e}" for e in accepted)
            st.caption(
                f"Accepted: **{ext_list}** · Duplicate rows (same date / amount / balance) "
                "are removed automatically when loading."
            )
            uploaded = st.file_uploader(
                f"Upload {bank} export",
                type=accepted,
                key=f"mv_upload_{bank}",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                bank_dir.mkdir(parents=True, exist_ok=True)
                dest = bank_dir / uploaded.name
                dest.write_bytes(uploaded.getbuffer())
                st.success(f"Saved **{uploaded.name}** — reloading data…")
                get_raw_data.clear()
                st.rerun()

    display = bank_df[["date", "concept", "amount", "balance", "category", "tx_id"]].copy()
    display["date"] = display["date"].dt.strftime("%Y-%m-%d")
    display = display.reset_index(drop=True)

    edited = st.data_editor(
        display.drop(columns=["tx_id"]),
        column_config={
            "date": st.column_config.TextColumn("Date", disabled=True, width="small"),
            "concept": st.column_config.TextColumn("Concept", disabled=True, width="large"),
            "amount": st.column_config.NumberColumn("Amount (€)", disabled=True, format="%.2f", width="small"),
            "balance": st.column_config.NumberColumn("Balance (€)", disabled=True, format="%.2f", width="small"),
            "category": st.column_config.SelectboxColumn(
                "Category", options=cats, required=True, width="medium"
            ),
        },
        hide_index=True,
        use_container_width=True,
        height=560,
        key=f"editor_{bank}",
    )

    changed = edited["category"] != display["category"]
    if changed.any():
        for idx in display.index[changed]:
            st.session_state.overrides[display.loc[idx, "tx_id"]] = edited.loc[idx, "category"]
        save_overrides(st.session_state.overrides)
        st.rerun()


# ── Bank subtab: charts ───────────────────────────────────────────────────────

def render_charts(bank_df: pd.DataFrame, bank: str):
    color = BANK_COLORS.get(bank, "#555")

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Balance over time")
        bal = bank_df.dropna(subset=["balance"]).copy()
        bal["day"] = bal["date"].dt.normalize()
        daily = bal.groupby("day")["balance"].last().reset_index().rename(columns={"day": "date"})
        fig = px.line(daily, x="date", y="balance", line_shape="hv",
                      color_discrete_sequence=[color], labels={"balance": "€", "date": ""})
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Expenses by category")
        exp = bank_df[bank_df["amount"] < 0]
        if exp.empty:
            st.info("No expenses in this period.")
        else:
            by_cat = exp.groupby("category")["amount"].sum().abs().reset_index()
            fig2 = px.pie(by_cat, values="amount", names="category", hole=0.35, height=380)
            fig2.update_traces(textposition="inside", textinfo="percent+label")
            fig2.update_layout(showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Monthly cash flow")
    monthly = (
        bank_df.assign(month=bank_df["date"].dt.to_period("M").dt.to_timestamp())
        .groupby("month")["amount"].sum()
        .reset_index()
    )
    fig3 = px.bar(monthly, x="month", y="amount",
                  color_discrete_sequence=[color], labels={"amount": "€", "month": ""})
    fig3.add_hline(y=0, line_width=1, line_color="gray")
    st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.subheader("Next month predictions")

    preds = predict_next_month(df[df["bank"] == bank])
    next_month = (pd.Timestamp.now().to_period("M") + 1).to_timestamp().strftime("%B %Y")
    st.caption(f"Estimated totals for **{next_month}** · linear trend over last 24 months · "
               "categories with < 2 months of data excluded")

    col_pl, col_pr = st.columns(2)
    with col_pl:
        st.markdown("**Predicted income by category**")
        if preds["income"]:
            inc_df = (
                pd.DataFrame(preds["income"].items(), columns=["category", "amount"])
                .sort_values("amount", ascending=True)
            )
            fig_pi = px.bar(
                inc_df, x="amount", y="category", orientation="h",
                color_discrete_sequence=["#2ca02c"],
                labels={"amount": "€", "category": ""},
            )
            fig_pi.update_layout(margin={"l": 0, "r": 0, "t": 10, "b": 0})
            st.plotly_chart(fig_pi, use_container_width=True)
        else:
            st.info("Not enough history for income predictions.")

    with col_pr:
        st.markdown("**Predicted expenses by category**")
        if preds["expenses"]:
            exp_df = (
                pd.DataFrame(preds["expenses"].items(), columns=["category", "amount"])
                .sort_values("amount", ascending=True)
            )
            fig_pe = px.bar(
                exp_df, x="amount", y="category", orientation="h",
                color_discrete_sequence=["#d62728"],
                labels={"amount": "€", "category": ""},
            )
            fig_pe.update_layout(margin={"l": 0, "r": 0, "t": 10, "b": 0})
            st.plotly_chart(fig_pe, use_container_width=True)
        else:
            st.info("Not enough history for expense predictions.")


# ── Bank subtab: file upload ──────────────────────────────────────────────────

def render_upload(bank: str):
    bank_dir, accepted = BANK_DIRS.get(bank, (None, []))
    if bank_dir is None:
        st.info("File upload not configured for this bank.")
        return

    existing = sorted(bank_dir.glob("*.*")) if bank_dir.exists() else []
    if existing:
        st.caption("**Current files on disk:**")
        for f in existing:
            st.text(f"  {f.name}  ({f.stat().st_size / 1024:.1f} KB)")
    else:
        st.caption("No data files found yet.")

    st.divider()
    ext_list = ", ".join(f".{e}" for e in accepted)
    st.caption(
        f"Accepted formats: **{ext_list}**  •  "
        "Duplicate transactions (same date / amount / description) are removed automatically."
    )

    uploaded = st.file_uploader(
        f"Upload {bank} export",
        type=accepted,
        key=f"upload_{bank}",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        bank_dir.mkdir(parents=True, exist_ok=True)
        dest = bank_dir / uploaded.name
        dest.write_bytes(uploaded.getbuffer())
        st.success(f"Saved **{uploaded.name}** — reloading data…")
        get_raw_data.clear()
        st.rerun()


# ── Overview charts ───────────────────────────────────────────────────────────

def render_overview():
    filtered = apply_filters(df)

    # Metrics
    cols = st.columns(5)
    for i, bank in enumerate(all_banks):
        last = df[df["bank"] == bank].dropna(subset=["balance"]).sort_values("date")
        if not last.empty:
            cols[i].metric(f"🏦 {bank}", f"€{last['balance'].iloc[-1]:,.2f}")
    total_in = filtered[filtered["amount"] > 0]["amount"].sum()
    total_out = filtered[filtered["amount"] < 0]["amount"].sum()
    cols[3].metric("📥 Income", f"€{total_in:,.0f}")
    cols[4].metric("📤 Expenses", f"€{abs(total_out):,.0f}")

    st.divider()

    # Balance over time + monthly flow
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Balance over time")
        bal = df[df["bank"].isin(all_banks)].dropna(subset=["balance"]).copy()
        bal["day"] = bal["date"].dt.normalize()
        daily = (
            bal.groupby(["bank", "day"])["balance"].last()
            .reset_index().rename(columns={"day": "date"})
        )
        fig = px.line(daily, x="date", y="balance", color="bank",
                      color_discrete_map=BANK_COLORS, line_shape="hv",
                      labels={"balance": "€", "date": ""})
        fig.update_layout(legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Monthly net cash flow")
        monthly = (
            filtered.assign(month=filtered["date"].dt.to_period("M").dt.to_timestamp())
            .groupby(["bank", "month"])["amount"].sum()
            .reset_index()
        )
        fig2 = px.bar(monthly, x="month", y="amount", color="bank",
                      color_discrete_map=BANK_COLORS, barmode="group",
                      labels={"amount": "€", "month": ""})
        fig2.add_hline(y=0, line_width=1, line_color="gray")
        fig2.update_layout(legend_title_text="")
        st.plotly_chart(fig2, use_container_width=True)

    # Expenses + income breakdowns
    col_l2, col_r2 = st.columns(2)
    with col_l2:
        st.subheader("Expenses by category & year")
        exp = filtered[filtered["amount"] < 0].copy()
        exp["year"] = exp["date"].dt.year.astype(str)
        by_cat = exp.groupby(["category", "year"])["amount"].sum().abs().reset_index()
        fig3 = px.bar(by_cat, x="amount", y="category", color="year",
                      orientation="h", height=600, labels={"amount": "€", "category": ""})
        fig3.update_layout(barmode="stack", yaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig3, use_container_width=True)

    with col_r2:
        st.subheader("Income by category & year")
        inc = filtered[filtered["amount"] > 0].copy()
        inc["year"] = inc["date"].dt.year.astype(str)
        by_cat2 = inc.groupby(["category", "year"])["amount"].sum().reset_index()
        fig4 = px.bar(by_cat2, x="amount", y="category", color="year",
                      orientation="h", height=400, labels={"amount": "€", "category": ""})
        fig4.update_layout(barmode="stack", yaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig4, use_container_width=True)


# ── Categories manager ────────────────────────────────────────────────────────

def render_categories():
    st.subheader("Expenditure categories")
    st.caption("Add rows with the ＋ button, delete with the trash icon. Changes are saved automatically.")

    cat_df = pd.DataFrame({"Category": st.session_state.categories})

    edited = st.data_editor(
        cat_df,
        num_rows="dynamic",
        column_config={"Category": st.column_config.TextColumn("Category name", required=True)},
        hide_index=True,
        use_container_width=True,
        height=520,
        key="categories_editor",
    )

    new_cats = [c for c in edited["Category"].dropna().tolist() if str(c).strip()]
    if sorted(new_cats) != sorted(st.session_state.categories):
        st.session_state.categories = sorted(new_cats)
        save_categories(new_cats)
        st.toast(f"Saved {len(new_cats)} categories.", icon="✅")
        st.rerun()


# ── Settings ─────────────────────────────────────────────────────────────────

def render_settings():
    st.subheader("Change dashboard password")
    with st.form("change_pw", clear_on_submit=True):
        new_pw  = st.text_input("New password",     type="password")
        conf_pw = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Update password")

    if submitted:
        if not new_pw:
            st.error("Password cannot be empty.")
        elif new_pw != conf_pw:
            st.error("Passwords do not match.")
        elif len(new_pw) < 8:
            st.error("Password must be at least 8 characters.")
        else:
            try:
                result = subprocess.run(
                    ["/usr/bin/htpasswd", "-i", str(HTPASSWD_FILE), "admin"],
                    input=new_pw.encode(),
                    capture_output=True,
                )
                if result.returncode == 0:
                    st.success("Password updated successfully.")
                else:
                    st.error(f"htpasswd error: {result.stderr.decode().strip()}")
            except Exception as e:
                st.error(f"Failed: {e}")


# ── Layout ────────────────────────────────────────────────────────────────────

tab_labels = ["📊 Overview"] + [f"🏦 {b}" for b in all_banks] + ["⚙️ Categories", "🔒 Settings"]
tabs = st.tabs(tab_labels)

with tabs[0]:
    st.title("💳 Bank Dashboard")
    render_overview()

for i, bank in enumerate(all_banks):
    with tabs[i + 1]:
        st.title(f"🏦 {bank}")
        bank_df = (
            apply_filters(df[df["bank"] == bank])
            .sort_values("date", ascending=False)
            .reset_index(drop=True)
        )
        sub_movements, sub_charts, sub_upload = st.tabs(["📋 Movements", "📈 Charts", "📤 Upload"])
        with sub_movements:
            render_movements(bank_df, bank)
        with sub_charts:
            render_charts(bank_df, bank)
        with sub_upload:
            render_upload(bank)

with tabs[-2]:
    render_categories()

with tabs[-1]:
    render_settings()
