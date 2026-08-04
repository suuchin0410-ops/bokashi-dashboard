"""Google Drive から売上CSVを直接読み込むモジュール（Streamlit Cloud用）。

Streamlit SecretsにGCPサービスアカウントのキーが設定されていれば
Google Drive APIでCSVを取得し、一時ディレクトリに保存して返す。
未設定の場合はローカルの data/sales/ にフォールバックする。
"""
from __future__ import annotations

import io
import re
import shutil
import tempfile
from pathlib import Path

import streamlit as st

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    _HAS_GOOGLE = True
except ImportError:
    _HAS_GOOGLE = False

_LOCAL_SALES_DIR = Path(__file__).parent.parent / "data" / "sales"

_PREFIX_MAP = {
    "日別売上": "daily",
    "商品別売上": "product",
    "部門別売上": "department",
    "客層別売上_既存・新規": "customer",
    "客層別売上_年代": "customer_age",
    "客層別売上_国籍": "customer_nationality",
    "曜日別売上": "weekday",
    "時間帯別売上": "hourly",
}


def _map_filename(title: str) -> str | None:
    prefix = None
    for jp_name, p in _PREFIX_MAP.items():
        if title.startswith(jp_name):
            prefix = p
            break
    if not prefix:
        return None
    m = re.search(r"期間[：:](\d{4})(\d{2})\d{2}-\d{8}", title)
    if m:
        return f"{prefix}_{m.group(1)}_{m.group(2)}.csv"
    m = re.search(r"(\d{4})[_-](\d{2})", title)
    if m:
        return f"{prefix}_{m.group(1)}_{m.group(2)}.csv"
    return None


def _build_drive_service():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds)


_PREV_TMP_DIR: str | None = None


@st.cache_data(ttl=300, show_spinner="Google Driveからデータを取得中...")
def _fetch_csvs_from_drive(folder_id: str) -> str:
    """DriveフォルダのCSVをダウンロードしてtmpディレクトリのパスを返す。5分キャッシュ。"""
    global _PREV_TMP_DIR
    if _PREV_TMP_DIR and Path(_PREV_TMP_DIR).exists():
        shutil.rmtree(_PREV_TMP_DIR, ignore_errors=True)
    service = _build_drive_service()
    query = f"'{folder_id}' in parents and mimeType='text/csv' and trashed=false"
    results = service.files().list(
        q=query, fields="files(id, name, modifiedTime)", pageSize=100
    ).execute()
    files = results.get("files", [])

    # 同じlocal_nameにマッピングされるファイルが複数ある場合、最新のものだけを残す
    best: dict[str, dict] = {}
    for f in files:
        local_name = _map_filename(f["name"])
        if not local_name:
            continue
        mod_time = f.get("modifiedTime", "")
        if local_name not in best or mod_time > best[local_name]["modifiedTime"]:
            best[local_name] = {"id": f["id"], "name": f["name"], "modifiedTime": mod_time}

    tmp_dir = Path(tempfile.mkdtemp(prefix="bokashi_sales_"))
    downloaded = []
    for local_name, f in best.items():
        request = service.files().get_media(fileId=f["id"])
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        (tmp_dir / local_name).write_bytes(buf.getvalue())
        downloaded.append(local_name)

    _PREV_TMP_DIR = str(tmp_dir)
    return str(tmp_dir)


def _drive_available() -> bool:
    if not _HAS_GOOGLE:
        return False
    try:
        _ = st.secrets["gcp_service_account"]
        return True
    except (FileNotFoundError, KeyError):
        return False


def get_sales_dir() -> Path:
    """CSVのあるディレクトリを返す。Drive接続可能ならDriveから、なければローカル。"""
    if _drive_available():
        try:
            folder_id = st.secrets.get("drive_sales_folder_id", "1Ligr0RnQOo7aPB9iZ2YMS0CefsgGHuBC")
            return Path(_fetch_csvs_from_drive(folder_id))
        except Exception as e:
            st.sidebar.warning(f"Drive接続エラー: {e}")
    return _LOCAL_SALES_DIR


def get_data_source_info() -> dict:
    """現在のデータソース情報を返す（サイドバー表示用）。"""
    if _drive_available():
        return {"source": "Google Drive", "icon": "☁️", "cached_ttl": "5分"}
    return {"source": "ローカルファイル", "icon": "💾", "cached_ttl": None}
