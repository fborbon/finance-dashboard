import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from data_loader import load_all
from predictor import predict_next_month

st.set_page_config(page_title="Panel Bancario", layout="wide", page_icon="💳")

# ── Hide Streamlit toolbar (3-dot menu) ───────────────────────────────────────

st.markdown(
    "<style>"
    "#MainMenu{display:none}"
    "[data-testid='stToolbar']{display:none}"
    ".ag-body-viewport::-webkit-scrollbar{width:10px}"
    ".ag-body-viewport::-webkit-scrollbar-track{background:transparent}"
    ".ag-body-viewport::-webkit-scrollbar-thumb{background:#888;border-radius:5px}"
    ".ag-body-viewport::-webkit-scrollbar-thumb:hover{background:#555}"
    "</style>",
    unsafe_allow_html=True,
)

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

# ── Translations ──────────────────────────────────────────────────────────────

_MONTHS_ES = ["enero","febrero","marzo","abril","mayo","junio",
               "julio","agosto","septiembre","octubre","noviembre","diciembre"]

TRANSLATIONS: dict[str, dict[str, str]] = {
    "es": {
        # page title
        "page_title": "💳 Panel Bancario",
        # sidebar
        "filters": "Filtros",
        "date_range": "Rango de fechas",
        "hide_transfers": "Ocultar transferencias entre cuentas propias",
        "language_btn": "🇬🇧 English",
        # top-level tabs
        "tab_overview": "📊 Resumen",
        "tab_categories": "⚙️ Categorías",
        "tab_settings": "🔒 Ajustes",
        # bank sub-tabs
        "subtab_movements": "📋 Movimientos",
        "subtab_charts": "📈 Gráficos",
        "subtab_upload": "📤 Subir",
        # movements table columns
        "col_date": "Fecha",
        "col_concept": "Concepto",
        "col_amount": "Importe (€)",
        "col_balance": "Saldo (€)",
        "col_category": "Categoría",
        # overview
        "metric_income": "📥 Ingresos",
        "metric_expenses": "📤 Gastos",
        "balance_over_time": "Balance a lo largo del tiempo",
        "monthly_net_flow": "Flujo de caja mensual neto",
        "expenses_by_cat_year": "Gastos por categoría y año",
        "income_by_cat_year": "Ingresos por categoría y año",
        # charts
        "balance_over_time_bank": "Balance a lo largo del tiempo",
        "expenses_by_cat": "Gastos por categoría",
        "no_expenses": "Sin gastos en este período.",
        "monthly_cash_flow": "Flujo de caja mensual",
        "next_month_preds": "Predicciones del próximo mes",
        "pred_caption": "Totales estimados para **{month}** · tendencia lineal sobre los últimos 24 meses · se excluyen categorías con menos de 2 meses de datos",
        "pred_income": "**Ingresos previstos por categoría**",
        "pred_expenses": "**Gastos previstos por categoría**",
        "no_income_history": "Historial insuficiente para predicciones de ingresos.",
        "no_expense_history": "Historial insuficiente para predicciones de gastos.",
        # upload
        "upload_not_configured": "La carga de archivos no está configurada para este banco.",
        "current_files": "**Archivos actuales en disco:**",
        "no_files": "Aún no hay archivos de datos.",
        "accepted_formats": "Formatos aceptados: **{exts}**  •  Las transacciones duplicadas (misma fecha / importe / saldo) se eliminan automáticamente.",
        "upload_label": "Subir exportación de {bank}",
        "upload_success": "Guardado **{name}** — recargando datos…",
        # categories
        "cat_subheader": "Categorías de gasto",
        "cat_caption": "Añade filas con el botón ＋ y elimina con el icono de papelera. Los cambios se guardan automáticamente.",
        "cat_col": "Categoría",
        "cat_col_name": "Nombre de categoría",
        "cat_saved": "Guardadas {n} categorías.",
        # settings
        "settings_pw_header": "Cambiar contraseña del panel",
        "new_pw": "Nueva contraseña",
        "confirm_pw": "Confirmar contraseña",
        "update_pw_btn": "Actualizar contraseña",
        "pw_empty": "La contraseña no puede estar vacía.",
        "pw_mismatch": "Las contraseñas no coinciden.",
        "pw_short": "La contraseña debe tener al menos 8 caracteres.",
        "pw_ok": "Contraseña actualizada correctamente.",
        "pw_err": "Error de htpasswd: {msg}",
        "pw_fail": "Error: {err}",
        "session_header": "Sesión",
        "logout_btn": "🚪 Cerrar sesión",
        # bulk category
        "apply_all_checkbox": "Aplicar a todos los movimientos similares",
        "apply_all_help": "Asigna la misma categoría a todos los movimientos cuyo concepto comience igual (primeros 20 caracteres).",
        "apply_all_toast": "Categoría aplicada a {n} movimiento(s) similares.",
        # add-category dialog (triggered from dropdown sentinel)
        "add_cat_sentinel": "➕  Añadir categoría",
        "add_cat_dialog_title": "Nueva categoría",
        "new_cat_placeholder": "Nombre de la categoría…",
        "add_cat_btn_ok": "Añadir",
        "cancel_btn": "Cancelar",
        "new_cat_added": "Categoría '{name}' añadida.",
    },
    "en": {
        "page_title": "💳 Bank Dashboard",
        "filters": "Filters",
        "date_range": "Date range",
        "hide_transfers": "Hide own inter-bank transfers",
        "language_btn": "🇪🇸 Español",
        "tab_overview": "📊 Overview",
        "tab_categories": "⚙️ Categories",
        "tab_settings": "🔒 Settings",
        "subtab_movements": "📋 Movements",
        "subtab_charts": "📈 Charts",
        "subtab_upload": "📤 Upload",
        "col_date": "Date",
        "col_concept": "Concept",
        "col_amount": "Amount (€)",
        "col_balance": "Balance (€)",
        "col_category": "Category",
        "metric_income": "📥 Income",
        "metric_expenses": "📤 Expenses",
        "balance_over_time": "Balance over time",
        "monthly_net_flow": "Monthly net cash flow",
        "expenses_by_cat_year": "Expenses by category & year",
        "income_by_cat_year": "Income by category & year",
        "balance_over_time_bank": "Balance over time",
        "expenses_by_cat": "Expenses by category",
        "no_expenses": "No expenses in this period.",
        "monthly_cash_flow": "Monthly cash flow",
        "next_month_preds": "Next month predictions",
        "pred_caption": "Estimated totals for **{month}** · linear trend over last 24 months · categories with < 2 months of data excluded",
        "pred_income": "**Predicted income by category**",
        "pred_expenses": "**Predicted expenses by category**",
        "no_income_history": "Not enough history for income predictions.",
        "no_expense_history": "Not enough history for expense predictions.",
        "upload_not_configured": "File upload not configured for this bank.",
        "current_files": "**Current files on disk:**",
        "no_files": "No data files found yet.",
        "accepted_formats": "Accepted formats: **{exts}**  •  Duplicate transactions (same date / amount / balance) are removed automatically.",
        "upload_label": "Upload {bank} export",
        "upload_success": "Saved **{name}** — reloading data…",
        "cat_subheader": "Expenditure categories",
        "cat_caption": "Add rows with the ＋ button, delete with the trash icon. Changes are saved automatically.",
        "cat_col": "Category",
        "cat_col_name": "Category name",
        "cat_saved": "Saved {n} categories.",
        "settings_pw_header": "Change dashboard password",
        "new_pw": "New password",
        "confirm_pw": "Confirm password",
        "update_pw_btn": "Update password",
        "pw_empty": "Password cannot be empty.",
        "pw_mismatch": "Passwords do not match.",
        "pw_short": "Password must be at least 8 characters.",
        "pw_ok": "Password updated successfully.",
        "pw_err": "htpasswd error: {msg}",
        "pw_fail": "Failed: {err}",
        "session_header": "Session",
        "logout_btn": "🚪 Log out",
        "apply_all_checkbox": "Apply to all similar movements",
        "apply_all_help": "Assigns the same category to every movement whose concept starts with the same characters (first 20).",
        "apply_all_toast": "Category applied to {n} similar movement(s).",
        "add_cat_sentinel": "➕  Add category",
        "add_cat_dialog_title": "New category",
        "new_cat_placeholder": "Category name…",
        "add_cat_btn_ok": "Add",
        "cancel_btn": "Cancel",
        "new_cat_added": "Category '{name}' added.",
    },
}


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("lang", "es")
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text


