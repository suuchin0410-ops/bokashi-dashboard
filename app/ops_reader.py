"""bokashi OPSアプリ（Firebase: bokashi-ops-app）の在庫・仕入・原価データを読むモジュール（読み取り専用）

アプリ本体: ../../../../Projects/es/es-ops（es-ops のマルチテナント版。VITE_TENANT=bokashi でビルド）
            このフォルダの ops-app/ からシンボリックリンクで参照できる。
データ:     Firestore stores/store_bokashi/{items, sessions, entries, purchases, recipes, dailySales, locations}

原価率の計算は es-ops の src/lib/monthlyCost.ts と同じ定義:
  原価 = 期首在庫 + 当月仕入 − 期末在庫（期首・期末とも本棚卸しがある月だけ「確定」）
  原価率 = 原価 ÷ 売上（税抜, dailySales）
  期末在庫は月末（25日以降）の本棚卸し、無ければ翌月初（7日以前）の本棚卸し。
  揃わない月は 仕入 ÷ 売上 を「推定」とする。本棚卸し＝カウント40品目以上（bokashi のテナント設定）。

使い方:
  python ops_reader.py            # 在庫・仕入・原価率のサマリーを表示
  python ops_reader.py --json     # 同じ内容をJSONで出力（会議レポート用）
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from datetime import date

from pathlib import Path

import requests

PROJECT = "bokashi-ops-app"
STORE = "store_bokashi"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/stores/{STORE}"
FULL_STOCKTAKE_MIN_ITEMS = 40
APP_URL = "https://bokashi-ops-app.web.app"
SALES_DIR = Path(__file__).parent.parent / "data" / "sales"


# ============================================================
# Firestore REST
# ============================================================
def _token() -> str | None:
    """gcloud の Application Default Credentials があれば使う（無くても現行ルールでは読める）"""
    try:
        r = subprocess.run(["gcloud", "auth", "application-default", "print-access-token"],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


_TOKEN = None


def _headers() -> dict:
    global _TOKEN
    if _TOKEN is None:
        _TOKEN = _token() or ""
    return {"Authorization": f"Bearer {_TOKEN}", "x-goog-user-project": PROJECT} if _TOKEN else {}


def _val(v: dict):
    if "stringValue" in v: return v["stringValue"]
    if "integerValue" in v: return int(v["integerValue"])
    if "doubleValue" in v: return float(v["doubleValue"])
    if "booleanValue" in v: return v["booleanValue"]
    if "nullValue" in v: return None
    if "timestampValue" in v: return v["timestampValue"]
    if "arrayValue" in v: return [_val(x) for x in v["arrayValue"].get("values", [])]
    if "mapValue" in v: return {k: _val(x) for k, x in v["mapValue"].get("fields", {}).items()}
    return None


def fetch(collection: str) -> list[dict]:
    """コレクションの全ドキュメントを dict のリストで返す（id を含む）"""
    out, token = [], None
    while True:
        params = {"pageSize": 300}
        if token:
            params["pageToken"] = token
        r = requests.get(f"{BASE}/{collection}", headers=_headers(), params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        for d in js.get("documents", []):
            row = {k: _val(v) for k, v in d.get("fields", {}).items()}
            row.setdefault("id", d["name"].rsplit("/", 1)[-1])
            out.append(row)
        token = js.get("nextPageToken")
        if not token:
            return out


# ============================================================
# 集計
# ============================================================
def _is_deposit(item: dict | None) -> bool:
    return bool(item) and (item.get("isDeposit") or "保証金" in item.get("name", ""))


def load_all() -> dict:
    return {c: fetch(c) for c in ("items", "sessions", "entries", "purchases", "recipes", "dailySales")}


def local_daily_ex_tax() -> dict[str, float]:
    """data/sales の日別売上CSV（data_loader 経由）から {YYYY-MM-DD: 純売上(税抜)}。0円の日（休業・未来日）は除く"""
    import data_loader as dl
    df = dl.load_daily(SALES_DIR)
    df = df[df["純売上(税抜)"] > 0]
    return dict(zip(df["日付"].dt.strftime("%Y-%m-%d"), df["純売上(税抜)"].astype(float)))


def sales_gap(D: dict) -> list[dict]:
    """月別に ローカルCSV と OPS dailySales の税抜売上を突き合わせる（OPS側の取込漏れ・古さの検知用）"""
    ops, loc = defaultdict(float), defaultdict(float)
    for d in D["dailySales"]:
        ops[(d.get("date") or d["id"])[:7]] += float(d.get("revenueTaxExcl") or 0)
    for k, v in local_daily_ex_tax().items():
        loc[k[:7]] += v
    return [{"month": m, "local": round(loc[m]), "ops": round(ops[m]), "diff": round(ops[m] - loc[m])}
            for m in sorted(set(ops) | set(loc)) if round(ops[m]) != round(loc[m])]


def full_stocktakes(D: dict) -> list[dict]:
    """完了した本棚卸し（カウント40品目以上）を日付順に。各要素に value（在庫額）と entries を付与"""
    by_sess = defaultdict(list)
    for e in D["entries"]:
        by_sess[e.get("sessionId")].append(e)
    out = []
    for s in D["sessions"]:
        es = [e for e in by_sess[s["id"]] if e.get("countedQty") is not None]
        if s.get("status") != "completed" or len({e["itemId"] for e in es}) < FULL_STOCKTAKE_MIN_ITEMS:
            continue
        value = sum(float(e["countedQty"]) * float(e.get("unitCost") or 0) for e in es)
        out.append({**s, "value": round(value), "entries": es, "n_items": len({e["itemId"] for e in es})})
    return sorted(out, key=lambda s: s["sessionDate"])


def monthly_cost(D: dict) -> list[dict]:
    """月次の売上（税抜）・仕入・期首/期末在庫・原価・原価率。method: stocktake / estimate / none"""
    items = {i["id"]: i for i in D["items"]}
    purch = defaultdict(float)
    for p in D["purchases"]:
        if _is_deposit(items.get(p.get("itemId"))):
            continue
        purch[p["purchaseDate"][:7]] += float(p.get("quantity") or 0) * float(p.get("unitCost") or 0)
    # 売上（税抜）: 日単位で ローカルCSV（Drive同期・正）を優先し、無い日だけ OPS の dailySales で補う
    day = {(d.get("date") or d["id"]): float(d.get("revenueTaxExcl") or 0) for d in D["dailySales"]}
    day.update(local_daily_ex_tax())
    rev = defaultdict(float)
    for ymd, v in day.items():
        rev[ymd[:7]] += v

    # 月 → 期末在庫（25日以降の棚卸し優先、無ければ翌月7日以前）
    inv = {}
    for s in full_stocktakes(D):
        y, m, dd = (int(x) for x in s["sessionDate"][:10].split("-"))
        if dd >= 25:
            inv[f"{y}-{m:02d}"] = (s["value"], s["sessionDate"])
        elif dd <= 7:
            pm = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
            inv.setdefault(pm, (s["value"], s["sessionDate"]))

    rows = []
    for ym in sorted(set(rev) | set(purch)):
        y, m = (int(x) for x in ym.split("-"))
        pm = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
        r, p = rev.get(ym, 0), purch.get(ym, 0)
        if pm in inv and ym in inv:
            cogs = inv[pm][0] + p - inv[ym][0]; method = "stocktake"
        elif r and p:
            cogs = p; method = "estimate"
        else:
            cogs = 0; method = "none" if not r else "no_purchase"
        rows.append({"month": ym, "revenue": round(r), "purch": round(p),
                     "beginInv": inv.get(pm, (None,))[0], "inv": inv.get(ym, (None,))[0], "invDate": inv.get(ym, (None, None))[1],
                     "cogs": round(cogs), "cogsRate": round(cogs / r * 100, 1) if r and cogs else None, "method": method})
    return rows


def current_stock(D: dict) -> dict:
    """直近の本棚卸し＋それ以降の仕入 = 現在の推定在庫（消費は差し引けないので上限値）。発注点割れも返す"""
    st = full_stocktakes(D)
    if not st:
        return {"date": None, "value": 0, "items": [], "below_reorder": []}
    last = st[-1]
    items = {i["id"]: i for i in D["items"]}
    qty = defaultdict(float)
    for e in last["entries"]:
        qty[e["itemId"]] += float(e["countedQty"])
    after = defaultdict(float)
    for p in D["purchases"]:
        if p["purchaseDate"] > last["sessionDate"][:10]:
            after[p["itemId"]] += float(p.get("quantity") or 0)
    rows = []
    for iid in set(qty) | set(after):
        it = items.get(iid, {})
        if not it or it.get("isActive") is False or _is_deposit(it):
            continue
        q = qty[iid]
        rows.append({"id": iid, "name": it.get("name", iid), "category": it.get("category", ""), "unit": it.get("unit", ""),
                     "counted": q, "purchased_after": after[iid], "est_qty": q + after[iid],
                     "value": round((q + after[iid]) * float(it.get("costPrice") or 0)),
                     "reorderPoint": it.get("reorderPoint") or 0, "parLevel": it.get("parLevel") or 0})
    below = [r for r in rows if r["reorderPoint"] and r["est_qty"] <= r["reorderPoint"]]
    by_cat = defaultdict(int)
    for r in rows:
        by_cat[r["category"] or "未分類"] += r["value"]
    return {"date": last["sessionDate"], "value": last["value"], "n_items": last["n_items"],
            "items": sorted(rows, key=lambda r: -r["value"]), "by_category": dict(sorted(by_cat.items(), key=lambda x: -x[1])),
            "below_reorder": sorted(below, key=lambda r: r["name"])}


def recipe_costs(D: dict) -> list[dict]:
    """レシピの理論原価・原価率（売価は税抜）"""
    items = {i["id"]: i for i in D["items"]}
    out = []
    for r in D["recipes"]:
        cost = sum(float(g.get("quantity") or 0) * float(items.get(g.get("itemId"), {}).get("costPrice") or 0)
                   for g in r.get("ingredients", []))
        price = float(r.get("sellingPrice") or 0)
        out.append({"menu": r.get("menuName"), "category": r.get("category", ""), "price": price, "cost": round(cost),
                    "rate": round(cost / price * 100, 1) if price else None})
    return sorted(out, key=lambda x: -(x["rate"] or 0))


def summary() -> dict:
    D = load_all()
    return {"fetched_at": date.today().isoformat(), "app": APP_URL,
            "counts": {k: len(v) for k, v in D.items()},
            "stocktakes": [{"date": s["sessionDate"], "items": s["n_items"], "value": s["value"]} for s in full_stocktakes(D)],
            "monthly_cost": monthly_cost(D), "sales_gap": sales_gap(D), "stock": current_stock(D), "recipes": recipe_costs(D)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    S = summary()
    if a.json:
        print(json.dumps(S, ensure_ascii=False, indent=1, default=str)); return
    print(f"bokashi OPS（{S['app']}）取得: {S['fetched_at']}  件数: {S['counts']}")
    print("\n■ 本棚卸し"); [print(f"  {s['date']}  {s['items']}品目  在庫額 ¥{s['value']:,}") for s in S["stocktakes"]]
    print("\n■ 月次原価率（method: stocktake=確定 / estimate=仕入÷売上 / no_purchase=仕入記録なし）")
    for r in S["monthly_cost"]:
        rate = f"{r['cogsRate']}%" if r["cogsRate"] is not None else "—"
        print(f"  {r['month']}  売上(税抜) ¥{r['revenue']:,}  仕入 ¥{r['purch']:,}  原価率 {rate}  [{r['method']}]")
    for g in S["sales_gap"]:
        print(f"  ⚠️ {g['month']} 売上の不一致: ローカルCSV ¥{g['local']:,} / OPS ¥{g['ops']:,}（差 {g['diff']:+,}）")
    st = S["stock"]
    print(f"\n■ 在庫（{st['date']} の本棚卸し ¥{st['value']:,} ＋以降の仕入）")
    for c, v in list(st.get("by_category", {}).items())[:10]: print(f"  {c}: ¥{v:,}")
    print(f"  発注点以下: {len(st['below_reorder'])}品目 " + "、".join(r['name'] for r in st['below_reorder'][:15]))
    print(f"\n■ レシピ原価率（{len(S['recipes'])}件）")
    for r in S["recipes"][:15]:
        print(f"  {r['menu']}  売価¥{r['price']:,.0f}  原価¥{r['cost']:,}  {r['rate']}%")


if __name__ == "__main__":
    main()
