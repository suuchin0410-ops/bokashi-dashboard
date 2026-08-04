"""スマレジCSVの読み込み・前処理（共通モジュール）

会議準備やレポート作成時は必ずこのモジュールの関数を使うこと。
csv.reader による手書きパースは禁止（エンコーディング・カラムずれの温床）。
"""
import io

import pandas as pd
from pathlib import Path

_DEFAULT_CATEGORY_MAP = {
    "ドリンク": "ドリンク",
    "コーヒー,ラテ": "ドリンク",
    "ソーダ，ジュース，ティー": "ドリンク",
    "パンケーキ（セットドリンク）": "ドリンク",
    "ランチ（セットドリンク）": "ドリンク",
    "ランチ（セッットドリンク）": "ドリンク",
    "スイーツ": "スイーツ",
    "パンケーキ": "スイーツ",
    "かき氷": "スイーツ",
    "ランチ": "ランチ",
    "テイクアウト": "テイクアウト",
    "2F シェアラウンジ": "シェアラウンジ",
}

_CONFIG_DIR = Path(__file__).parent / "config"


def _load_category_map() -> dict:
    """YAMLの category_map があればそちらを優先、なければデフォルトを使う。"""
    import yaml
    for cfg_file in _CONFIG_DIR.glob("*.yaml"):
        try:
            with open(cfg_file, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if cfg and "category_map" in cfg:
                return cfg["category_map"]
        except Exception:
            continue
    return _DEFAULT_CATEGORY_MAP


CATEGORY_MAP = _load_category_map()


def _read_csvs(sales_dir: Path, prefix: str, add_month: bool = False) -> pd.DataFrame:
    import re, csv as csvmod
    pattern = re.compile(rf"^{re.escape(prefix)}_\d{{4}}_\d{{2}}\.csv$")
    files = sorted(f for f in sales_dir.glob(f"{prefix}_*.csv") if pattern.match(f.name))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        df = _read_single_csv(f, prefix)
        if add_month:
            m = f.stem.replace(f"{prefix}_", "")
            df["年月"] = m[:4] + "-" + m[5:]
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def _read_single_csv(f: Path, prefix: str) -> pd.DataFrame:
    """単一CSVを読み込む。ヘッダー文字化けによる列数不一致を自動修復する。"""
    import csv as csvmod

    for enc in ("shift_jis", "cp932", "utf-8-sig", "utf-8"):
        try:
            text = f.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        text = f.read_bytes().decode("shift_jis", errors="replace")

    lines = text.strip().split("\n")
    if len(lines) < 2:
        return pd.DataFrame()

    header_fields = list(csvmod.reader(io.StringIO(lines[0])))[0]
    data_fields = list(csvmod.reader(io.StringIO(lines[1])))[0]

    if len(header_fields) != len(data_fields):
        if prefix == "daily" and len(data_fields) == len(_DAILY_STANDARD_HEADER):
            df = pd.read_csv(
                io.StringIO("\n".join(lines[1:])),
                names=_DAILY_STANDARD_HEADER,
                dtype=str, quotechar='"',
            )
            return df

    df = pd.read_csv(
        io.StringIO(text), encoding=None, quotechar='"',
        on_bad_lines="skip", dtype=str,
    )
    return df


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


_DAILY_STANDARD_HEADER = [
    "日付", "純売上", "純売上(税抜)", "消費税", "免税額", "総売上",
    "値引き", "ポイント利用", "外税受領", "売上対象外", "送料", "手数料",
    "原価", "粗利", "販売点数", "返品数", "取引数", "取引単価",
    "客数", "客単価", "予算設定金額", "予算達成率", "クーポン利用",
]

_DAILY_STANDARD_COLS = set(_DAILY_STANDARD_HEADER)


def _normalize_daily_columns(df: pd.DataFrame) -> pd.DataFrame:
    """スマレジCSVのフォーマット差異を吸収する。

    月によって「原価」→「売上」へカラム名が変わったり、
    文字化けした来客数カラム（例: Βc用数）が挿入されて
    客数・客単価の意味がずれるケースに対応する。
    """
    if "売上" in df.columns:
        if "原価" not in df.columns:
            df = df.rename(columns={"売上": "原価"})
        else:
            df["原価"] = df["原価"].fillna(df["売上"])
            df = df.drop(columns=["売上"])

    extra = [c for c in df.columns if c not in _DAILY_STANDARD_COLS]
    for col in extra:
        vals = pd.to_numeric(df[col], errors="coerce")
        mask = vals.notna() & (vals > 0)
        if not mask.any():
            continue
        df.loc[mask, "客数"] = vals[mask]
        df = df.drop(columns=[col])
        break

    return df


def load_daily(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "daily")
    if df.empty:
        return df
    df["日付"] = df["日付"].astype(str)
    df = df[df["日付"].str.match(r"^\d{4}/\d{2}/\d{2}$", na=False)].copy()
    df["日付"] = pd.to_datetime(df["日付"])
    df = _normalize_daily_columns(df)
    df = _to_numeric(df, [
        "純売上", "純売上(税抜)", "消費税", "総売上", "値引き",
        "原価", "粗利", "販売点数", "返品数", "取引数",
        "取引単価", "客数", "クーポン利用",
    ])
    df = df[df["純売上"] > 0].copy()
    df["客単価"] = (df["純売上"] / df["客数"].replace(0, pd.NA)).round(0).fillna(0)
    df["曜日番号"] = df["日付"].dt.dayofweek
    df["粗利率"] = (df["粗利"] / df["純売上"] * 100).round(1)
    return df


def load_product(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "product", add_month=True)
    if df.empty:
        return df
    df = _to_numeric(df, [
        "純売上", "純売上(税抜)", "消費税", "原価",
        "純売上構成比", "販売点数", "返品数",
    ])
    df = df[df["純売上"] > 0].copy()
    df["商品コード"] = df["商品コード"].astype(str).str.strip()
    df["商品名"] = df["商品名"].astype(str).str.strip()
    df["部門名"] = df["部門名"].astype(str).str.strip()
    df = df[~df["商品コード"].str.contains("合計|前月|前年", na=False)].copy()
    df = df[~df["商品名"].isin(["", "nan", "合計"])].copy()
    df = df[~df["部門名"].isin(["", "nan", "合計"])].copy()
    df = df[~df["商品名"].str.contains("セット値引", na=False)].copy()
    df["カテゴリ"] = df["部門名"].map(CATEGORY_MAP).fillna("その他")
    return df


def load_customer(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "customer", add_month=True)
    if df.empty:
        return df
    df["ラベル"] = df["ラベル"].astype(str).str.strip()
    df = df[df["ラベル"].isin(["新規", "リピーター"])].copy()
    df = _to_numeric(df, [
        "純売上", "純売上(税抜)", "消費税", "純売上構成比",
        "販売点数", "返品数", "販売点数構成比", "客数", "客単価",
    ])
    return df


def load_department(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "department", add_month=True)
    if df.empty:
        return df
    df["部門名"] = df["部門名"].astype(str).str.strip()
    df = df[~df["部門名"].isin(["", "nan"])].copy()
    df = df[df["部門名"] != "合計"].copy()
    df = _to_numeric(df, [
        "純売上", "純売上(税抜)", "消費税", "原価",
        "純売上構成比", "販売点数", "返品数", "販売点数構成比",
    ])
    df = df[df["純売上"] > 0].copy()
    return df


def load_hourly(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "hourly", add_month=True)
    if df.empty:
        return df
    df["時間帯"] = df["時間帯"].astype(str).str.strip()
    df = df[~df["時間帯"].isin(["", "nan", "合計"])].copy()
    df = _to_numeric(df, ["純売上", "純売上(税抜)", "消費税", "構成比", "総売上",
                          "販売点数", "返品数", "取引数", "客数", "客単価"])
    df = df[df["純売上"] > 0].copy()
    df["時間"] = df["時間帯"].str.extract(r"(\d{2}):\d{2}").astype(int)
    return df


def load_customer_age(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "customer_age", add_month=True)
    if df.empty:
        return df
    df["ラベル"] = df["ラベル"].astype(str).str.strip()
    df = df[~df["ラベル"].isin(["", "nan"])].copy()
    df = df[df["ラベル"] != "合計"].copy()
    df = _to_numeric(df, ["純売上", "純売上(税抜)", "消費税", "純売上構成比",
                          "販売点数", "返品数", "販売点数構成比", "客数", "客単価"])
    return df


def load_customer_nationality(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "customer_nationality", add_month=True)
    if df.empty:
        return df
    df["ラベル"] = df["ラベル"].astype(str).str.strip()
    df = df[~df["ラベル"].isin(["", "nan"])].copy()
    df = df[df["ラベル"] != "合計"].copy()
    df = _to_numeric(df, ["純売上", "純売上(税抜)", "消費税", "純売上構成比",
                          "販売点数", "返品数", "販売点数構成比", "客数", "客単価"])
    return df


def load_weekday(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "weekday", add_month=True)
    if df.empty:
        return df
    df["曜日"] = df["曜日"].astype(str).str.strip()
    df = df[~df["曜日"].isin(["", "nan", "合計"])].copy()
    df = _to_numeric(df, ["回数", "純売上", "純売上(税抜)", "消費税", "構成比",
                          "総売上", "販売点数", "返品数", "取引数", "客数", "客単価"])
    _weekday_order = {"月曜日": 0, "火曜日": 1, "水曜日": 2, "木曜日": 3,
                      "金曜日": 4, "土曜日": 5, "日曜日": 6}
    df["曜日番号"] = df["曜日"].map(_weekday_order).fillna(7).astype(int)
    df = df.sort_values("曜日番号")
    return df


def validate_daily(df: pd.DataFrame, expected_month: str = None) -> dict:
    """日別データの整合性を検証し、結果をdictで返す。

    Args:
        df: load_daily() の戻り値
        expected_month: "2026-07" 形式。指定すると当月データの日数チェックを行う

    Returns:
        {"ok": bool, "warnings": [...], "summary": {...}}
    """
    warnings = []
    if df.empty:
        return {"ok": False, "warnings": ["データが空です"], "summary": {}}

    total_sales = int(df["純売上"].sum())
    total_customers = int(df["客数"].sum())
    num_days = len(df)
    daily_avg = int(total_sales / num_days) if num_days else 0
    cust_avg = round(total_customers / num_days, 1) if num_days else 0
    unit_price = int(total_sales / total_customers) if total_customers else 0

    if expected_month:
        month_df = df[df["日付"].dt.strftime("%Y-%m") == expected_month]
        import calendar
        year, mon = map(int, expected_month.split("-"))
        max_days = calendar.monthrange(year, mon)[1]
        actual_days = len(month_df)
        if actual_days < max_days * 0.6:
            warnings.append(
                f"{expected_month}: {actual_days}日分のデータ（{max_days}日中）— "
                f"営業日数が少なすぎる場合はCSVの取得漏れを確認"
            )

    zero_customer_days = df[df["客数"] == 0]
    if len(zero_customer_days) > 0:
        dates = zero_customer_days["日付"].dt.strftime("%m/%d").tolist()
        warnings.append(f"客数0の日あり: {', '.join(dates[:5])}")

    high_days = df[df["純売上"] > 100000]
    event_info = []
    for _, row in high_days.iterrows():
        d = row["日付"].strftime("%m/%d")
        s = int(row["純売上"])
        event_info.append(f"{d}(¥{s:,})")
    if event_info:
        warnings.append(f"イベント日の可能性（¥10万超）: {', '.join(event_info)}")

    return {
        "ok": len(warnings) == 0,
        "warnings": warnings,
        "summary": {
            "days": num_days,
            "total_sales": total_sales,
            "daily_avg": daily_avg,
            "total_customers": total_customers,
            "customer_avg": cust_avg,
            "unit_price": unit_price,
        },
    }


def compare_same_period(
    sales_dir: Path,
    target_start: str,
    target_end: str,
    event_threshold: int = 100000,
) -> pd.DataFrame:
    """複数月の同一日付範囲を比較する。

    Args:
        sales_dir: data/sales/ ディレクトリ
        target_start: "2026-07-01" 形式
        target_end: "2026-07-19" 形式
        event_threshold: この金額を超える日をイベント日として除外

    Returns:
        月ごとの集計DataFrame（全日 / イベント除外の両方）
    """
    df = load_daily(sales_dir)
    if df.empty:
        return pd.DataFrame()

    start_day = int(target_start.split("-")[2])
    end_day = int(target_end.split("-")[2])

    df["day"] = df["日付"].dt.day
    period = df[(df["day"] >= start_day) & (df["day"] <= end_day)].copy()
    period["年月"] = period["日付"].dt.strftime("%Y-%m")
    period["is_event"] = period["純売上"] > event_threshold

    rows = []
    for ym, grp in period.groupby("年月"):
        all_days = len(grp)
        all_sales = int(grp["純売上"].sum())
        all_cust = int(grp["客数"].sum())

        normal = grp[~grp["is_event"]]
        n_days = len(normal)
        n_sales = int(normal["純売上"].sum())
        n_cust = int(normal["客数"].sum())

        event_dates = grp[grp["is_event"]]["日付"].dt.strftime("%m/%d").tolist()

        rows.append({
            "年月": ym,
            "全営業日数": all_days,
            "全純売上": all_sales,
            "全日販": int(all_sales / all_days) if all_days else 0,
            "全客数": all_cust,
            "全客単価": int(all_sales / all_cust) if all_cust else 0,
            "通常営業日数": n_days,
            "通常純売上": n_sales,
            "通常日販": int(n_sales / n_days) if n_days else 0,
            "通常客数": n_cust,
            "通常客単価": int(n_sales / n_cust) if n_cust else 0,
            "イベント日": ", ".join(event_dates) if event_dates else "なし",
        })

    result = pd.DataFrame(rows).sort_values("年月", ascending=False)
    return result


_DOW_JP = ["月", "火", "水", "木", "金", "土", "日"]


def build_weekly_table(df: pd.DataFrame, week_start: str, week_end: str,
                       event_threshold: int = 80000) -> list[list[str]]:
    """指定期間の日別テーブル行を生成する（ヘッダー行付き）。

    曜日は日付から自動算出。イベント日は備考に表示。
    戻り値は notion_writer.table() にそのまま渡せる。
    """
    start = pd.Timestamp(week_start)
    end = pd.Timestamp(week_end)
    period = df[(df["日付"] >= start) & (df["日付"] <= end)].sort_values("日付")

    rows = [["日付", "曜日", "純売上", "客数", "客単価", "備考"]]
    for _, r in period.iterrows():
        d = r["日付"]
        sales = int(r["純売上"])
        cust = int(r["客数"])
        unit = int(r["客単価"])
        dow = _DOW_JP[d.weekday()]
        note = ""
        if sales > event_threshold:
            note = f"⚠️ ¥{event_threshold:,}超"
        rows.append([
            d.strftime("%-m/%-d"), dow,
            f"¥{sales:,}", str(cust), f"¥{unit:,}", note,
        ])
    return rows


def build_summary_table(sales_dir: Path, target_end: str,
                        event_threshold: int = 80000) -> list[list[str]]:
    """同期間比較の売上サマリーテーブル行を生成する（ヘッダー行付き）。

    target_end: "2026-07-19" — 当月の最終データ日
    各月の1日〜同日を比較。イベント日は自動除外。
    戻り値は notion_writer.table() にそのまま渡せる。
    """
    year, month, end_day = target_end.split("-")
    start = f"{year}-{month}-01"
    comp = compare_same_period(sales_dir, start, target_end, event_threshold)
    if comp.empty:
        return [["データなし"]]

    target_ym = f"{year}-{month}"
    target_row = comp[comp["年月"] == target_ym]
    prev_months = comp[comp["年月"] != target_ym].head(2)

    header = ["指標", f"{int(month)}月（1-{int(end_day)}日）"]

    # Add event-excluded column for target if it has events
    has_target_event = False
    if not target_row.empty:
        tr = target_row.iloc[0]
        if tr["イベント日"] != "なし":
            has_target_event = True
            header.append(f"{int(month)}月（イベント除外）")

    for _, pr in prev_months.iterrows():
        ym = pr["年月"]
        m = int(ym.split("-")[1])
        label = f"{m}月同期間"
        if pr["イベント日"] != "なし":
            label += f"（除{pr['イベント日']}）"
        header.append(label)

    header.append("前月比")

    def _build_row(label, key_all, key_normal, fmt="¥{:,}"):
        row = [label]
        t_val = None
        if not target_row.empty:
            tr = target_row.iloc[0]
            row.append(fmt.format(tr[key_all]))
            t_val = tr[key_normal]
            if has_target_event:
                row.append(fmt.format(tr[key_normal]))

        prev_val = None
        for _, pr in prev_months.iterrows():
            v = pr[key_normal]
            row.append(fmt.format(v))
            if prev_val is None:
                prev_val = v

        if t_val and prev_val and prev_val > 0:
            pct = (t_val / prev_val - 1) * 100
            row.append(f"{pct:+.1f}%")
        else:
            row.append("—")
        return row

    rows = [header]
    rows.append(_build_row("日販平均", "全日販", "通常日販"))
    rows.append(_build_row("総客数", "全客数", "通常客数", "{:,}人"))
    rows.append(_build_row("客単価", "全客単価", "通常客単価"))

    # Operating days row
    days_row = ["営業日数"]
    if not target_row.empty:
        tr = target_row.iloc[0]
        days_row.append(f"{tr['全営業日数']}日")
        if has_target_event:
            days_row.append(f"{tr['通常営業日数']}日")
    for _, pr in prev_months.iterrows():
        days_row.append(f"{pr['通常営業日数']}日")
    days_row.append("—")
    rows.append(days_row)

    return rows


def save_uploaded_csv(uploaded_file, sales_dir: Path) -> str:
    """Streamlitのアップロードファイルをdata/sales/に保存する。
    ファイル名からprefixを判定して適切な名前で保存。"""
    sales_dir.mkdir(parents=True, exist_ok=True)
    name = uploaded_file.name
    dest = sales_dir / name
    dest.write_bytes(uploaded_file.getvalue())
    return str(dest)
