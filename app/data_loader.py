"""スマレジCSVの読み込み・前処理（共通モジュール）"""
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
    files = sorted(sales_dir.glob(f"{prefix}_*.csv"))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        df = pd.read_csv(f, encoding="shift_jis", quotechar='"')
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


def load_daily(sales_dir: Path) -> pd.DataFrame:
    df = _read_csvs(sales_dir, "daily")
    if df.empty:
        return df
    df["日付"] = df["日付"].astype(str)
    df = df[df["日付"].str.match(r"^\d{4}/\d{2}/\d{2}$", na=False)].copy()
    df["日付"] = pd.to_datetime(df["日付"])
    df = _to_numeric(df, [
        "純売上", "純売上(税抜)", "消費税", "総売上", "値引き",
        "原価", "粗利", "販売点数", "返品数", "取引数",
        "取引単価", "客数", "客単価", "クーポン利用",
    ])
    df = df[df["純売上"] > 0].copy()
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


def save_uploaded_csv(uploaded_file, sales_dir: Path) -> str:
    """Streamlitのアップロードファイルをdata/sales/に保存する。
    ファイル名からprefixを判定して適切な名前で保存。"""
    sales_dir.mkdir(parents=True, exist_ok=True)
    name = uploaded_file.name
    dest = sales_dir / name
    dest.write_bytes(uploaded_file.getvalue())
    return str(dest)
