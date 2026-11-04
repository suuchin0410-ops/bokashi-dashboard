# レンタル予約管理ツールの公開（Firebase Hosting）

- 公開先: Firebase プロジェクト `bokashi-ops-app` の Hosting サイト `bokashi-rental`
  - 管理画面 https://bokashi-rental.web.app （スタッフ用パスワードが必要）
  - お客様用 申込フォーム https://bokashi-rental.web.app/#apply （ログイン不要）
  - 本番化設計書 https://bokashi-rental.web.app/design.html
- OPSアプリのサイト（bokashi-ops-app.web.app）とは別サイト。OPSアプリのコードには触れない
- **保存先は共有データベース（同じ Firebase プロジェクトの Firestore）。** お客様がフォームを送ると
  `stores/store_bokashi/rentalBookings` に直接保存され、ログインしたスタッフの端末すべてで予約一覧に「Web申込」の仮予約として出る
  （2026-11-04〜。それ以前のブラウザ保存版は、ログイン後に「設定」→「データ」→「この端末に残っている予約を共有データベースへ移す」で移行できる）
- 設定（発行者名・登録番号・振込先・店舗メール）も `rentalSettings/store` に保存され、全端末で共通

## 仕組み（A案: 自動登録＋簡易ログイン）

| 誰が | できること | 根拠 |
|---|---|---|
| お客様（未ログイン） | 申込の作成だけ。内容の形と長さをルールで検査。読む・直す・消すはできない | es-ops の `firestore.rules` の `rentalWebRequest` |
| スタッフ（`crew@bokashi-ops.app` / 管理者 `staff@es-marketing.app` のパスワードログイン） | 予約と設定の読み書き | 同 `rentalStaff` |
| OPSアプリ | `rental*` は読まない・書かない | コレクション名を `rental` 接頭辞で分離 |

- ログイン画面はパスワード1つ（OPSアプリと同じ流儀。crew → admin の順に試す）。一度入れると、その端末・ブラウザでは次回から不要
- Firebase が読み込めない環境（claude.ai 上のコピー・オフライン）では、従来どおりそのブラウザの localStorage で動く（画面下に「保存先：このブラウザ」と出る）
- 申込が共有データベースに保存できなかったときだけ、お客様にはメール（取込コード付き）か電話での申込を案内する。
  その取込は「予約を登録」→「取込コードから（予備）」
- メール・カレンダー・請求書PDFは引き続き半自動（mailto / Google Calendar のテンプレート URL / 印刷）。自動化は `design.html` の本番化で

## 更新手順

```bash
cd docs/mockups/deploy
python3 build.py                      # 元ファイルを公開用に包み直す
firebase deploy --only hosting:rental # 公開
```

- `public/index.html` ← `../rental-space-tool.html`、`public/design.html` ← `../../strategy/rental-space-production-design.html`
- 元ファイルを直したら必ず `build.py` を通す（public/ は生成物）
- Firebase の設定値（apiKey 等）は `rental-space-tool.html` 冒頭の `<script type="module">` に書いてある（Web アプリの公開設定なので秘密ではない。守っているのはルール）

## Firestore ルール（es-ops リポジトリ側）

- ルールは es-ops リポジトリ（`ops-app/` → `Projects/es/es-ops`）の `firestore.rules` で管理する決まり。
  rental 用のブロックは **認証必須版 `firestore.rules`** と、**本番で動いている旧版 `docs/rollback/firestore.rules.before-auth`** の両方に同じ文面で入れてある
- 2026-11-04 時点で bokashi-ops-app の本番に出ているのは「旧版＋rental ブロック」。認証必須版はまだ出していない
  （出すと OPSアプリが止まる。切替は es-ops の `docs/AUTH_ROLLOUT.md` の順序で）。bokashi に出すときは旧版の方を使う
- テスト: es-ops で `npm run test:rules`（`tests/rules/rental.emu.ts` が両ファイルを検査）
- デプロイ（旧版＋rental を bokashi にだけ）:

```bash
cd "$(mktemp -d)" && cp "/Users/suzukishinya/Desktop/Claude Code/Projects/es/es-ops/docs/rollback/firestore.rules.before-auth" firestore.rules && printf '{ "firestore": { "rules": "firestore.rules" } }\n' > firebase.json && firebase deploy --only firestore:rules --project bokashi-ops-app
```

## 運用開始チェックリスト

1. **Firebase コンソールで Authentication を有効化**（鈴木の操作・初回のみ）: https://console.firebase.google.com/project/bokashi-ops-app/authentication → 「始める」→ Sign-in method で **メール / パスワード** を有効化
2. スタッフ用アカウントを作る（鈴木の操作。パスワードは12文字以上、チャットや文書に書かない）:
   es-ops で `node scripts/auth/create-shared-accounts.cjs --project bokashi-ops-app --email crew@bokashi-ops.app --apply`
   （OPSアプリの認証切替でも同じアカウントを使う予定なので、ここで決めたパスワードがそのまま OPS のパスワードになる）
3. 店舗の端末で https://bokashi-rental.web.app を開き、パスワードでログイン → 「設定」で店舗名・発行者名・登録番号・住所・電話・店舗メール・振込先を保存（全端末で共通になる）
4. 「設定」→「サンプルデータを消す」（上部の「サンプルデータ表示中」が消えればOK）。旧ブラウザ保存版の予約があれば「この端末に残っている予約を共有データベースへ移す」
5. 試しにお客様用フォーム（/#apply）から1件申し込み → 予約一覧に「Web申込」の仮予約が出る → 日程確定（Googleカレンダーの保存先を店舗用カレンダーにする）→ 確認メール作成、まで一度通す
6. お客様には https://bokashi-rental.web.app/#apply を案内（bokashi.ink の Rental ページからリンク）。朝と夕方に予約一覧の「仮予約」を確認する運用にする（新着の通知はまだ無い）

## ローカルでの動作確認（本番データに触れない）

- `.claude/launch.json` の `rental` が `public/` を http://localhost:8766 で配信する
- Firebase エミュレータ（auth 9099 / firestore 8080）を `firestore.rules.before-auth` で起動し、`http://localhost:8766/?emu=1` を開くとエミュレータにつながる（`?emu=1` は localhost でしか効かない）
- エミュレータの Auth にテスト用の `crew@bokashi-ops.app` を作ってログインする（本番のアカウントとは無関係）

## 既知の制約（本番化で解消）

- 新着の Web 申込の通知（メール・Chatwork）はまだ無い。一覧の「仮予約」タイルと、開いているときのトーストで気づく
- 申込の作成は未ログインで許しているため、いたずら投稿は防げない（内容の検査と長さ制限のみ）。増えるようなら App Check か Functions 経由（設計書 5章）
- メール・カレンダーの完全自動化、請求書 PDF の自動添付は `design.html` の本番化で実装する
- Codex（OpenAI）によるレビュー（ロジック2回・UI/UX 2回）は `../codex-review-2026-11-03.md` に保存。未対応の指摘もそこに残っている
