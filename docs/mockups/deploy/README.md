# レンタル予約管理ツールの公開（Firebase Hosting）

- 公開先: Firebase プロジェクト `bokashi-ops-app` の Hosting サイト `bokashi-rental`
  - 管理画面 https://bokashi-rental.web.app
  - お客様用 申込フォーム https://bokashi-rental.web.app/#apply
  - 本番化設計書 https://bokashi-rental.web.app/design.html
- OPSアプリのサイト（bokashi-ops-app.web.app）とは別サイト。OPSアプリには触れない
- 公開版の保存先はブラウザごと（localStorage）。店舗の決まった端末・ブラウザで使い、「設定」からバックアップを取る

## 更新手順

```bash
cd docs/mockups/deploy
python3 build.py                      # 元ファイルを公開用に包み直す
firebase deploy --only hosting:rental # 公開
```

- `public/index.html` ← `../rental-space-tool.html`、`public/design.html` ← `../../strategy/rental-space-production-design.html`
- 元ファイルを直したら必ず `build.py` を通す（public/ は生成物）

## 公開前に決めておく値

`rental-space-tool.html` の `const DEFAULTS = {...}` にある **`email`（店舗メールアドレス）** は、お客様用フォームの送信先になる。
お客様の端末では店舗側の「設定」は読めないため、ここに書いて公開する必要がある。空のままだと、フォームは「内容をコピーして店舗へ送ってください」という案内になる。

発行者名・登録番号・振込先は、管理画面の「設定」で入れる（端末のブラウザに保存される）。

## 運用開始チェックリスト

1. `rental-space-tool.html` の `DEFAULTS.email` に店舗の実在メールアドレスを入れ、`python3 build.py` → `firebase deploy --only hosting:rental`
2. 店舗の管理用端末（1台・1ブラウザ・1タブ）で https://bokashi-rental.web.app を開き、「設定」で店舗名・発行者名・登録番号・住所・電話・店舗メール・振込先を保存
3. 「設定」→「サンプルデータを消す」（上部の「サンプルデータ表示中」が消えればOK）
4. 試しに「新規予約」で1件登録 → 日程確定（Googleカレンダーの保存先を店舗用カレンダーにする）→ 確認メール作成、まで一度通す
5. 閉店時に「設定」→「バックアップを保存（JSON）」。端末を替えるときは「復元」
6. お客様には https://bokashi-rental.web.app/#apply を案内（bokashi.ink の Rental ページからリンク）。管理用のブラウザをお客様に触らせない

## 既知の制約（本番化で解消）

- 保存はブラウザ内のみ。複数端末での共有、メール・カレンダーの完全自動化、請求書 PDF の自動添付は `design.html` の本番化で実装する
- Codex（OpenAI）によるレビュー2回分は `../codex-review-2026-11-03.md` に保存。未対応の指摘もそこに残っている
