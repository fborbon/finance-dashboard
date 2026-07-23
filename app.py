import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from data_loader import load_all


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
        "category_filter_label": "Categorías",
        "category_filter_help": "Desmarca categorías para excluirlas de tablas y gráficos.",
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
        "expenses_by_cat": "Movimientos por categoría",
        "no_expenses": "Sin gastos en este período.",
        "monthly_cash_flow": "Flujo de caja mensual",
        "hist_totals":   "Acumulado histórico por categoría",
        "hist_income":   "**Ingresos totales por categoría**",
        "hist_expenses": "**Gastos totales por categoría**",
        "no_income_data": "Sin ingresos en este período.",
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
        # bulk row assignment
        "bulk_apply_btn":   "Aplicar selección",
        "rows_selected":    "{n} fila(s) seleccionadas",
        "select_rows_hint": "☑ Selecciona filas · elige categoría · Aplicar o Guardar",
        "bulk_applied":     "'{cat}' aplicado a {n} fila(s)",
        "save_btn":         "Guardar",
        "refresh_btn":      "🔄 Actualizar tabla",
        "bulk_cat_label":   "Categoría para selección",
        "auto_classified":  "✅ {n} fila(s) categorizadas automáticamente.",
        "filter_all":       "(Todas las categorías)",
        "filter_concept_ph": "🔍 Buscar concepto…",
        "filter_cat_ph":     "Filtrar categoría…",
        "sort_by_label":     "Ordenar por",
        "sort_asc_help":     "Alternar orden ascendente/descendente",
    },
    "en": {
        "page_title": "💳 Bank Dashboard",
        "filters": "Filters",
        "date_range": "Date range",
        "hide_transfers": "Hide own inter-bank transfers",
        "category_filter_label": "Categories",
        "category_filter_help": "Uncheck categories to exclude them from tables and charts.",
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
        "hist_totals":   "Cumulative totals by category",
        "hist_income":   "**Total income by category**",
        "hist_expenses": "**Total expenses by category**",
        "no_income_data": "No income in this period.",
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
        # bulk row assignment
        "bulk_apply_btn":   "Apply selection",
        "rows_selected":    "{n} row(s) selected",
        "select_rows_hint": "☑ Select rows · pick category · Apply or Save",
        "bulk_applied":     "'{cat}' applied to {n} row(s)",
        "save_btn":         "Save",
        "refresh_btn":      "🔄 Refresh table",
        "bulk_cat_label":   "Category for selection",
        "auto_classified":  "✅ {n} row(s) auto-classified.",
        "filter_all":       "(All categories)",
        "filter_concept_ph": "🔍 Search concept…",
        "filter_cat_ph":     "Filter category…",
        "sort_by_label":     "Sort by",
        "sort_asc_help":     "Toggle ascending/descending order",
    },
}


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("lang", "es")
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text


PREFIX_LEN  = 20   # characters used to match "same kind" concepts
HISTORY_MAX = 10   # undo/redo depth

