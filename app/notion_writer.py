"""Notionページの作成・ブロック追記ユーティリティ（claude-code integration用）

主な機能:
  - create_meeting_page(): 定例会議ページを自動作成（親ページから権限継承、接続作業不要）
  - append_blocks(): 任意のブロックをページに追記
  - insert_blocks_after(): 指定ブロックの直後にブロックを挿入
  - delete_blocks(): 指定ブロックを削除
  - get_blocks(): ページのブロック一覧を取得
  - create_transcript_toggle(): 文字起こし用トグルを作成

ブロック生成ヘルパー:
  - heading(), text_block(), bulleted(), callout(), table(), divider(), toggle()
"""
import requests
import json
from pathlib import Path
from datetime import date

TOKEN_FILE = Path(__file__).parent / "config" / ".notion_token"
NOTION_VERSION = "2022-06-28"

# 「bokashi 議事録」親ページID — このページにclaude-codeインテグレーションが接続済み
# 子ページはここに作成すれば権限が自動継承される
MEETING_PARENT_PAGE_ID = "35e05528-aa05-80b2-aab6-e006658f3f42"


# ============================================================
# 内部ユーティリティ
# ============================================================

def _get_token():
    return TOKEN_FILE.read_text().strip()


def _headers():
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def extract_page_id(url_or_id: str) -> str:
    """NotionのURLまたはIDからpage_idを抽出する。

    対応形式:
      - UUID形式: "35e05528-aa05-80b2-aab6-e006658f3f42"
      - URL形式: "https://www.notion.so/Page-Title-35e05528aa0580b2aab6e006658f3f42"
      - ハイフンなし32文字: "35e05528aa0580b2aab6e006658f3f42"
    """
    url_or_id = url_or_id.strip().rstrip("/")

    # 既にUUID形式（8-4-4-4-12）ならそのまま返す
    import re
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
    if uuid_pattern.match(url_or_id):
        return url_or_id

    # URLからIDを抽出
    clean = url_or_id.split("?")[0]
    raw = clean.split("-")[-1] if "-" in clean.split("/")[-1] else clean.split("/")[-1]
    raw = raw.replace("-", "")
    if len(raw) == 32:
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return raw


# ============================================================
# ブロック生成ヘルパー（公開API）
# ============================================================

def text_block(text: str, block_type: str = "paragraph", **kwargs) -> dict:
    """テキストブロックを生成"""
    block = {
        "object": "block",
        "type": block_type,
        block_type: {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }
    if "color" in kwargs:
        block[block_type]["color"] = kwargs["color"]
    return block


def heading(text: str, level: int = 2, toggleable: bool = False) -> dict:
    """見出しブロックを生成"""
    htype = f"heading_{level}"
    return {
        "object": "block",
        "type": htype,
        htype: {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "is_toggleable": toggleable,
        }
    }


def divider() -> dict:
    """区切り線ブロック"""
    return {"object": "block", "type": "divider", "divider": {}}


def bulleted(text: str, bold_prefix: str = None) -> dict:
    """箇条書きブロック"""
    if bold_prefix:
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": bold_prefix}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": f" {text}"}},
                ]
            }
        }
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def callout(text: str, icon: str = "📌") -> dict:
    """コールアウトブロック"""
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"type": "emoji", "emoji": icon},
        }
    }


def table_row(cells: list) -> dict:
    """テーブル行ブロック"""
    return {
        "object": "block",
        "type": "table_row",
        "table_row": {
            "cells": [[{"type": "text", "text": {"content": str(c)}}] for c in cells]
        }
    }


def table(rows: list, has_header: bool = True) -> dict:
    """テーブルブロック"""
    width = len(rows[0]) if rows else 0
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": has_header,
            "has_row_header": False,
            "children": [table_row(row) for row in rows],
        }
    }


def toggle(title: str, children: list = None) -> dict:
    """トグルブロック（折りたたみ）"""
    block = {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
        }
    }
    if children:
        block["toggle"]["children"] = children[:100]  # Notion APIは子ブロック100個まで
    return block


# ============================================================
# ページ操作API
# ============================================================

