import hashlib
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent

# ── Category rules ────────────────────────────────────────────────────────────
# (keywords, category)  — first match wins; keywords matched against lowercase concept

CATEGORIES = [
    # Supermarket
    (["city supermarket", "fresh market", "green grocers", "daily foods", "market plus",
      "intl supermarket", "international supermarket", "travel grocery",
      "mercadona", "carrefour", "leclerc", "lidl", "aldi", "eroski", "coviran",
      "tj-bm", "carniceria", "fruteria", "tj-dia ", "chuleteros", "carnicas",
      "frutimix", "tj-monop", "tj-mendi", "mas x menos"], "supermarket"),
    # Amazon
    (["amazon", "amzn", "prime video"], "amazon"),
    # Pharmacy
    (["pharmacy", "health plus pharmacy", "farmacia", "tj-fcia", "tj-carlos iii"], "pharmacy"),
    # Bakery
    (["morning bakery", "city patisserie", "the bread shop", "sweet corner",
      "panaderia", "panadero", "tahona", "granier", "ogipan", "manterola",
      "arkupe gozotegia", "quindianita", "delicias de jose", "pasteleria",
      "tj-etxe goxoan", "tj-sarl aita"], "bakery"),
    # Restaurant / café
    (["the bistro", "city burger", "local kitchen", "corner café", "the grill",
      "sakura", "airport bistro", "holiday restaurant", "beach café",
      "hosteleria", "heladeria", "restaurante", "restauracion", "udon",
      "mc donalds", "mcdonalds", "tagliatella", "asados labea", "meson",
      "tasca ", "la guillotina", "hostal ", "tj-zuasti", "sota de lezkairu",
      "k fecico", "kfc", "central park", "pops ", "brief atocha",
      "la huerta de chicha", "el faro de suances", "tj-calenda",
      "tj-glaces", "tj-arcasa", "tj-plk", "tj-garden", "tj-butchers"], "restaurant"),
    (["café", "cafe "], "restaurant"),
    (["bar "], "restaurant"),
    # Hotel
    (["city hotel", "grand suites", "the lodge", "seaside hotel", "airport hotel",
      "hotel iriguibel", "hotel arenas", "hotel venta", "hotel"], "hotel"),
    # Accommodation (non-hotel)
    (["airbnb", "booking.com"], "accommodation"),
    # Flight
    (["air connect", "euro airways", "budget airlines",
      "expedia", "vueling", "iberia", "ryanair", "evelop", "lufthansa", "airlines"], "flight"),
    # Taxi
    (["city taxi", "quickcab", "airport taxi", "taxi licencia", "taxi "], "taxi"),
    # DIY / home improvement
    (["buildright", "home depot", "tool store", "paint express",
      "leroy merlin", "brico depot", "ferreteria", "textil hogar",
      "berroa garden", "cerrajeria", "saltoki"], "diy"),
    # Sports
    (["sportzone", "gym central", "active life", "gesport", "sarriguren", "decathlon"], "sports"),
    # Fuel
    (["highway fuel", "city gas station", "express petrol", "motorway petrol",
      "olloki oil", "es lezkairu", "mutilva", "tj-e.s. zuasti", "cepsa",
      "petro", "gasolinera", "gasolina", "low cost repost", "aralar soto"], "fuel"),
    # Toll
    (["highway toll", "north motorway", "city bypass toll", "east toll road",
      "vasco aragonesa", "autopista", "interbiak", "peage", "bidegi"], "toll"),
    # Parking
    (["city parking", "central car park", "station parking", "mall car park",
      "parking", "aparcamiento", "ap. pl. castillo", "telpark"], "parking"),
    # Internet & mobile
    (["telecom mobile", "netconnect", "móvil ", "vodafone", "lowi", "mybox", "orange"], "internet & mobile"),
    # Utilities
    (["city electric", "water services", "gas supply", "rcbo.", "recibo unico",
      "energia xxi", "rcbo.energia"], "utilities"),
    # Rent paid
    (["property management", "monthly rent", "periodica 5056343378", "alquiler olloki"], "rent"),
    # Rental income received
    (["tenant monthly payment", "tenant payment", "maria josefa iriarte"], "rental income"),
    # Loan / mortgage
    (["bank loan payment", "préstamo4227846153", "hipoteca mendillori", "pres.32551789564",
      "santander consumer", "berlingo"], "loan"),
    # Investment
    (["interactive brokers", "revolut digital assets"], "investment"),
    # Dept. store
    (["the mall", "city department store", "tj-0246 eci", "el corte ingles", "corte ingles",
      "tj-ikea", "ikea", "herno", "mediacite"], "dept. store"),
    # ATM
    (["atm cash withdrawal", "cash withdrawal", "reint.cajero", "cajero", "tj-cajero"], "atm"),
    # Bizum
    (["bizum recibido", "bizum"], "bizum"),
    # PayPal
    (["paypal"], "paypal"),
    # Refund
    (["amazon refund", "store refund", "card refund"], "refund"),
    # Own inter-bank transfers (identified by account owner's name or explicit labels)
    (["transfer to bank2", "transfer to bank3", "transfer to bank1",
      "transfer from bank1", "transfer from bank2",
      "trf. fernando borbon", "trf. fernando adrian borbon",
      "to fernando borbon", "payment from bank account",
      "payment from fernando", "transferencia  fernando borbon",
      "gastosre  fernando borbon", "international transfer to fernando",
      "30080090-fernando", "transfer from bank account",
      "transfer to bank account"], "own transfer"),
    # Income / salary
    (["employer corp", "salary payment", "freelance income",
      "ing. cheque ajeno", "ingreso cajero", "apertura cta",
      "magotteaux", "tgss", "direccion provincial"], "income"),
    # Generic transfer
    (["transferencia", "trf. ", "transf. a su favor"], "transfer"),
    # Exchange
    (["exchange", "currency exchange"], "exchange"),
]