PREFIX_LEN = 20  # characters used to match "same kind" concepts

def _concept_prefix(concept: str) -> str:
    return str(concept).strip().lower()[:PREFIX_LEN]


def _next_month_label(lang: str) -> str:
    ts = (pd.Timestamp.now().to_period("M") + 1).to_timestamp()
    if lang == "es":
        return f"{_MONTHS_ES[ts.month - 1].capitalize()} {ts.year}"
    return ts.strftime("%B %Y")


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

if "lang" not in st.session_state:
    st.session_state.lang = "es"
if "categories" not in st.session_state:
    st.session_state.categories = load_categories()
if "overrides" not in st.session_state:
    st.session_state.overrides = load_overrides()

raw_df = get_raw_data()
df = apply_overrides(raw_df, st.session_state.overrides)
all_banks = sorted(df["bank"].unique())

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.header(t("filters"))
date_min = df["date"].min().date()
date_max = df["date"].max().date()
date_range = st.sidebar.date_input(t("date_range"), value=[date_min, date_max])
start_date = date_range[0] if len(date_range) > 0 else date_min
end_date = date_range[1] if len(date_range) > 1 else date_max
hide_transfers = st.sidebar.checkbox(t("hide_transfers"), value=False)

st.sidebar.divider()
if st.sidebar.button(t("language_btn"), use_container_width=True):
    st.session_state.lang = "en" if st.session_state.lang == "es" else "es"
    st.rerun()


