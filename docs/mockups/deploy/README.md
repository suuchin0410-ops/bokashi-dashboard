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

1. ~~Firebase コンソールで Authentication を有効化~~ **済（2026-11-04）**: メール / パスワード を有効化。承認済みドメインに bokashi-rental.web.app を追加済み
2. ~~スタッフ用アカウントを作る~~ **済（2026-11-04）**: `crew@bokashi-ops.app` を作成。パスワードは鈴木の PC の `~/.config/bokashi-rental/staff-password.txt`（リポジトリ外・本人のみ読める）。
   店長には口頭か電話で伝える。変更は es-ops で `node scripts/auth/create-shared-accounts.cjs --project bokashi-ops-app --email crew@bokashi-ops.app --apply --reset`
   （OPSアプリの認証切替でも同じアカウントを使う予定なので、このパスワードがそのまま OPS のパスワードになる）
3. ご利用時間は平日 12:00〜21:00／土日祝 10:00〜21:00（フォームの判定も同じ）。変えるときは `rental-space-tool.html` の `withinHours` と文言を直す
4. 店舗の端末で https://bokashi-rental.web.app を開き、パスワードでログイン → 「設定」で店舗名・発行者名・登録番号・住所・電話・店舗メール・振込先を保存（全端末で共通になる）
5. 「設定」→「サンプルデータを消す」（上部の「サンプルデータ表示中」が消えればOK）。旧ブラウザ保存版の予約があれば「この端末に残っている予約を共有データベースへ移す」
6. 試しにお客様用フォーム（/#apply）から1件申し込み → 予約一覧に「Web申込」の仮予約が出る → 日程確定（Googleカレンダーの保存先を店舗用カレンダーにする）→ 確認メール作成、まで一度通す
7. お客様には https://bokashi-rental.web.app/#apply を案内（bokashi.ink の Rental ページからリンク）。新着は Slack の `#予約通知` に届くので、通知を見たら予約一覧で対応する

## Slack 通知（Cloud Functions・codebase `rental`）

- `functions/` に Firestore トリガー `notifyRentalRequest` がある。`stores/store_bokashi/rentalBookings` に **Web 申込（source: web）** が作られたら、
  Slack の Incoming Webhook（`#予約通知`）に受付番号・希望日時・人数・内容・連絡先・見積・管理画面リンクを投稿し、文書に `slackNotifiedAt` を記録する（二重投稿防止）。
  スタッフが「予約を登録」で入れた分は通知しない
- 前提: bokashi-ops-app が **Blaze プラン**（Functions と Secret Manager を使うため。2026-11-04 に Blaze 化・Secret 登録・デプロイ済み。月数十件なら無料枠内）
- Slack 側は **済（2026-11-04）**: ワークスペース「bokashiと丸大の情報共有」に Slack アプリ `bokashi Rental Notify`（App ID A0CE8U2NRHV、https://api.slack.com/apps/A0CE8U2NRHV/incoming-webhooks）を作り、
  Incoming Webhook を `#予約通知` に追加。テスト投稿で 200 を確認。URL は鈴木の PC の `~/.config/bokashi-rental/slack-webhook-rental.txt`（リポジトリ外・本人のみ読める）
- Webhook URL は Secret Manager の `SLACK_WEBHOOK_RENTAL` に入れてある（version 1。リポジトリ・チャットには書かない）。作り直すときは:

```bash
cd docs/mockups/deploy && firebase functions:secrets:set SLACK_WEBHOOK_RENTAL --project bokashi-ops-app --data-file ~/.config/bokashi-rental/slack-webhook-rental.txt
```

- デプロイ（この codebase だけ。引数なしの `firebase deploy` は打たない）:

```bash
cd docs/mockups/deploy && firebase deploy --only functions:rental --project bokashi-ops-app
```

- ローカルテスト（本文と POST の確認。本番に触れない）: `cd docs/mockups/deploy/functions && npm test`
- ログ: `firebase functions:log --only notifyRentalRequest --project bokashi-ops-app`
- Webhook を作り直したときは `functions:secrets:set` をやり直してから再デプロイ（Secret の新しい版は再デプロイで反映）

## ローカルでの動作確認（本番データに触れない）

- `.claude/launch.json` の `rental` が `public/` を http://localhost:8766 で配信する
- Firebase エミュレータ（auth 9099 / firestore 8080）を `firestore.rules.before-auth` で起動し、`http://localhost:8766/?emu=1` を開くとエミュレータにつながる（`?emu=1` は localhost でしか効かない）
- エミュレータの Auth にテスト用の `crew@bokashi-ops.app` を作ってログインする（本番のアカウントとは無関係）

## 既知の制約（本番化で解消）

- 新着の Web 申込は `#予約通知`（Slack）に届く（2026-11-04 に Functions をデプロイ・通し確認済み）。Slack を見ない時間帯は一覧の「仮予約」タイルでも分かる
- 申込の作成は未ログインで許しているため、いたずら投稿は防げない（内容の検査と長さ制限のみ）。増えるようなら App Check か Functions 経由（設計書 5章）
- メール・カレンダーの完全自動化、請求書 PDF の自動添付は `design.html` の本番化で実装する
- Codex（OpenAI）によるレビュー（ロジック2回・UI/UX 2回）は `../codex-review-2026-11-03.md` に保存。未対応の指摘もそこに残っている