def _categorize(concept: str) -> str:
    c = str(concept).lower()
    for keywords, category in CATEGORIES:
        for kw in keywords:
            if kw in c:
                return category
    return "other"


# ── Deduplication helper ──────────────────────────────────────────────────────

def _dedup(df: pd.DataFrame) -> pd.DataFrame:
    # When balance is present it uniquely identifies a transaction in the account
    # (running total after each event), so the key is just bank+amount+balance —
    # no date. Omitting the date makes dedup robust to timestamp drift between
    # exports (timezone suffix, seconds rounding, Started vs Completed date, etc.).
    # Falls back to bank+date+amount+concept when balance is NaN.
    def _row_key(r):
        bal = r["balance"]
        if pd.notna(bal):
            return f"{r['bank']}|{r['amount']:.2f}|{bal:.2f}"
        return f"{r['bank']}|{pd.Timestamp(r['date']).isoformat()}|{r['amount']:.2f}|{str(r['concept'])}"

    ids = df.apply(lambda r: hashlib.md5(_row_key(r).encode()).hexdigest(), axis=1)
    return df[~ids.duplicated(keep="first")].reset_index(drop=True)


# ── Revolut CSV helper (shared by Bank3 and Revo) ────────────────────────────

def _load_revolut_csv(path: Path, bank_name: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "State" not in df.columns:
        return pd.DataFrame(columns=["date", "concept", "amount", "balance", "bank", "category"])
    df = df[df["State"] == "COMPLETED"].copy()
    df["date"]     = pd.to_datetime(df["Started Date"], errors="coerce")
    df["concept"]  = df["Description"].astype(str).str.strip()
    df["amount"]   = pd.to_numeric(df["Amount"],  errors="coerce")
    df["balance"]  = pd.to_numeric(df["Balance"], errors="coerce")
    df["bank"]     = bank_name
    df["category"] = df["concept"].apply(_categorize)
    df.loc[df["Type"] == "Topup",       "category"] = "own transfer"
    df.loc[df["Type"] == "ATM",         "category"] = "atm"
    df.loc[df["Type"] == "Card Refund", "category"] = "refund"
    df.loc[df["Type"] == "Exchange",    "category"] = "exchange"
    return df[["date", "concept", "amount", "balance", "bank", "category"]]


# ── Bank1 loader (xlsx per year) ──────────────────────────────────────────────

def _load_bank1_file(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    raw = pd.read_excel(path, sheet_name=xl.sheet_names[0])
    cols = list(raw.columns)

    date_col    = next(c for c in cols
                       if any(k in str(c).lower() for k in ("fecha", "date"))
                       and not any(k in str(c).lower() for k in ("valor", "value")))
    concept_col = next(c for c in cols
                       if str(c).lower() in
                       ("concepto", "descripcion", "descripción", "description", "concept"))
    amount_col  = next(c for c in cols
                       if any(k in str(c).lower() for k in ("importe", "amount")))
    balance_col = next(c for c in cols
                       if any(k in str(c).lower() for k in ("saldo", "balance")))

    df = raw[[date_col, concept_col, amount_col, balance_col]].copy()
    df.columns = ["date", "concept", "amount", "balance"]

    # 2020 file uses MM/DD/YYYY; new xls files have ISO dates; others DD/MM/YYYY
    if path.stem == "2020":
        df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y", errors="coerce")
    else:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

    df["bank"] = "Bank1"
    return df


def load_bank1() -> pd.DataFrame:
    dfs = [_load_bank1_file(p) for p in sorted(BASE.glob("Bank1/*.xls*"))]
    df = pd.concat(dfs, ignore_index=True)
    df["concept"] = df["concept"].astype(str).str.strip()
    df["category"] = df["concept"].apply(_categorize)
    return _dedup(df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True))


# ── Bank2 loader (multi-column xlsx/xls) ─────────────────────────────────────

def _load_bank2_file(path: Path) -> pd.DataFrame:
    raw_head = pd.read_excel(path, header=None, nrows=6)

    # Find header row by looking for date-column keyword
    header_row = None
    for i, row in raw_head.iterrows():
        vals = [str(v).lower() for v in row.tolist()]
        if any(any(k in v for k in ("operaci", "fecha", "operation", "operation date"))
               for v in vals):
            header_row = i
            break

    if header_row is not None:
        # 25-column layout
        raw = pd.read_excel(path, header=None)
        headers = raw.iloc[header_row].tolist()
        data = raw.iloc[header_row + 1:].copy()
        data.columns = headers
        data = data.dropna(how="all").reset_index(drop=True)

        date_col = next(
            (c for c in headers
             if isinstance(c, str)
             and any(k in c.lower() for k in ("f. operaci", "operaci", "operation date", "operation", "fecha"))),
            None
        )
        if date_col is None:
            raise ValueError(
                f"Cannot find date column in {path.name}. Headers found: {headers}"
            )
        income_col = next(
            (c for c in headers if isinstance(c, str)
             and any(k in c.lower() for k in ("ingreso", "income"))), None
        )
        expense_col = next(
            (c for c in headers if isinstance(c, str)
             and any(k in c.lower() for k in ("gasto", "expense"))), None
        )
        amount_col = next(
            (c for c in headers if isinstance(c, str)
             and any(k in c.lower() for k in ("importe", "cantidad", "amount"))), None
        )
        balance_col = next(
            (c for c in headers if isinstance(c, str)
             and any(k in c.lower() for k in ("saldo (+)", "balance (+)", "saldo", "balance"))),
            None
        )
        if balance_col is None:
            raise ValueError(
                f"Cannot find balance column in {path.name}. Headers found: {headers}"
            )
        comp1_col = next(
            (c for c in headers if isinstance(c, str)
             and any(k in c.lower() for k in ("complementario 1", "description 1", "movimiento"))), None
        )
        comp3_col = next(
            (c for c in headers if isinstance(c, str)
             and any(k in c.lower() for k in ("complementario 3", "description 3", "más datos", "mas datos", "details"))), None
        )

        data["date"] = pd.to_datetime(data[date_col], dayfirst=True, errors="coerce")

        if income_col and expense_col:
            inc = pd.to_numeric(data[income_col], errors="coerce").fillna(0)
            exp = pd.to_numeric(data[expense_col], errors="coerce").fillna(0)
            data["amount"] = inc - exp
        elif income_col or expense_col:
            data["amount"] = pd.to_numeric(data[income_col or expense_col], errors="coerce")
        elif amount_col:
            data["amount"] = pd.to_numeric(data[amount_col], errors="coerce")
        else:
            raise ValueError(
                f"Cannot find amount column in {path.name}. Headers found: {headers}"
            )

        data["balance"] = pd.to_numeric(data[balance_col], errors="coerce")

        def _concept(row):
            c1 = str(row[comp1_col]).strip() if comp1_col and pd.notna(row[comp1_col]) else ""
            c3 = str(row[comp3_col]).strip() if comp3_col and pd.notna(row[comp3_col]) else ""
            if c1.lower().startswith("fecha de operaci"):
                c1 = " ".join(c1.split()[4:]).strip()
            combined = c1 if c1 else c3
            if c3 and c3 not in combined:
                combined = f"{combined} {c3}".strip()
            return combined or "no description"

        data["concept"] = data.apply(_concept, axis=1)

    else:
        # Old 6-column layout
        data = pd.read_excel(path, header=None, skiprows=3)
        data.columns = ["date", "date_val", "concept", "details", "amount", "balance"]
        data["date"]    = pd.to_datetime(data["date"], errors="coerce")
        data["amount"]  = pd.to_numeric(data["amount"], errors="coerce")
        data["balance"] = pd.to_numeric(data["balance"], errors="coerce")
        data["concept"] = data.apply(
            lambda r: f"{r['concept']} {r['details']}".strip()
            if pd.notna(r["details"]) else str(r["concept"]), axis=1
        )

    return data[["date", "concept", "amount", "balance"]].copy()


def load_bank2() -> pd.DataFrame:
    paths = [p for p in (BASE / "Bank2").iterdir()
             if p.suffix.lower() in (".xls", ".xlsx")]
    dfs = [_load_bank2_file(p) for p in sorted(paths)]
    df = pd.concat(dfs, ignore_index=True)
    df["bank"] = "Bank2"
    df["concept"] = df["concept"].astype(str).str.strip()
    df["category"] = df["concept"].apply(_categorize)
    return _dedup(df.dropna(subset=["date", "amount"]).sort_values("date").reset_index(drop=True))


# ── Bank3 loader (csv — multiple files supported) ────────────────────────────

def load_bank3() -> pd.DataFrame:
    parts = [_load_revolut_csv(p, "Bank3")
             for p in sorted((BASE / "Bank3").glob("*.csv"))]
    df = pd.concat(parts, ignore_index=True)
    return _dedup(df.dropna(subset=["date", "amount"]).sort_values("date").reset_index(drop=True))


# ── Real bank loaders (Rural / Caixa / Revo) ─────────────────────────────────

def load_rural() -> pd.DataFrame:
    dfs = [_load_bank1_file(p) for p in sorted(BASE.glob("Rural/*.xls*"))]
    df = pd.concat(dfs, ignore_index=True)
    df["bank"] = "Rural"
    df["concept"] = df["concept"].astype(str).str.strip()
    df["category"] = df["concept"].apply(_categorize)
    return _dedup(df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True))


