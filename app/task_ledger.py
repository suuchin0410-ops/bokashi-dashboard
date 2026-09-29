"""アクションアイテム台帳（data/tasks.json）

会議をまたいでタスクの状態を管理する。Phase 2 は台帳から未完了タスクだけを
Notion の to_do（チェックボックス）ブロックとして出力し、Phase 4 は Notion で
チェックされた to_do を読み取って台帳を「完了」に更新する。
完了・取下のタスクは翌週以降のレポートに表示されない。

状態: 進行中 / 保留 / 完了 / 取下
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

LEDGER = Path(__file__).parent.parent / "data" / "tasks.json"
ARCHIVE = LEDGER.parent / "tasks_archive.json"
OPEN_STATUSES = ("進行中", "保留")
STATUS_TAG = {"進行中": "🔄 進行中", "保留": "⏸ 保留", "完了": "✅ 完了", "取下": "⛔ 取下"}
STATUS_COLOR = {"進行中": "blue_background", "保留": "gray_background", "完了": "green_background", "取下": "red_background"}


# ------------------------------------------------------------
# 読み書き
# ------------------------------------------------------------
def load() -> list[dict]:
    if not LEDGER.exists():
        return []
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def save(tasks: list[dict]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")


def next_id(tasks: list[dict]) -> int:
    """台帳とアーカイブの両方を見て、過去に使った番号を再利用しない。"""
    used = [t["id"] for t in tasks]
    if ARCHIVE.exists():
        used += [t["id"] for t in json.loads(ARCHIVE.read_text(encoding="utf-8"))]
    return max(used, default=0) + 1


def open_tasks(tasks: list[dict] | None = None) -> list[dict]:
    """翌週以降に表示するタスク（完了・取下を除く）"""
    tasks = load() if tasks is None else tasks
    return [t for t in tasks if t.get("status", "進行中") in OPEN_STATUSES]


def add(tasks: list[dict], task: str, owner: str, cat: str = "", since: str = "",
        due: str = "", ai: str = "", why: str = "") -> dict:
    t = dict(id=next_id(tasks), cat=cat, task=task, owner=owner, since=since or date.today().strftime("%-m/%-d"),
             due=due, carry=1, status="進行中", ai=ai, why=why, done_at="", notes="")
    tasks.append(t)
    return t


def set_status(tasks: list[dict], task_id: int, status: str, when: str = "", note: str = "") -> dict | None:
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = status
            if status in ("完了", "取下"):
                t["done_at"] = when or date.today().isoformat()
            if note:
                t["notes"] = (t.get("notes", "") + " " + note).strip()
            return t
    return None


ARCHIVE = LEDGER.parent / "tasks_archive.json"


def archive_done(tasks: list[dict]) -> int:
    """完了・取下のタスクを台帳から削除し、tasks_archive.json に移す（履歴保持）。
    Phase 4 の sync 後に呼ぶ。戻り値は移した件数。"""
    done = [t for t in tasks if t.get("status") in ("完了", "取下")]
    if not done:
        return 0
    arch = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    arch.extend(done)
    ARCHIVE.write_text(json.dumps(arch, ensure_ascii=False, indent=1), encoding="utf-8")
    tasks[:] = [t for t in tasks if t.get("status") not in ("完了", "取下")]
    return len(done)


def bump_carry(tasks: list[dict]) -> int:
    """会議終了後に呼ぶ。未完了のまま残ったタスクの持ち越し回数を+1する。"""
    n = 0
    for t in tasks:
        if t.get("status", "進行中") in OPEN_STATUSES:
            t["carry"] = int(t.get("carry", 1)) + 1
            n += 1
    return n


# ------------------------------------------------------------
# Notion ブロック
# ------------------------------------------------------------
def _rt(text: str, bold: bool = False, color: str | None = None) -> dict:
    d = {"type": "text", "text": {"content": text}}
    ann = {}
    if bold:
        ann["bold"] = True
    if color:
        ann["color"] = color
    if ann:
        d["annotations"] = ann
    return d


def todo_block(t: dict, show_ai: bool = True) -> dict:
    """タスク1件を to_do ブロックにする。先頭の #id で台帳と突合する。
    チェックを入れる＝完了。"""
    status = t.get("status", "進行中")
    parts = [
        _rt(f"#{t['id']} ", True),
        _rt(f"{STATUS_TAG[status]} ", color=STATUS_COLOR[status]),
        _rt(f"[{t['cat']}] " if t.get("cat") else ""),
        _rt(t["task"], True),
        _rt(f"【{t['owner']}】"),
        _rt(f"｜初出 {t.get('since','')}" + (f"・持越{t['carry']}回" if int(t.get("carry", 1)) >= 2 else "") + (f"・期限 {t['due']}" if t.get("due") else ""), color="gray"),
    ]
    if show_ai and t.get("ai"):
        parts.append(_rt(f"｜AI: {t['ai']}", color="orange"))
    parts = [p for p in parts if p["text"]["content"]]
    return {"object": "block", "type": "to_do", "to_do": {"rich_text": parts, "checked": status == "完了"}}


def todo_blocks(tasks: list[dict], show_ai: bool = True) -> list[dict]:
    return [todo_block(t, show_ai) for t in tasks]


# ------------------------------------------------------------
# Notion → 台帳 同期
# ------------------------------------------------------------
_ID_RE = re.compile(r"^#(\d+)\b")


def sync_from_notion(page_url_or_id: str, meeting_date: str = "") -> dict:
    """Notionページ内の to_do を走査し、チェック済みのものを台帳で「完了」にする。
    戻り値: {"completed": [ids], "still_open": [ids], "unknown": [texts]}"""
    import notion_writer as nw
    tasks = load()
    blocks = nw.get_blocks(page_url_or_id, include_children=True)
    completed, still_open, unknown = [], [], []
    for b in blocks:
        if b.get("type") != "to_do":
            continue
        text = "".join(x.get("plain_text", "") for x in b["to_do"]["rich_text"])
        m = _ID_RE.match(text)
        if not m:
            unknown.append(text[:60])
            continue
        tid = int(m.group(1))
        if b["to_do"].get("checked"):
            if set_status(tasks, tid, "完了", when=meeting_date):
                completed.append(tid)
        else:
            still_open.append(tid)
    archived = archive_done(tasks)
    save(tasks)
    return {"completed": completed, "still_open": still_open, "unknown": unknown, "archived": archived}


if __name__ == "__main__":
    import sys
    tasks = load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for t in open_tasks(tasks):
            print(f"#{t['id']:>3} {STATUS_TAG[t['status']]} [{t['cat']}] {t['task']}【{t['owner']}】 初出{t['since']} 持越{t['carry']}")
        print(f"未完了 {len(open_tasks(tasks))} / 全 {len(tasks)}")
    elif cmd == "done":
        for a in sys.argv[2:]:
            print(set_status(tasks, int(a), "完了"))
        save(tasks)
    elif cmd == "sync":
        print(sync_from_notion(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""))
