"""Notionページのテキストを取得するユーティリティ"""
import requests
import re
from pathlib import Path

TOKEN_FILE = Path(__file__).parent / "config" / ".notion_token"


def _get_token():
    return TOKEN_FILE.read_text().strip()


def _extract_page_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip().rstrip("/")
    clean = url_or_id.split("?")[0]
    raw = clean.split("-")[-1] if "-" in clean.split("/")[-1] else clean.split("/")[-1]
    raw = raw.replace("-", "")
    if len(raw) == 32:
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return raw


def _get_blocks(block_id: str, token: str) -> list:
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
    blocks = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=headers)
        data = r.json()
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return blocks


def _extract_text(block: dict) -> str:
    btype = block.get("type", "")
    content = block.get(btype, {})
    rich_text = content.get("rich_text", [])
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def _get_page_title(page_id: str, token: str) -> str:
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=headers)
    data = r.json()
    props = data.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    return ""


def fetch_page(url_or_id: str) -> dict:
    token = _get_token()
    page_id = _extract_page_id(url_or_id)
    title = _get_page_title(page_id, token)
    blocks = _get_blocks(page_id, token)

    lines = []
    for b in blocks:
        text = _extract_text(b)
        if text.strip():
            lines.append(text)

    return {"title": title, "page_id": page_id, "text": "\n".join(lines), "block_count": len(blocks)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python notion_reader.py <notion_url_or_page_id>")
        sys.exit(1)
    result = fetch_page(sys.argv[1])
    print(f"タイトル: {result['title']}")
    print(f"ブロック数: {result['block_count']}")
    print(f"文字数: {len(result['text'])}")
    print("---")
    print(result["text"][:3000])