def load_caixa() -> pd.DataFrame:
    paths = [p for p in (BASE / "Caixa").iterdir()
             if p.suffix.lower() in (".xls", ".xlsx")]
    dfs = [_load_bank2_file(p) for p in sorted(paths)]
    df = pd.concat(dfs, ignore_index=True)
    df["bank"] = "Caixa"
    df["concept"] = df["concept"].astype(str).str.strip()
    df["category"] = df["concept"].apply(_categorize)
    return _dedup(df.dropna(subset=["date", "amount"]).sort_values("date").reset_index(drop=True))


def load_revo() -> pd.DataFrame:
    parts = [_load_revolut_csv(p, "Revo")
             for p in sorted((BASE / "Revo").glob("*.csv"))]
    df = pd.concat(parts, ignore_index=True)
    return _dedup(df.dropna(subset=["date", "amount"]).sort_values("date").reset_index(drop=True))


# ── Combined loader ───────────────────────────────────────────────────────────

def load_all() -> pd.DataFrame:
    parts: list[pd.DataFrame] = []

    # Per-year xlsx/xls — prefer Rural (real) over Bank1 (demo)
    if list(BASE.glob("Rural/*.xls*")):
        parts.append(load_rural())
    elif list(BASE.glob("Bank1/*.xls*")):
        parts.append(load_bank1())

    # Multi-year xlsx/xls — prefer Caixa (real) over Bank2 (demo)
    caixa_dir = BASE / "Caixa"
    caixa_files = ([p for p in caixa_dir.iterdir()
                    if p.suffix.lower() in (".xls", ".xlsx")]
                   if caixa_dir.exists() else [])
    bank2_dir = BASE / "Bank2"
    if caixa_files:
        parts.append(load_caixa())
    elif bank2_dir.exists() and [p for p in bank2_dir.iterdir()
                                  if p.suffix.lower() in (".xls", ".xlsx")]:
        parts.append(load_bank2())

    # CSV — prefer Revo (real) over Bank3 (demo)
    if list((BASE / "Revo").glob("*.csv")):
        parts.append(load_revo())
    elif list((BASE / "Bank3").glob("*.csv")):
        parts.append(load_bank3())

    df = pd.concat(parts, ignore_index=True)
    df["amount"]  = pd.to_numeric(df["amount"],  errors="coerce")
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    df["date"]    = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.sort_values("date").reset_index(drop=True)