def _concept_prefix(concept: str) -> str:
    return str(concept).strip().lower()[:PREFIX_LEN]



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
    # Snapshot current file before overwriting so every save is individually recoverable
    if OVERRIDES_FILE.exists():
        import shutil, datetime
        bak_dir = BASE / "backups" / "overrides"
        bak_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H%M%S")
        shutil.copy2(OVERRIDES_FILE, bak_dir / f"category_overrides_{stamp}.json")
        # Keep only the 200 most recent per-save snapshots
        snaps = sorted((bak_dir).glob("category_overrides_*.json"), key=lambda p: p.name, reverse=True)
        for old in snaps[200:]:
            old.unlink()
    OVERRIDES_FILE.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _auto_classify_after_upload(bank: str) -> int:
    """Scan new tx_ids in `bank` and apply categories learned from existing overrides.

    Builds concept-prefix rules (lengths 5-30 chars) from every non-'other' override,
    discards any prefix that is ambiguous (maps to two different categories), then for
    each new tx_id tries the longest matching prefix. Returns the number of rows classified.
    """
    from data_loader import load_all as _load_all
    fresh = _load_all()
    overrides = st.session_state.overrides

    fresh = fresh.copy()
    fresh["_tid"] = fresh.apply(
        lambda r: tx_id(r["bank"], r["date"], r["concept"], r["amount"]), axis=1
    )

    # Build prefix → category from every known non-'other' override.
    # A prefix is discarded if it maps to more than one category (ambiguous).
    prefix_rules: dict = {}  # prefix → category | None (None = ambiguous)
    _tid_to_concept = fresh.set_index("_tid")["concept"].to_dict()
    for tid, cat in overrides.items():
        if cat == "other" or tid not in _tid_to_concept:
            continue
        concept = str(_tid_to_concept[tid]).strip().lower()
        for length in range(5, min(len(concept) + 1, 31)):
            p = concept[:length]
            if p not in prefix_rules:
                prefix_rules[p] = cat
            elif prefix_rules[p] != cat:
                prefix_rules[p] = None  # ambiguous
    prefix_rules = {p: c for p, c in prefix_rules.items() if c is not None}

    # Apply to unclassified rows in the uploaded bank only.
    new_overrides = {}
    for _, row in fresh[fresh["bank"] == bank].iterrows():
        tid = row["_tid"]
        if tid in overrides:
            continue
        concept = str(row["concept"]).strip().lower()
        best_cat = None
        for length in range(min(len(concept), 30), 4, -1):
            if concept[:length] in prefix_rules:
                best_cat = prefix_rules[concept[:length]]
                break
        if best_cat:
            new_overrides[tid] = best_cat

    if new_overrides:
        st.session_state.overrides.update(new_overrides)
        _push_history()
        save_overrides(st.session_state.overrides)

    return len(new_overrides)


def _push_history():
    """Snapshot current overrides before a mutation so undo can restore it."""
    st.session_state._ov_history.append(st.session_state.overrides.copy())
    if len(st.session_state._ov_history) > HISTORY_MAX:
        st.session_state._ov_history.pop(0)
    st.session_state._ov_redo.clear()


def tx_id(bank: str, date, concept: str, amount: float) -> str:
    s = f"{bank}|{pd.Timestamp(date).isoformat()}|{concept}|{amount}"
    return hashlib.md5(s.encode()).hexdigest()


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def get_raw_data() -> pd.DataFrame:
    df = load_all()
    # Pre-compute tx_id once so apply_overrides can use a fast map() instead of a loop.
    df["tx_id"] = df.apply(
        lambda r: tx_id(r["bank"], r["date"], r["concept"], r["amount"]), axis=1
    )
    return df


def apply_overrides(raw: pd.DataFrame, overrides: dict) -> pd.DataFrame:
    df = raw.copy()  # tx_id column is already present from get_raw_data()
    if overrides:
        df["category"] = df["tx_id"].map(overrides).fillna(df["category"])
    df["category"] = df["category"].fillna("other").replace("accommodation", "other")
    return df


# ── Session state init ────────────────────────────────────────────────────────

if "lang" not in st.session_state:
    st.session_state.lang = "es"
if "categories" not in st.session_state:
    st.session_state.categories = load_categories()
if "overrides" not in st.session_state:
    _raw_ov = load_overrides()
    _acc_tids = [_t for _t, _c in _raw_ov.items() if _c == "accommodation"]
    if _acc_tids:
        for _t in _acc_tids:
            _raw_ov[_t] = "other"
        save_overrides(_raw_ov)
    st.session_state.overrides = _raw_ov
if "_ov_history" not in st.session_state:
    st.session_state._ov_history = []
if "_ov_redo" not in st.session_state:
    st.session_state._ov_redo = []

raw_df = get_raw_data()
df = apply_overrides(raw_df, st.session_state.overrides)
all_banks = sorted(df["bank"].unique())


# ── Keep the user on their current bank tab across our internal st.rerun()s ────
# st.tabs() has no way to set the active tab from Python, and st.rerun() resets
# it to the first tab. We remember which bank tab triggered the rerun and click
# it back into place client-side once the tab bar has been rendered again.
def _mark_active_bank(bank: str):
    st.session_state["_restore_tab"] = f"🏦 {bank}"


