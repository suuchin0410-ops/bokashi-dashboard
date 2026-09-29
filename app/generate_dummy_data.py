"""スマレジCSV形式のダミー売上データを生成する（日別・商品別・部門別・客層別）"""
import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "sales"

DEPARTMENTS = [
    {"id": 8000006, "name": "ドリンク"},
    {"id": 8000015, "name": "スイーツ"},
    {"id": 8000019, "name": "ランチ"},
    {"id": 8000017, "name": "パンケーキ"},
    {"id": 8000018, "name": "テイクアウト"},
    {"id": 8000020, "name": "パンケーキ（セットドリンク）"},
    {"id": 8000021, "name": "ランチ（セットドリンク）"},
]

PRODUCTS = [
    {"code": 1, "name": "浅煎りコーヒー", "dept": "ドリンク", "price": 600, "cost": 90, "weight": 15},
    {"code": 5, "name": "カフェラテ", "dept": "ドリンク", "price": 600, "cost": 110, "weight": 12},
    {"code": 6, "name": "カフェラテ（ICE）", "dept": "ドリンク", "price": 600, "cost": 110, "weight": 10},
    {"code": 3, "name": "深煎りコーヒー", "dept": "ドリンク", "price": 600, "cost": 90, "weight": 8},
    {"code": 4, "name": "深煎りコーヒー（ICE）", "dept": "ドリンク", "price": 600, "cost": 90, "weight": 5},
    {"code": 2, "name": "浅煎りコーヒー (ICE)", "dept": "ドリンク", "price": 600, "cost": 90, "weight": 5},
    {"code": 7, "name": "穀物コーヒー", "dept": "ドリンク", "price": 600, "cost": 80, "weight": 4},
    {"code": 8, "name": "穀物ラテ", "dept": "ドリンク", "price": 600, "cost": 100, "weight": 5},
    {"code": 11, "name": "ブレンドハーブティー", "dept": "ドリンク", "price": 500, "cost": 60, "weight": 6},
    {"code": 10, "name": "ハーブソーダ", "dept": "ドリンク", "price": 800, "cost": 120, "weight": 4},
    {"code": 12, "name": "りんごのストレートジュース", "dept": "ドリンク", "price": 800, "cost": 200, "weight": 3},
    {"code": 20, "name": "バスクチーズ", "dept": "スイーツ", "price": 700, "cost": 210, "weight": 12},
    {"code": 21, "name": "タルトタタン", "dept": "スイーツ", "price": 750, "cost": 230, "weight": 8},
    {"code": 22, "name": "ティラミス", "dept": "スイーツ", "price": 700, "cost": 200, "weight": 7},
    {"code": 23, "name": "クラシックプリン", "dept": "スイーツ", "price": 600, "cost": 150, "weight": 6},
    {"code": 26, "name": "キャロットケーキ", "dept": "スイーツ", "price": 700, "cost": 190, "weight": 4},
    {"code": 29, "name": "オレンジケーキ", "dept": "スイーツ", "price": 700, "cost": 200, "weight": 3},
    {"code": 100, "name": "発酵スパイスカレー", "dept": "ランチ", "price": 1280, "cost": 385, "weight": 10},
    {"code": 35, "name": "スフレパンケーキ", "dept": "パンケーキ", "price": 1100, "cost": 280, "weight": 6},
    {"code": 30, "name": "プレーンパンケーキ", "dept": "パンケーキ", "price": 900, "cost": 220, "weight": 4},
    {"code": 31, "name": "フルーツパンケーキ", "dept": "パンケーキ", "price": 1200, "cost": 350, "weight": 3},
    {"code": 36, "name": "スフレパンケーキ（パフェ付）", "dept": "パンケーキ", "price": 1500, "cost": 400, "weight": 2},
    {"code": 28, "name": "フィナンシェ（プレーン×紅茶）", "dept": "テイクアウト", "price": 600, "cost": 180, "weight": 3},
]

TAX_RATE = 0.10