def create_meeting_page(meeting_date: str = None, title_suffix: str = "定例会議") -> dict:
    """定例会議用のNotionページを自動作成する。

    親ページ「bokashi 議事録」の子ページとして作成するため、
    claude-codeインテグレーションの権限が自動で継承される。
    手動で「接続」を追加する必要はない。

    Args:
        meeting_date: "YYYY-MM-DD" 形式の日付。省略時は今日の日付
        title_suffix: ページタイトルの接尾辞

    Returns:
        {"ok": True, "page_id": "...", "url": "..."} or {"error": ...}
    """
    if meeting_date is None:
        meeting_date = date.today().isoformat()

    page_title = f"{meeting_date} {title_suffix}"

    # ページ作成
    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=_headers(),
        json={
            "parent": {"page_id": MEETING_PARENT_PAGE_ID},
            "properties": {
                "title": {
                    "title": [{"text": {"content": page_title}}]
                }
            },
        },
    )

    if r.status_code != 200:
        return {"error": r.status_code, "detail": r.json()}

    page = r.json()
    page_id = page["id"]
    url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

    # 初期構造を書き込み: 文字起こし貼り付け用のセクションを用意
    init_blocks = [
        callout(
            f"{meeting_date} 定例会議ページ（Claude Code自動作成）",
            "📋"
        ),
        divider(),
        heading("文字起こし全文", 2),
        callout(
            "会議後、Plaud Noteの文字起こしテキストをこの下に貼り付けてください",
            "👇"
        ),
    ]

    append_result = append_blocks(page_id, init_blocks)
    if append_result.get("error"):
        return {"error": "page_created_but_init_failed", "page_id": page_id, "url": url, "detail": append_result}

    return {"ok": True, "page_id": page_id, "url": url, "title": page_title}


def append_blocks(page_url_or_id: str, blocks: list) -> dict:
    """Notionページの末尾にブロックを追記する。100ブロック制限のためチャンクで送信。"""
    page_id = extract_page_id(page_url_or_id)
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    results = []
    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i + 100]
        r = requests.patch(url, headers=_headers(), json={"children": chunk})
        if r.status_code != 200:
            return {"error": r.status_code, "detail": r.json(), "chunk_index": i}
        results.append(r.json())
    return {"ok": True, "chunks_sent": len(results), "total_blocks": len(blocks)}


def insert_blocks_after(page_url_or_id: str, after_block_id: str, blocks: list) -> dict:
    """指定ブロックの直後にブロックを挿入する。"""
    page_id = extract_page_id(page_url_or_id)
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    results = []
    current_after = after_block_id
    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i + 100]
        payload = {"children": chunk, "after": current_after}
        r = requests.patch(url, headers=_headers(), json=payload)
        if r.status_code != 200:
            return {"error": r.status_code, "detail": r.json(), "chunk_index": i}
        data = r.json()
        results.append(data)
        # 次のチャンクは最後に挿入したブロックの後に
        inserted = data.get("results", [])
        if inserted:
            current_after = inserted[-1]["id"]
    return {"ok": True, "chunks_sent": len(results), "total_blocks": len(blocks)}


def get_blocks(page_url_or_id: str, include_children: bool = False) -> list:
    """ページのブロック一覧を取得する。"""
    page_id = extract_page_id(page_url_or_id)
    blocks = _fetch_block_children(page_id)
    if include_children:
        enriched = []
        for b in blocks:
            enriched.append(b)
            if b.get("has_children") and b.get("type") != "child_page":
                children = _fetch_block_children(b["id"])
                for c in children:
                    c["_parent_block_id"] = b["id"]
                    enriched.append(c)
        return enriched
    return blocks


def delete_blocks(block_ids: list) -> dict:
    """指定されたブロックIDのリストを削除する。"""
    results = []
    for bid in block_ids:
        r = requests.delete(
            f"https://api.notion.com/v1/blocks/{bid}",
            headers=_headers(),
        )
        results.append({"id": bid, "status": r.status_code})
    failed = [r for r in results if r["status"] != 200]
    return {"ok": len(failed) == 0, "deleted": len(results) - len(failed), "failed": failed}