def _restore_active_tab():
    label = st.session_state.pop("_restore_tab", None)
    if not label:
        return
    st.components.v1.html(f"""
        <script>
        (function() {{
            const target = {json.dumps(label)};
            function clickTab() {{
                const doc = window.parent.document;
                const buttons = doc.querySelectorAll('button[role="tab"]');
                for (const btn of buttons) {{
                    if (btn.innerText.trim() === target) {{
                        btn.click();
                        return true;
                    }}
                }}
                return false;
            }}
            if (!clickTab()) {{ setTimeout(clickTab, 100); }}
        }})();
        </script>
    """, height=0)

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.header(t("filters"))
start_date = df["date"].min().date()
end_date = df["date"].max().date()
hide_transfers = st.sidebar.checkbox(t("hide_transfers"), value=False)

st.session_state.setdefault("cat_filter_sidebar", st.session_state.categories.copy())
# Drop any categories from the saved selection that no longer exist.
st.session_state["cat_filter_sidebar"] = [
    c for c in st.session_state["cat_filter_sidebar"] if c in st.session_state.categories
]
active_categories = st.sidebar.multiselect(
    t("category_filter_label"),
    options=st.session_state.categories,
    key="cat_filter_sidebar",
    help=t("category_filter_help"),
)

st.sidebar.divider()
if st.sidebar.button(t("language_btn"), use_container_width=True):
    st.session_state.lang = "en" if st.session_state.lang == "es" else "es"
    st.rerun()

st.sidebar.divider()
_undo_n = len(st.session_state._ov_history)
_redo_n = len(st.session_state._ov_redo)
_ub, _rb = st.sidebar.columns(2)
with _ub:
    if st.button(
        f"↩ Undo" + (f" ({_undo_n})" if _undo_n else ""),
        disabled=(_undo_n == 0),
        use_container_width=True,
        key="global_undo",
    ):
        st.session_state._ov_redo.append(st.session_state.overrides.copy())
        st.session_state.overrides = st.session_state._ov_history.pop()
        save_overrides(st.session_state.overrides)
        for _b in all_banks:
            st.session_state.pop(f"editor_{_b}", None)
        st.rerun()
with _rb:
    if st.button(
        f"↪ Redo" + (f" ({_redo_n})" if _redo_n else ""),
        disabled=(_redo_n == 0),
        use_container_width=True,
        key="global_redo",
    ):
        st.session_state._ov_history.append(st.session_state.overrides.copy())
        st.session_state.overrides = st.session_state._ov_redo.pop()
        save_overrides(st.session_state.overrides)
        for _b in all_banks:
            st.session_state.pop(f"editor_{_b}", None)
        st.rerun()


def apply_filters(source: pd.DataFrame) -> pd.DataFrame:
    mask = (source["date"].dt.date >= start_date) & (source["date"].dt.date <= end_date)
    if hide_transfers:
        mask &= ~source["category"].isin(TRANSFER_CATS)
    mask &= source["category"].isin(active_categories)
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
        _mark_active_bank(bank)
        st.rerun()

    if add_ok and new_name.strip():
        _name = new_name.strip().lower()
        if _name not in [c.lower() for c in st.session_state.categories]:
            st.session_state.categories = sorted(st.session_state.categories + [_name])
            save_categories(st.session_state.categories)
        matched_tids = {tid: _name for tid in pending_ids}
        if apply_all:
            _bank_full = df[df["bank"] == bank]
            for concept in concepts:
                prefix = _concept_prefix(concept)
                if prefix:
                    matches = _bank_full[
                        _bank_full["concept"].str.strip().str.lower().str.startswith(prefix)
                    ]
                    for _, mrow in matches.iterrows():
                        matched_tids[mrow["tx_id"]] = _name
        for tid, cat in matched_tids.items():
            st.session_state.overrides[tid] = cat
        total_matched = len(matched_tids)
        _push_history()
        save_overrides(st.session_state.overrides)
        st.session_state.pop(f"_pending_new_cat_{bank}", None)
        st.session_state.pop(f"_pending_concepts_{bank}", None)
        st.session_state.pop(f"_pending_apply_all_{bank}", None)
        st.toast(t("new_cat_added", name=_name), icon="✅")
        if apply_all and total_matched > len(pending_ids):
            st.toast(t("apply_all_toast", n=total_matched), icon="✅")
        st.session_state.pop(f"editor_{bank}", None)
        _mark_active_bank(bank)
        st.rerun()


