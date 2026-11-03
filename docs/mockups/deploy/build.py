#!/usr/bin/env python3
"""公開用 HTML を組み立てる。

- public/index.html  ← ../rental-space-tool.html（予約管理ツール＋お客様用フォーム）
- public/design.html ← ../../strategy/rental-space-production-design.html（本番化設計書）

元ファイルは claude.ai の Artifact 形式（<title> と <style> から始まり、doctype や <head> を持たない）なので、
通常のブラウザ向けに doctype・charset・viewport・最小リセットで包む。
使い方: このフォルダで `python3 build.py` → `firebase deploy --only hosting:rental`
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
SOURCES = {
    "index.html": HERE.parent / "rental-space-tool.html",
    "design.html": HERE.parent.parent / "strategy" / "rental-space-production-design.html",
}
RESET = (
    "*,*::before,*::after{box-sizing:border-box}html{-webkit-text-size-adjust:100%}"
    "body{margin:0;min-height:100vh;-webkit-font-smoothing:antialiased}"
    "img,svg,video{max-width:100%;height:auto}[hidden]{display:none!important}"
)


def wrap(src: str) -> str:
    cut = src.find("</style>")
    if cut < 0:
        raise SystemExit("元ファイルに </style> が見つかりません")
    cut += len("</style>")
    head, body = src[:cut], src[cut:]
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        f"<style>{RESET}</style>\n{head}\n</head><body>{body}\n</body></html>\n"
    )


def main() -> None:
    PUBLIC.mkdir(exist_ok=True)
    for name, src in SOURCES.items():
        out = PUBLIC / name
        out.write_text(wrap(src.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"{out.relative_to(HERE)}  ←  {src.name}  ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
