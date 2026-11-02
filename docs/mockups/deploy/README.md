# レンタル予約管理モックの公開（Firebase Hosting）

- 公開先: Firebase プロジェクト `bokashi-ops-app` の Hosting サイト `bokashi-rental`（https://bokashi-rental.web.app）
- OPSアプリのサイト（bokashi-ops-app.web.app）とは別サイト。OPSアプリには触れない
- `public/index.html` = `../rental-space-tool.html` を、`public/design.html` = `../../strategy/rental-space-production-design.html` を、それぞれ `<!doctype html>` と viewport で包んだもの
- 更新手順: 元ファイルを直してから、このフォルダで `python3` の wrap を再実行し `firebase deploy --only hosting:rental`
- Firebase 上では claude.ai の共有DBは使えないため、モックの保存先はブラウザごと（localStorage）になる