def apply_filters(source: pd.DataFrame) -> pd.DataFrame:
    mask = (source["date"].dt.date >= start_date) & (source["date"].dt.date <= end_date)
    if hide_transfers:
        mask &= ~source["category"].isin(TRANSFER_CATS)
    return source[mask].copy()



# ── New-category dialog ───────────────────────────────────────────────────────

def _new_cat_dialog_body():
    bank        = st.session_state.get("_dialog_bank", "")
    pending_ids = st.session_state.get(f"_pending_new_cat_{bank}", [])
    concepts    = st.session_state.get(f"_pending_concepts_{bank}", [])
    apply_all   = st.session_state.get(f"_pending_apply_all_{bank}", False)

    with st.form("_new_cat_dlg"):
        new_name = st.text_input(
            "", placeholder=t("new_cat_placeholder"), label_visibility="collapsed"
        )
        col1, col2 = st.columns(2)
        with col1:
            add_ok = st.form_submit_button(
                t("add_cat_btn_ok"), type="primary", use_container_width=True
            )
        with col2:
            cancel = st.form_submit_button(t("cancel_btn"), use_container_width=True)

    if cancel:
        st.session_state.pop(f"_pending_new_cat_{bank}", None)
        st.session_state.pop(f"_pending_concepts_{bank}", None)
        st.session_state.pop(f"_pending_apply_all_{bank}", None)
        st.rerun()

    if add_ok and new_name.strip():
        _name = new_name.strip().lower()
        if _name not in [c.lower() for c in st.session_state.categories]:
            st.session_state.categories = sorted(st.session_state.categories + [_name])
            save_categories(st.session_state.categories)
        for tid in pending_ids:
            st.session_state.overrides[tid] = _name
        total_matched = 0
        if apply_all:
            for concept in concepts:
                prefix = _concept_prefix(concept)
                if prefix:
                    matches = df[df["concept"].str.strip().str.lower().str.startswith(prefix)]
                    for _, mrow in matches.iterrows():
                        st.session_state.overrides[mrow["tx_id"]] = _name
                    total_matched += len(matches)
        save_overrides(st.session_state.overrides)
        st.session_state.pop(f"_pending_new_cat_{bank}", None)
        st.session_state.pop(f"_pending_concepts_{bank}", None)
        st.session_state.pop(f"_pending_apply_all_{bank}", None)
        st.toast(t("new_cat_added", name=_name), icon="✅")
        if apply_all and total_matched > 0:
            st.toast(t("apply_all_toast", n=total_matched), icon="✅")
        st.rerun()


@st.dialog("Nueva categoría")
def _new_cat_dialog_es():
    _new_cat_dialog_body()


@st.dialog("New category")
def _new_cat_dialog_en():
    _new_cat_dialog_body()


# ── Bank subtab: movements table ──────────────────────────────────────────────

