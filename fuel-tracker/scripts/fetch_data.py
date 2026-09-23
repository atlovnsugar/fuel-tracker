#!/usr/bin/env python3
"""Download EU fuel/gas data and write JSON into site/data. Run from the repo root."""
import io, json, pathlib, re, time, urllib.request
from datetime import datetime, timezone
import pandas as pd

OUT = pathlib.Path("site/data")
UA = {"User-Agent": "Mozilla/5.0 (fuel-tracker GitHub Action)"}
OIL_URL = ("https://energy.ec.europa.eu/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en"
           "?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx")
EU = "BE BG CZ DK DE EE IE EL ES FR HR IT CY LV LT LU HU MT NL AT PL PT RO SI SK FI SE".split()
NAMES = {n.lower(): c for c, n in zip(EU, ["Belgium", "Bulgaria", "Czechia", "Denmark", "Germany", "Estonia",
    "Ireland", "Greece", "Spain", "France", "Croatia", "Italy", "Cyprus", "Latvia", "Lithuania", "Luxembourg",
    "Hungary", "Malta", "Netherlands", "Austria", "Poland", "Portugal", "Romania", "Slovenia", "Slovakia",
    "Finland", "Sweden"])}
NAMES["czech republic"] = "CZ"
FUELS = [("heating", r"heating"), ("lpg", r"lpg"), ("petrol", r"super|95|petrol|gasoline"),
         ("diesel", r"automotive|automobile|diesel|gas oil")]


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:
            print(f"  attempt {i + 1} failed for {url[:80]}: {e}")
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"Download failed: {url}")


def country(v):
    s = str(v).strip()
    if len(s) == 2 and s.upper() in EU + ["GR"]:
        return "EL" if s.upper() == "GR" else s.upper()
    return NAMES.get(s.lower())


def parse_sheet(raw):
    hdr = next((i for i in range(min(20, len(raw)))
                if any(re.search(r"in force|^date", str(c).lower()) for c in raw.iloc[i])
                and any(re.search(r"super|95", str(c).lower()) for c in raw.iloc[i])), None)
    if hdr is None:
        return None
    cols = [str(c).strip().lower() for c in raw.iloc[hdr]]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = cols
    dcol = next(c for c in cols if re.search(r"in force|^date", c))
    ccol = next((c for c in cols if "countr" in c), None)
    if ccol is None:
        return None
    df["_d"] = pd.to_datetime(df[dcol], errors="coerce")
    df["_c"] = df[ccol].map(country)
    df = df.dropna(subset=["_d", "_c"])
    used, res = {dcol, ccol}, {}
    for key, pat in FUELS:
        col = next((c for c in cols if c not in used and re.search(pat, c)), None)
        if col is None:
            continue
        used.add(col)
        s = pd.to_numeric(df[col], errors="coerce")
        if s.median() > 10:  # bulletin publishes EUR per 1000 litres
            s = s / 1000
        res[key] = pd.DataFrame({"d": df["_d"], "c": df["_c"], "v": s}).dropna()
    return res


def oil():
    raw = pd.read_excel(io.BytesIO(get(OIL_URL)), sheet_name=None, header=None)
    print("Sheets:", {k: v.shape for k, v in raw.items()})
    res = None
    for name, df in raw.items():
        if re.search(r"net|without|excl|\bwo\b|no tax", name.lower()):
            continue
        res = parse_sheet(df)
        if res and "petrol" in res and "diesel" in res:
            print("Using sheet:", name, "fuels:", list(res))
            break
        res = None
    if not res:
        for name, df in raw.items():
            print("---", name); print(df.head(8).to_string())
        raise RuntimeError("Oil Bulletin layout not recognised (see sheet dump above)")
    dates = sorted(set().union(*[set(f["d"]) for f in res.values()]))
    countries = {}
    for key, f in res.items():
        p = f.pivot_table(index="d", columns="c", values="v", aggfunc="mean").reindex(dates)
        for c in p.columns:
            countries.setdefault(c, {})[key] = [None if pd.isna(x) else round(float(x), 4) for x in p[c]]
    if len(countries) < 20 or len(dates) < 300:
        raise RuntimeError(f"Parsed data looks incomplete: {len(countries)} countries, {len(dates)} dates")
    (OUT / "oil.json").write_text(json.dumps({
        "unit": "EUR/l, taxes included", "dates": [d.strftime("%Y-%m-%d") for d in dates],
        "countries": countries}, separators=(",", ":")))
    print(f"oil.json: {len(countries)} countries, {len(dates)} weeks, latest {dates[-1].date()}")


def gas():
    base = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_202?format=JSON&lang=EN&"
    j = None
    for q in ("currency=EUR&unit=KWH&tax=I_TAX", "currency=EUR"):
        try:
            j = json.loads(get(base + q, 2)); break
        except Exception as e:
            print("gas query failed:", q, e)
    if j is None:
        raise RuntimeError("Eurostat gas request failed")
    ids, size = j["id"], j["size"]
    cats = {d: [c for c, _ in sorted(j["dimension"][d]["category"]["index"].items(), key=lambda kv: kv[1])]
            for d in ids}
    pref = {"currency": "EUR", "unit": "KWH", "tax": "I_TAX", "nrg_cons": "GJ20-199"}
    pick = {d: (pref[d] if pref.get(d) in cats[d] else cats[d][0]) for d in ids if d not in ("geo", "time")}
    print("Gas dimensions used:", pick)
    out = {}
    for flat, v in j["value"].items():
        rem, pos = int(flat), {}
        for d, n in zip(reversed(ids), reversed(size)):
            pos[d] = rem % n; rem //= n
        code = {d: cats[d][pos[d]] for d in ids}
        if all(code[d] == c for d, c in pick.items()) and code["geo"] in EU:
            out.setdefault(code["geo"], {})[code["time"]] = round(v, 4)
    periods = sorted({t for s in out.values() for t in s})
    (OUT / "gas.json").write_text(json.dumps({
        "unit": f"EUR/{pick.get('unit', '?')}, households, all taxes", "band": pick.get("nrg_cons"),
        "periods": periods, "countries": {c: [s.get(t) for t in periods] for c, s in out.items()}},
        separators=(",", ":")))
    print(f"gas.json: {len(out)} countries, {len(periods)} periods")


def geo():
    base = "https://gisco-services.ec.europa.eu/distribution/v2/"
    for path, name, keep in [
        ("countries/geojson/CNTR_RG_20M_2020_4326.geojson", "eu.geojson", lambda p: p.get("CNTR_ID") in EU),
        ("nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_3.geojson", "cz.geojson",
         lambda p: str(p.get("NUTS_ID", "")).startswith("CZ"))]:
        feats = [f for f in json.loads(get(base + path))["features"] if keep(f["properties"])]
        if not feats:
            raise RuntimeError(f"No features kept from {path}")
        (OUT / name).write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
        print(f"{name}: {len(feats)} features")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    oil(); geo()
    try:
        gas()
    except Exception as e:  # gas is optional: the app shows a notice instead of failing the deploy
        print("WARNING: gas data unavailable:", e)
        (OUT / "gas.json").write_text('{"periods":[],"countries":{}}')
    (OUT / "meta.json").write_text(json.dumps({"built": datetime.now(timezone.utc).isoformat(timespec="minutes")}))