@st.dialog("Nueva categoría")
def _new_cat_dialog_es():
    _new_cat_dialog_body()


@st.dialog("New category")
def _new_cat_dialog_en():
    _new_cat_dialog_body()


# ── EXPERIMENTAL: Tabulator.js preview (read-only) ─────────────────────────────
# No maintained Streamlit<->Tabulator bridge exists on PyPI, so a real editable
# integration would require writing a full custom bidirectional component (the
# same category of effort/risk as streamlit-aggrid, which we just moved away
# from). This is a read-only proof of concept, loaded from CDN client-side via
# st.components.v1.html, purely to demonstrate the native in-header text-filter
# UX before committing to that engineering cost.
def _render_tabulator_poc(bank_df: pd.DataFrame, bank: str, cats: list):
    poc_df = bank_df[["date", "concept", "amount", "balance", "category"]].copy()
    poc_df["date"] = poc_df["date"].dt.strftime("%Y-%m-%d")
    poc_df["amount"] = poc_df["amount"].round(2)
    poc_df["balance"] = poc_df["balance"].round(2)
    poc_df["category"] = poc_df["category"].fillna("other").where(poc_df["category"].isin(cats), "other")
    rows_json = poc_df.to_json(orient="records")

    html = f"""
    <link href="https://unpkg.com/tabulator-tables@6.3.1/dist/css/tabulator_simple.min.css" rel="stylesheet">
    <script src="https://unpkg.com/tabulator-tables@6.3.1/dist/js/tabulator.min.js"></script>
    <div id="tab-poc-{bank}"></div>
    <script>
    new Tabulator("#tab-poc-{bank}", {{
        data: {rows_json},
        layout: "fitColumns",
        height: 480,
        placeholder: "No rows",
        columns: [
            {{title: "Fecha",     field: "date",     headerFilter: "input", headerFilterFunc: "like", width: 110}},
            {{title: "Concepto",  field: "concept",  headerFilter: "input", headerFilterFunc: "like"}},
            {{title: "Importe",   field: "amount",   headerFilter: "input", headerFilterFunc: "like", hozAlign: "right", width: 110}},
            {{title: "Saldo",     field: "balance",  hozAlign: "right", width: 110}},
            {{title: "Categoría", field: "category", headerFilter: "input", headerFilterFunc: "like", width: 150}},
        ],
    }});
    </script>
    """
    st.components.v1.html(html, height=520, scrolling=True)


# ── Bank subtab: movements table ──────────────────────────────────────────────