def render_movements(bank_df: pd.DataFrame, bank: str):
    SENTINEL = t("add_cat_sentinel")
    cats = st.session_state.categories

    apply_all = st.checkbox(
        t("apply_all_checkbox"),
        key=f"apply_all_{bank}",
        help=t("apply_all_help"),
        value=True,
    )

    display = bank_df[["date", "concept", "amount", "balance", "category", "tx_id"]].copy()
    display["date"] = display["date"].dt.strftime("%Y-%m-%d")
    display = display.reset_index(drop=True)

    edited = st.data_editor(
        display.drop(columns=["tx_id"]),
        column_config={
            "date":     st.column_config.TextColumn(t("col_date"),     disabled=True, width="small"),
            "concept":  st.column_config.TextColumn(t("col_concept"),  disabled=True, width="large"),
            "amount":   st.column_config.NumberColumn(t("col_amount"), disabled=True, format="%.2f", width="small"),
            "balance":  st.column_config.NumberColumn(t("col_balance"),disabled=True, format="%.2f", width="small"),
            "category": st.column_config.SelectboxColumn(
                t("col_category"), options=cats + [SENTINEL], required=True, width="medium"
            ),
        },
        hide_index=True,
        use_container_width=True,
        height=560,
        key=f"editor_{bank}",
    )

    # NaN-safe comparison (both sides filled so NaN==NaN doesn't create spurious changes)
    changed      = edited["category"].fillna("") != display["category"].fillna("")
    sentinel_sel = changed & (edited["category"] == SENTINEL)
    real_changes = changed & ~sentinel_sel

    if real_changes.any():
        total_matched = 0
        for idx in display.index[real_changes]:
            new_cat = edited.loc[idx, "category"]
            st.session_state.overrides[display.loc[idx, "tx_id"]] = new_cat
            if apply_all:
                prefix = _concept_prefix(display.loc[idx, "concept"])
                if prefix:
                    matches = df[df["concept"].str.strip().str.lower().str.startswith(prefix)]
                    for _, mrow in matches.iterrows():
                        st.session_state.overrides[mrow["tx_id"]] = new_cat
                    total_matched += len(matches)
        save_overrides(st.session_state.overrides)
        if apply_all and total_matched > 0:
            st.toast(t("apply_all_toast", n=total_matched), icon="✅")

    # Sentinel selected → open popup dialog to name the new category
    if sentinel_sel.any():
        st.session_state[f"_pending_new_cat_{bank}"] = [
            display.loc[idx, "tx_id"] for idx in display.index[sentinel_sel]
        ]
        st.session_state[f"_pending_concepts_{bank}"] = [
            display.loc[idx, "concept"] for idx in display.index[sentinel_sel]
        ]
        st.session_state[f"_pending_apply_all_{bank}"] = apply_all
        st.session_state["_dialog_bank"] = bank
        if st.session_state.get("lang", "es") == "es":
            _new_cat_dialog_es()
        else:
            _new_cat_dialog_en()
    elif st.session_state.get(f"_pending_new_cat_{bank}"):
        st.session_state.pop(f"_pending_new_cat_{bank}", None)


# ── Bank subtab: charts ───────────────────────────────────────────────────────