def update_block_text(block_id: str, new_text: str, block_type: str = "paragraph") -> dict:
    """ブロックのテキストを更新する。"""
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{block_id}",
        headers=_headers(),
        json={
            block_type: {
                "rich_text": [{"type": "text", "text": {"content": new_text}}]
            }
        },
    )
    if r.status_code == 200:
        return {"ok": True}
    return {"error": r.status_code, "detail": r.json()}


def create_transcript_toggle(page_url_or_id: str, transcript_text: str,
                              toggle_title: str = "文字起こし全文（クリックで展開）") -> dict:
    """文字起こしテキストをトグル（折りたたみ）ブロックとしてページに追加する。

    長いテキストは2000文字ごとに分割してトグルの子ブロックにする。
    """
    page_id = extract_page_id(page_url_or_id)

    # テキストを2000文字チャンクに分割（Notion APIの制限）
    chunks = []
    for i in range(0, len(transcript_text), 2000):
        chunks.append(transcript_text[i:i + 2000])

    # 最初の100チャンクをトグルの子ブロックとして作成
    first_batch = chunks[:100]
    children = [text_block(chunk) for chunk in first_batch]
    toggle_block = toggle(toggle_title, children)

    result = append_blocks(page_id, [toggle_block])
    if result.get("error"):
        return result

    # 100チャンクを超える場合、トグル内に追加で書き込み
    if len(chunks) > 100:
        # トグルブロックのIDを取得
        blocks = get_blocks(page_id)
        toggle_id = None
        for b in reversed(blocks):
            if b.get("type") == "toggle":
                toggle_id = b["id"]
                break

        if toggle_id:
            for i in range(100, len(chunks), 100):
                batch = chunks[i:i + 100]
                extra_children = [text_block(chunk) for chunk in batch]
                extra_result = append_blocks(toggle_id, extra_children)
                if extra_result.get("error"):
                    return extra_result

    return {"ok": True, "chunks": len(chunks), "toggle_title": toggle_title}


# ============================================================
# 内部ヘルパー
# ============================================================

def _fetch_block_children(block_id: str) -> list:
    """ブロックの子ブロック一覧を取得（ページネーション対応）"""
    blocks = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=_headers())
        if r.status_code != 200:
            break
        data = r.json()
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return blocks


def find_block_by_text(page_url_or_id: str, search_text: str) -> str:
    """ページ内で指定テキストを含むブロックのIDを返す。見つからなければNone。"""
    blocks = get_blocks(page_url_or_id)
    for b in blocks:
        btype = b.get("type", "")
        content = b.get(btype, {})
        rich_text = content.get("rich_text", [])
        block_text = "".join(rt.get("plain_text", "") for rt in rich_text)
        if search_text in block_text:
            return b["id"]
    return None


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    usage = """Usage:
  python notion_writer.py create [YYYY-MM-DD]     # 会議ページを新規作成
  python notion_writer.py append <page_url> <text> # テキストを追記
  python notion_writer.py blocks <page_url>        # ブロック一覧を表示
"""

    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "create":
        meeting_date = sys.argv[2] if len(sys.argv) > 2 else None
        result = create_meeting_page(meeting_date)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("ok"):
            print(f"\n✅ ページ作成完了: {result['title']}")
            print(f"   URL: {result['url']}")
        else:
            print(f"\n❌ エラー: {result}")

    elif cmd == "append":
        if len(sys.argv) < 4:
            print("Usage: python notion_writer.py append <page_url> <text>")
            sys.exit(1)
        blocks = [text_block(sys.argv[3])]
        result = append_blocks(sys.argv[2], blocks)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "blocks":
        if len(sys.argv) < 3:
            print("Usage: python notion_writer.py blocks <page_url>")
            sys.exit(1)
        blocks = get_blocks(sys.argv[2])
        for i, b in enumerate(blocks):
            btype = b.get("type", "")
            content = b.get(btype, {})
            rich_text = content.get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_text)[:80]
            print(f"  [{i}] {btype} ({b['id']}): {text}")

    else:
        print(usage)