def _generate_month(year: int, month: int, seed: int = 42):
    rng = random.Random(seed + year * 100 + month)
    first = datetime(year, month, 1)
    if month == 12:
        last = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = datetime(year, month + 1, 1) - timedelta(days=1)

    days_in_month = (last - first).days + 1

    daily_rows = []
    product_totals = {}
    dept_totals = {}
    total_new_customers = 0
    total_repeat_customers = 0
    total_new_sales = 0
    total_repeat_sales = 0
    total_new_items = 0
    total_repeat_items = 0

    weights = [p["weight"] for p in PRODUCTS]

    for day_offset in range(days_in_month):
        date = first + timedelta(days=day_offset)
        weekday = date.weekday()

        if rng.random() < 0.08:
            continue

        if weekday in (5, 6):
            customer_count = rng.randint(22, 40)
        elif weekday == 4:
            customer_count = rng.randint(18, 32)
        else:
            customer_count = rng.randint(12, 25)

        day_sales = 0
        day_sales_notax = 0
        day_tax = 0
        day_gross = 0
        day_cost = 0
        day_items = 0
        day_returns = 0
        day_discount = 0
        day_transactions = rng.randint(max(1, customer_count - 5), customer_count)

        repeat_count = int(customer_count * rng.uniform(0.15, 0.30))
        new_count = customer_count - repeat_count

        for _ in range(customer_count):
            num_items = rng.choices([1, 2, 3], weights=[25, 50, 25])[0]
            ordered = rng.choices(PRODUCTS, weights=weights, k=num_items)

            for item in ordered:
                price = item["price"]
                cost = item["cost"]
                notax = math.floor(price / (1 + TAX_RATE))
                tax = price - notax

                day_sales += price
                day_sales_notax += notax
                day_tax += tax
                day_cost += cost
                day_items += 1

                key = (item["code"], item["name"], item["dept"])
                if key not in product_totals:
                    product_totals[key] = {"sales": 0, "notax": 0, "tax": 0, "cost": 0, "qty": 0, "returns": 0}
                product_totals[key]["sales"] += price
                product_totals[key]["notax"] += notax
                product_totals[key]["tax"] += tax
                product_totals[key]["cost"] += cost
                product_totals[key]["qty"] += 1

                dname = item["dept"]
                if dname not in dept_totals:
                    dept_totals[dname] = {"sales": 0, "notax": 0, "tax": 0, "cost": 0, "qty": 0, "returns": 0}
                dept_totals[dname]["sales"] += price
                dept_totals[dname]["notax"] += notax
                dept_totals[dname]["tax"] += tax
                dept_totals[dname]["cost"] += cost
                dept_totals[dname]["qty"] += 1

        if rng.random() < 0.3:
            day_discount = rng.choice([200, 300, 500, 600, 900])

        day_gross = day_sales + day_discount
        day_profit = day_sales - day_cost
        day_avg_tx = round(day_sales / day_transactions) if day_transactions > 0 else 0
        day_avg_cust = round(day_sales / customer_count) if customer_count > 0 else 0

        daily_rows.append({
            "日付": date.strftime("%Y/%m/%d"),
            "純売上": day_sales,
            "純売上(税抜)": day_sales_notax,
            "消費税": day_tax,
            "免税額": 0,
            "総売上": day_gross,
            "値引き": day_discount,
            "ポイント利用": 0,
            "外税受領": 0,
            "売上対象外": 0,
            "送料": 0,
            "手数料": 0,
            "原価": day_cost,
            "粗利": day_profit,
            "販売点数": day_items,
            "返品数": day_returns,
            "取引数": day_transactions,
            "取引単価": day_avg_tx,
            "客数": customer_count,
            "客単価": day_avg_cust,
            "予算設定金額": 0,
            "予算達成率": "0.0",
            "クーポン利用": 0,
        })

        new_items_day = int(day_items * new_count / customer_count)
        repeat_items_day = day_items - new_items_day
        new_sales_day = int(day_sales * new_count / customer_count)
        repeat_sales_day = day_sales - new_sales_day
        total_new_customers += new_count
        total_repeat_customers += repeat_count
        total_new_sales += new_sales_day
        total_repeat_sales += repeat_sales_day
        total_new_items += new_items_day
        total_repeat_items += repeat_items_day

    total_all_sales = total_new_sales + total_repeat_sales

    customer_rows = []
    for cid, label, sales, qty, count in [
        (12, "新規", total_new_sales, total_new_items, total_new_customers),
        (11, "リピーター", total_repeat_sales, total_repeat_items, total_repeat_customers),
    ]:
        notax = math.floor(sales / (1 + TAX_RATE))
        tax = sales - notax
        ratio = round(sales / total_all_sales * 100, 2) if total_all_sales > 0 else 0
        qty_total = total_new_items + total_repeat_items
        qty_ratio = round(qty / qty_total * 100, 2) if qty_total > 0 else 0
        avg = round(sales / count) if count > 0 else 0
        customer_rows.append({
            "客層ID": cid, "ラベル": label,
            "純売上": sales, "純売上(税抜)": notax, "消費税": tax,
            "純売上構成比": ratio, "販売点数": qty, "返品数": 0,
            "販売点数構成比": qty_ratio, "客数": count, "客単価": avg,
        })

    product_rows = []
    for (code, name, dept), v in sorted(product_totals.items(), key=lambda x: -x[1]["sales"]):
        total_p_sales = sum(vv["sales"] for vv in product_totals.values())
        total_p_qty = sum(vv["qty"] for vv in product_totals.values())
        ratio = round(v["sales"] / total_p_sales * 100, 2) if total_p_sales > 0 else 0
        qty_ratio = round(v["qty"] / total_p_qty * 100, 2) if total_p_qty > 0 else 0
        product_rows.append({
            "商品コード": code, "商品名": name, "部門名": dept,
            "純売上": v["sales"], "純売上(税抜)": v["notax"], "消費税": v["tax"],
            "原価": v["cost"], "純売上構成比": ratio,
            "販売点数": v["qty"], "返品数": v["returns"],
            "販売点数構成比": qty_ratio,
            "在庫数": "", "品番": "", "カラー": "", "サイズ": "", "グループコード": "",
        })

    dept_map = {d["name"]: d["id"] for d in DEPARTMENTS}
    dept_rows = []
    for dname, v in sorted(dept_totals.items(), key=lambda x: -x[1]["sales"]):
        total_d_sales = sum(vv["sales"] for vv in dept_totals.values())
        total_d_qty = sum(vv["qty"] for vv in dept_totals.values())
        ratio = round(v["sales"] / total_d_sales * 100, 2) if total_d_sales > 0 else 0
        qty_ratio = round(v["qty"] / total_d_qty * 100, 2) if total_d_qty > 0 else 0
        dept_rows.append({
            "部門ID": dept_map.get(dname, ""), "部門コード": "", "部門名": dname,
            "純売上": v["sales"], "純売上(税抜)": v["notax"], "消費税": v["tax"],
            "原価": v["cost"], "純売上構成比": ratio,
            "販売点数": v["qty"], "返品数": v["returns"], "販売点数構成比": qty_ratio,
        })

    return daily_rows, product_rows, dept_rows, customer_rows


def _write_csv(rows: list[dict], path: Path):
    if not rows:
        return
    with open(path, "w", newline="", encoding="shift_jis") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    year, month = 2026, 4
    for m in range(month, month + 2):
        tag = f"{year}_{m:02d}"
        daily, product, dept, customer = _generate_month(year, m)
        _write_csv(daily, OUTPUT_DIR / f"daily_{tag}.csv")
        _write_csv(product, OUTPUT_DIR / f"product_{tag}.csv")
        _write_csv(dept, OUTPUT_DIR / f"department_{tag}.csv")
        _write_csv(customer, OUTPUT_DIR / f"customer_{tag}.csv")
        total = sum(r["純売上"] for r in daily)
        print(f"{tag}: daily={len(daily)}日, 純売上=¥{total:,.0f}, 商品={len(product)}種, 部門={len(dept)}, 客層={len(customer)}")

    print("生成完了")


if __name__ == "__main__":
    main()
