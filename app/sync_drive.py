"""Google Drive salesフォルダとローカル data/sales/ を同期するためのユーティリティ。

このモジュールは Claude の Google Drive MCP から取得したファイル情報を使い、
ローカルにCSVを保存する。MCP呼び出し自体はClaude側で行い、結果をこのモジュールに渡す。

使い方（Claude側）:
    1. search_files で salesフォルダを検索
    2. このモジュールの map_drive_files() でDriveファイル名 → ローカルファイル名を変換
    3. download_file_content で取得した base64 を save_from_base64() でローカルに保存
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from pathlib import Path

SALES_DIR = Path(__file__).parent.parent / "data" / "sales"

DRIVE_SALES_FOLDER_ID = "1Ligr0RnQOo7aPB9iZ2YMS0CefsgGHuBC"

PREFIX_MAP = {
    "日別売上": "daily",
    "商品別売上": "product",
    "部門別売上": "department",
    "客層別売上_既存・新規": "customer",
    "客層別売上_年代": "customer_age",
    "客層別売上_国籍": "customer_nationality",
    "曜日別売上": "weekday",
    "時間帯別売上": "hourly",
}


def _extract_month(title: str) -> str | None:
    """Driveファイル名から YYYY_MM を抽出する。"""
    # 「期間：20260401-20260430」形式
    m = re.search(r"期間[：:](\d{4})(\d{2})\d{2}-\d{8}", title)
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    # 「年月：2026_04」形式
    m = re.search(r"(\d{4})[_-](\d{2})", title)
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    return None


def _extract_prefix(title: str) -> str | None:
    """Driveファイル名からローカルのprefix名を返す。"""
    for jp_name, prefix in PREFIX_MAP.items():
        if title.startswith(jp_name):
            return prefix
    return None


def map_drive_file(title: str) -> str | None:
    """Driveのファイル名 → ローカルファイル名 (例: daily_2026_04.csv)。
    マッピングできない場合は None。"""
    prefix = _extract_prefix(title)
    month = _extract_month(title)
    if prefix and month:
        return f"{prefix}_{month}.csv"
    return None


def map_drive_files(drive_files: list[dict]) -> list[dict]:
    """Drive検索結果のファイルリストに local_name を付与して返す。

    Args:
        drive_files: search_files の結果。各要素に id, title, modifiedTime が必要。

    Returns:
        local_name が付与されたファイルリスト。マッピングできないファイルは除外。
    """
    results = []
    seen = {}
    for f in drive_files:
        local_name = map_drive_file(f["title"])
        if not local_name:
            continue
        mod = f.get("modifiedTime", "")
        if local_name in seen:
            if mod <= seen[local_name]["modifiedTime"]:
                continue
        seen[local_name] = {**f, "local_name": local_name, "modifiedTime": mod}

    return list(seen.values())


def save_from_base64(b64_content: str, local_name: str) -> Path:
    """base64エンコードされたCSVをローカルに保存する。"""
    SALES_DIR.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(b64_content)
    dest = SALES_DIR / local_name
    dest.write_bytes(data)
    return dest


def get_sync_status(drive_files: list[dict]) -> dict:
    """Driveとローカルの差分を返す。

    Returns:
        {
            "new": [...],       # ローカルに存在しないファイル
            "updated": [...],   # ローカルより新しいファイル
            "synced": [...],    # 同期済み
        }
    """
    mapped = map_drive_files(drive_files)
    new, updated, synced = [], [], []

    for f in mapped:
        local_path = SALES_DIR / f["local_name"]
        if not local_path.exists():
            new.append(f)
        else:
            local_size = local_path.stat().st_size
            drive_size = int(f.get("fileSize", 0))
            if drive_size != local_size:
                updated.append(f)
            else:
                synced.append(f)

    return {"new": new, "updated": updated, "synced": synced}


SYNC_LOG = SALES_DIR / ".sync_log.json"


def _read_sync_log() -> dict:
    if SYNC_LOG.exists():
        return json.loads(SYNC_LOG.read_text(encoding="utf-8"))
    return {}


def record_sync(synced_files: list[str]) -> None:
    """同期完了を記録する。Claudeがsave_from_base64()後に呼ぶ。"""
    log = _read_sync_log()
    now = datetime.now().isoformat(timespec="seconds")
    log["last_sync"] = now
    log["files"] = {**log.get("files", {}), **{f: now for f in synced_files}}
    SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    SYNC_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def get_last_sync_info() -> dict | None:
    """最終同期情報を返す。未同期ならNone。"""
    log = _read_sync_log()
    if not log:
        return None
    return {
        "last_sync": log.get("last_sync"),
        "file_count": len(log.get("files", {})),
        "files": log.get("files", {}),
    }


def get_local_file_summary() -> list[dict]:
    """ローカルのsalesファイル一覧とサイズを返す。"""
    if not SALES_DIR.exists():
        return []
    files = []
    for p in sorted(SALES_DIR.glob("*.csv")):
        files.append({
            "name": p.name,
            "size": p.stat().st_size,
            "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
        })
    return files