def render_movements(bank_df: pd.DataFrame, bank: str):
    SENTINEL = t("add_cat_sentinel")
    cats = st.session_state.categories
    _valid_cats = set(cats)

    with st.expander("🧪 Tabulator preview (experimental, read-only)"):
        st.caption(
            "Type directly into the column headers below to filter — that's Tabulator's "
            "native headerFilter feature. This preview is read-only; category edits here "
            "are not saved (a real integration needs a custom Streamlit component)."
        )
        _render_tabulator_poc(bank_df, bank, cats)

    # ── Controls ──────────────────────────────────────────────────────────────
    _ck_col, _btn_col = st.columns([4, 1])
    with _ck_col:
        apply_all = st.checkbox(
            t("apply_all_checkbox"),
            key=f"apply_all_{bank}",
            help=t("apply_all_help"),
            value=False,
        )
    with _btn_col:
        if st.button(t("refresh_btn"), key=f"refresh_btn_{bank}", use_container_width=True):
            st.session_state.pop(f"editor_{bank}", None)
            _mark_active_bank(bank)
            st.rerun()

    # ── Search / filter row — boxes aligned above their matching table column ──
    _col_date, _col_concept, _col_amount, _col_balance, _col_category = st.columns(
        [1, 2.5, 1, 1, 1.5]
    )
    with _col_concept:
        _q_concept = st.text_input(
            "concept_search", key=f"q_concept_{bank}",
            placeholder=t("filter_concept_ph"), label_visibility="collapsed",
        )
    with _col_category:
        _q_cats = st.multiselect(
            "cat_filter", options=cats, key=f"q_cats_{bank}",
            placeholder=t("filter_cat_ph"), label_visibility="collapsed",
        )

    # ── Build display ─────────────────────────────────────────────────────────
    display = bank_df[["date", "concept", "amount", "balance", "category", "tx_id"]].copy()
    display["date"]     = display["date"].dt.strftime("%Y-%m-%d")
    display["amount"]   = display["amount"].round(2)
    display["balance"]  = display["balance"].round(2)
    display["category"] = (
        display["category"]
        .fillna("other")
        .where(display["category"].isin(_valid_cats), "other")
    )
    display = display.reset_index(drop=True)

    # ── Apply search filters ──────────────────────────────────────────────────
    mask = pd.Series(True, index=display.index)
    if _q_concept:
        mask &= display["concept"].str.contains(_q_concept, case=False, na=False, regex=False)
    if _q_cats:
        mask &= display["category"].isin(_q_cats)

    display_view = display[mask].reset_index(drop=True)

    # Reset editor state when filter changes so row-index mapping stays valid
    _fsig = f"{_q_concept}|{'|'.join(sorted(_q_cats))}"
    if st.session_state.get(f"_fsig_{bank}") != _fsig:
        st.session_state[f"_fsig_{bank}"] = _fsig
        st.session_state.pop(f"editor_{bank}", None)

    # ── Data editor ───────────────────────────────────────────────────────────
    editor_input = display_view.drop(columns=["tx_id"]).copy()
    editor_input.insert(0, "selected", False)

    edited = st.data_editor(
        editor_input,
        column_config={
            "selected": st.column_config.CheckboxColumn("☑", default=False, width="small"),
            "date":     st.column_config.TextColumn(t("col_date"),      disabled=True, width="small"),
            "concept":  st.column_config.TextColumn(t("col_concept"),   disabled=True, width="large"),
            "amount":   st.column_config.NumberColumn(t("col_amount"),  disabled=True, format="%.2f", width="small"),
            "balance":  st.column_config.NumberColumn(t("col_balance"), disabled=True, format="%.2f", width="small"),
            "category": st.column_config.SelectboxColumn(
                t("col_category"), options=cats + [SENTINEL], required=True, width="medium"
            ),
        },
        hide_index=True,
        use_container_width=True,
        height=520,
        key=f"editor_{bank}",
    )

    # ── Bulk selection: apply one category to every checked row ────────────────
    n_selected = int(edited["selected"].sum())
    _bulk_col, _bulk_btn = st.columns([3, 1])
    with _bulk_col:
        bulk_cat = st.selectbox(
            t("bulk_cat_label"), options=cats, key=f"bulk_cat_{bank}",
            label_visibility="collapsed", placeholder=t("bulk_cat_label"),
        )
    with _bulk_btn:
        bulk_clicked = st.button(
            t("bulk_apply_btn"), key=f"bulk_apply_{bank}",
            use_container_width=True, disabled=n_selected == 0,
        )
    st.caption(t("rows_selected", n=n_selected))

    if bulk_clicked and n_selected > 0:
        sel_idx = edited.index[edited["selected"]]
        for idx in sel_idx:
            tid = display_view.loc[idx, "tx_id"]
            st.session_state.overrides[tid] = bulk_cat
        _push_history()
        save_overrides(st.session_state.overrides)
        st.toast(t("bulk_applied", cat=bulk_cat, n=len(sel_idx)), icon="✅")
        st.session_state.pop(f"editor_{bank}", None)
        _mark_active_bank(bank)
        st.rerun()

    # ── Detect and save changes ───────────────────────────────────────────────
    changed      = edited["category"] != display_view["category"]
    sentinel_sel = changed & (edited["category"] == SENTINEL)
    real_changes = changed & ~sentinel_sel

    if real_changes.any():
        _bank_full = df[df["bank"] == bank]
        pending = {}
        for idx in display_view.index[real_changes]:
            new_cat = edited.loc[idx, "category"]
            tid     = display_view.loc[idx, "tx_id"]
            pending[tid] = new_cat
            if apply_all:
                prefix = _concept_prefix(display_view.loc[idx, "concept"])
                if prefix:
                    matches = _bank_full[
                        _bank_full["concept"].str.strip().str.lower().str.startswith(prefix)
                    ]
                    for _, mrow in matches.iterrows():
                        pending[mrow["tx_id"]] = new_cat
        for tid, cat in pending.items():
            st.session_state.overrides[tid] = cat
        _push_history()
        save_overrides(st.session_state.overrides)
        n_direct = int(real_changes.sum())
        if apply_all and len(pending) > n_direct:
            st.toast(t("apply_all_toast", n=len(pending)), icon="✅")
        st.session_state.pop(f"editor_{bank}", None)
        _mark_active_bank(bank)
        st.rerun()

    if sentinel_sel.any():
        st.session_state[f"_pending_new_cat_{bank}"] = [
            display_view.loc[idx, "tx_id"] for idx in display_view.index[sentinel_sel]
        ]
        st.session_state[f"_pending_concepts_{bank}"] = [
            display_view.loc[idx, "concept"] for idx in display_view.index[sentinel_sel]
        ]
        st.session_state[f"_pending_apply_all_{bank}"] = apply_all
        st.session_state["_dialog_bank"] = bank
        st.session_state.pop(f"editor_{bank}", None)
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
    st.subheader(t("hist_totals"))

    col_pl, col_pr = st.columns(2)

    with col_pl:
        st.markdown(t("hist_income"))
        inc = bank_df[bank_df["amount"] > 0]
        if inc.empty:
            st.info(t("no_income_data"))
        else:
            inc_df = (
                inc.groupby("category")["amount"].sum()
                .reset_index()
                .sort_values("amount", ascending=True)
            )
            _hi = max(350, len(inc_df) * 35 + 60)
            fig_pi = px.bar(
                inc_df, x="amount", y="category", orientation="h",
                color_discrete_sequence=["#2ca02c"],
                labels={"amount": "€", "category": ""},
            )
            fig_pi.update_layout(height=_hi, margin={"l": 0, "r": 10, "t": 10, "b": 0})
            st.plotly_chart(fig_pi, use_container_width=True)

    with col_pr:
        st.markdown(t("hist_expenses"))
        exp_h = bank_df[bank_df["amount"] < 0]
        if exp_h.empty:
            st.info(t("no_expenses"))
        else:
            exp_df = (
                exp_h.groupby("category")["amount"].sum().abs()
                .reset_index()
                .sort_values("amount", ascending=True)
            )
            _he = max(350, len(exp_df) * 35 + 60)
            fig_pe = px.bar(
                exp_df, x="amount", y="category", orientation="h",
                color_discrete_sequence=["#d62728"],
                labels={"amount": "€", "category": ""},
            )
            fig_pe.update_layout(height=_he, margin={"l": 0, "r": 10, "t": 10, "b": 0})
            st.plotly_chart(fig_pe, use_container_width=True)


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
        get_raw_data.clear()
        n_auto = _auto_classify_after_upload(bank)
        st.success(t("upload_success", name=uploaded.name))
        if n_auto:
            st.toast(t("auto_classified", n=n_auto))
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
# ── Layout ────────────────────────────────────────────────────────────────────

tab_labels = (
    [t("tab_overview")]
    + [f"🏦 {b}" for b in all_banks]
    + [t("tab_categories"), t("tab_settings")]
)
tabs = st.tabs(tab_labels)
_restore_active_tab()

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
