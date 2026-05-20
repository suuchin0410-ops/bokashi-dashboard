"""スマレジCSVの読み込み・前処理（共通モジュール）"""
import io

import pandas as pd
from pathlib import Path

CATEGORY_MAP = {
    "ドリンク": "ドリンク",
    "コーヒー,ラテ": "ドリンク",
    "ソーダ，ジュース，ティー": "ドリンク",
    "パンケーキ（セットドリンク）": "ドリンク",
    "ランチ（セットドリンク）": "ドリンク",
    "スイーツ": "スイーツ",
    "パンケーキ": "スイーツ",
    "ランチ": "ランチ",
    "テイクアウト": "テイクアウト",
    "2F シェアラウンジ": "シェアラウンジ",
}


def _read_csvs(sales_dir: Path, prefix: str, add_month: bool = False) -> pd.DataFrame:
    import re
    pattern = re.compile(rf"^{re.escape(prefix)}_\d{{4}}_\d{{2}}\.csv$")
    files = sorted(f for f in sales_dir.glob(f"{prefix}_*.csv") if pattern.match(f.name))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        for enc in ("shift_jis", "cp932", "utf-8-sig", "utf-8"):
            try:
                df = pd.read_csv(f, encoding=enc, quotechar='"', on_bad_lines="skip", dtype=str)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            raw = f.read_bytes().decode("shift_jis", errors="replace")
            df = pd.read_csv(io.StringIO(raw), quotechar='"', on_bad_lines="skip", dtype=str)
        if add_month:
            m = f.stem.replace(f"{prefix}_", "")
            df["年月"] = m[:4] + "-" + m[5:]
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


_DAILY_STANDARD_COLS = {
    "日付", "純売上", "純売上(税抜)", "消費税", "免税額", "総売上",
    "値引き", "ポイント利用", "外税受領", "売上対象外", "送料", "手数料",
    "原価", "売上", "粗利", "販売点数", "返品数", "取引数", "取引単価",
    "客数", "客単価", "予算設定金額", "予算達成率", "クーポン利用",
}


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
    df["商品名"] = df["商品名"].astype(str).str.strip()
    df["部門名"] = df["部門名"].astype(str).str.strip()
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


def save_uploaded_csv(uploaded_file, sales_dir: Path) -> str:
    """Streamlitのアップロードファイルをdata/sales/に保存する。
    ファイル名からprefixを判定して適切な名前で保存。"""
    sales_dir.mkdir(parents=True, exist_ok=True)
    name = uploaded_file.name
    dest = sales_dir / name
    dest.write_bytes(uploaded_file.getvalue())
    return str(dest)