def render_charts(bank_df: pd.DataFrame, bank: str):
    color = BANK_COLORS.get(bank, "#555")

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader(t("balance_over_time_bank"))
        bal = bank_df.dropna(subset=["balance"]).copy()
        bal["day"] = bal["date"].dt.normalize()
        daily = bal.groupby("day")["balance"].last().reset_index().rename(columns={"day": "date"})
        fig = px.line(daily, x="date", y="balance", line_shape="hv",
                      color_discrete_sequence=[color], labels={"balance": "€", "date": ""})
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader(t("expenses_by_cat"))
        exp = bank_df[bank_df["amount"] < 0]
        if exp.empty:
            st.info(t("no_expenses"))
        else:
            by_cat = exp.groupby("category")["amount"].sum().abs().reset_index()
            fig2 = px.pie(by_cat, values="amount", names="category", hole=0.35, height=380)
            fig2.update_traces(textposition="inside", textinfo="percent+label")
            fig2.update_layout(showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

    st.subheader(t("monthly_cash_flow"))
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
    st.subheader(t("next_month_preds"))

    preds = predict_next_month(df[df["bank"] == bank])
    next_month = _next_month_label(st.session_state.lang)
    st.caption(t("pred_caption", month=next_month))

    col_pl, col_pr = st.columns(2)
    with col_pl:
        st.markdown(t("pred_income"))
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
            st.info(t("no_income_history"))

    with col_pr:
        st.markdown(t("pred_expenses"))
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
            st.info(t("no_expense_history"))


# ── Bank subtab: file upload ──────────────────────────────────────────────────

def render_upload(bank: str):
    bank_dir, accepted = BANK_DIRS.get(bank, (None, []))
    if bank_dir is None:
        st.info(t("upload_not_configured"))
        return

    existing = sorted(bank_dir.glob("*.*")) if bank_dir.exists() else []
    if existing:
        st.caption(t("current_files"))
        for f in existing:
            st.text(f"  {f.name}  ({f.stat().st_size / 1024:.1f} KB)")
    else:
        st.caption(t("no_files"))

    st.divider()
    ext_list = ", ".join(f".{e}" for e in accepted)
    st.caption(t("accepted_formats", exts=ext_list))

    uploaded = st.file_uploader(
        t("upload_label", bank=bank),
        type=accepted,
        key=f"upload_{bank}",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        bank_dir.mkdir(parents=True, exist_ok=True)
        dest = bank_dir / uploaded.name
        dest.write_bytes(uploaded.getbuffer())
        st.success(t("upload_success", name=uploaded.name))
        get_raw_data.clear()
        st.rerun()


# ── Overview charts ───────────────────────────────────────────────────────────

def render_overview():
    filtered = apply_filters(df)

    cols = st.columns(5)
    for i, bank in enumerate(all_banks):
        last = df[df["bank"] == bank].dropna(subset=["balance"]).sort_values("date")
        if not last.empty:
            cols[i].metric(f"🏦 {bank}", f"€{last['balance'].iloc[-1]:,.2f}")
    total_in  = filtered[filtered["amount"] > 0]["amount"].sum()
    total_out = filtered[filtered["amount"] < 0]["amount"].sum()
    cols[3].metric(t("metric_income"),   f"€{total_in:,.0f}")
    cols[4].metric(t("metric_expenses"), f"€{abs(total_out):,.0f}")

    st.divider()

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader(t("balance_over_time"))
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
        st.subheader(t("monthly_net_flow"))
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

    col_l2, col_r2 = st.columns(2)
    with col_l2:
        st.subheader(t("expenses_by_cat_year"))
        exp = filtered[filtered["amount"] < 0].copy()
        exp["year"] = exp["date"].dt.year.astype(str)
        by_cat = exp.groupby(["category", "year"])["amount"].sum().abs().reset_index()
        fig3 = px.bar(by_cat, x="amount", y="category", color="year",
                      orientation="h", height=600, labels={"amount": "€", "category": ""})
        fig3.update_layout(barmode="stack", yaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig3, use_container_width=True)

    with col_r2:
        st.subheader(t("income_by_cat_year"))
        inc = filtered[filtered["amount"] > 0].copy()
        inc["year"] = inc["date"].dt.year.astype(str)
        by_cat2 = inc.groupby(["category", "year"])["amount"].sum().reset_index()
        fig4 = px.bar(by_cat2, x="amount", y="category", color="year",
                      orientation="h", height=400, labels={"amount": "€", "category": ""})
        fig4.update_layout(barmode="stack", yaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig4, use_container_width=True)


# ── Categories manager ────────────────────────────────────────────────────────

def render_categories():
    st.subheader(t("cat_subheader"))
    st.caption(t("cat_caption"))

    cat_df = pd.DataFrame({t("cat_col"): st.session_state.categories})

    edited = st.data_editor(
        cat_df,
        num_rows="dynamic",
        column_config={t("cat_col"): st.column_config.TextColumn(t("cat_col_name"), required=True)},
        hide_index=True,
        use_container_width=True,
        height=520,
        key="categories_editor",
    )

    new_cats = [c for c in edited[t("cat_col")].dropna().tolist() if str(c).strip()]
    if sorted(new_cats) != sorted(st.session_state.categories):
        st.session_state.categories = sorted(new_cats)
        save_categories(new_cats)
        st.toast(t("cat_saved", n=len(new_cats)), icon="✅")
        st.rerun()


# ── Settings ──────────────────────────────────────────────────────────────────

def render_settings():
    st.subheader(t("settings_pw_header"))
    with st.form("change_pw", clear_on_submit=True):
        new_pw  = st.text_input(t("new_pw"),     type="password")
        conf_pw = st.text_input(t("confirm_pw"), type="password")
        submitted = st.form_submit_button(t("update_pw_btn"))

    if submitted:
        if not new_pw:
            st.error(t("pw_empty"))
        elif new_pw != conf_pw:
            st.error(t("pw_mismatch"))
        elif len(new_pw) < 8:
            st.error(t("pw_short"))
        else:
            try:
                result = subprocess.run(
                    ["/usr/bin/htpasswd", "-i", str(HTPASSWD_FILE), "admin"],
                    input=new_pw.encode(),
                    capture_output=True,
                )
                if result.returncode == 0:
                    st.success(t("pw_ok"))
                else:
                    st.error(t("pw_err", msg=result.stderr.decode().strip()))
            except Exception as e:
                st.error(t("pw_fail", err=e))

    st.divider()
    st.subheader(t("session_header"))
    st.link_button(t("logout_btn"), url="/logout", type="secondary")


# ── Scroll-position preservation for data editors ────────────────────────────
# Injected into parent.document.head so the code runs in the same JS realm as
# AG Grid — cross-realm Object.defineProperty on DOM nodes doesn't work.

_SCROLL_FIX_JS = """
(function () {
    var saved = 0, guard = false, tid = null;

    function findDesc(el) {
        var p = Object.getPrototypeOf(el);
        while (p) {
            var d = Object.getOwnPropertyDescriptor(p, 'scrollTop');
            if (d && d.set) return d;
            p = Object.getPrototypeOf(p);
        }
        return null;
    }

    function patch(vp) {
        if (vp._agFix) return;
        vp._agFix = true;
        var nd = findDesc(vp);
        if (!nd) return;
        Object.defineProperty(vp, 'scrollTop', {
            configurable: true,
            get: function () { return nd.get.call(this); },
            set: function (v) {
                nd.set.call(this, (guard && v < 10 && saved > 30) ? saved : v);
            }
        });
        var origScrollTo = vp.scrollTo;
        vp.scrollTo = function (x, y) {
            var top = (x && typeof x === 'object') ? x.top : y;
            if (guard && typeof top === 'number' && top < 10 && saved > 30) {
                origScrollTo.call(this, { top: saved, behavior: 'instant' });
            } else {
                origScrollTo.apply(this, arguments);
            }
        };
    }

    // Each Streamlit rerun may replace the viewport DOM node entirely.
    // Watch for newly added viewports and patch them immediately so the
    // setter intercept is in place before AG Grid resets scrollTop.
    new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
            var nodes = muts[i].addedNodes;
            for (var j = 0; j < nodes.length; j++) {
                var n = nodes[j];
                if (n.nodeType !== 1) continue;
                var vps = n.classList && n.classList.contains('ag-body-viewport')
                    ? [n]
                    : Array.from(n.querySelectorAll ? n.querySelectorAll('.ag-body-viewport') : []);
                for (var k = 0; k < vps.length; k++) {
                    patch(vps[k]);
                    // Also do a RAF-based restore in case the element was
                    // added at scrollTop=0 without any setter call to intercept.
                    if (guard && saved > 30) {
                        (function (vp) {
                            requestAnimationFrame(function () {
                                if (guard && saved > 30) vp.scrollTop = saved;
                            });
                        })(vps[k]);
                    }
                }
            }
        }
    }).observe(document, { childList: true, subtree: true });

    document.addEventListener('mousedown', function (e) {
        if (!e.target.closest) return;
        var root = e.target.closest('.ag-root-wrapper');
        if (!root) return;
        var vp = root.querySelector('.ag-body-viewport');
        if (!vp) return;
        saved = vp.scrollTop;
        patch(vp);
        guard = true;
        clearTimeout(tid);
        tid = setTimeout(function () { guard = false; }, 3000);
    }, true);
})();
"""

components.html(
    "<script>(function(){"
    "if(parent.window._agScrollFixInit)return;"
    "parent.window._agScrollFixInit=true;"
    "var s=parent.document.createElement('script');"
    f"s.textContent={json.dumps(_SCROLL_FIX_JS)};"
    "parent.document.head.appendChild(s);"
    "})();</script>",
    height=0,
)

# ── Layout ────────────────────────────────────────────────────────────────────

tab_labels = (
    [t("tab_overview")]
    + [f"🏦 {b}" for b in all_banks]
    + [t("tab_categories"), t("tab_settings")]
)
tabs = st.tabs(tab_labels)

with tabs[0]:
    st.title(t("page_title"))
    render_overview()

for i, bank in enumerate(all_banks):
    with tabs[i + 1]:
        st.title(f"🏦 {bank}")
        bank_df = (
            apply_filters(df[df["bank"] == bank])
            .sort_values(["date", "balance"], ascending=[False, True])
            .reset_index(drop=True)
        )
        sub_movements, sub_charts, sub_upload = st.tabs([
            t("subtab_movements"), t("subtab_charts"), t("subtab_upload"),
        ])
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
