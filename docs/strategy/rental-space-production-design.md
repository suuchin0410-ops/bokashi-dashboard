---
date: 2026-11-02
type: 設計書（本番化の方針。コードは含まない）
subject: bokashi Base レンタルスペース予約管理（申込フォーム〜請求書送信）の本番化
status: 案。オーナー・舜さんの判断待ち
related:
  - docs/mockups/rental-space-tool.html（モック。https://claude.ai/artifact/KffbGYKm1YMN6ZaTTXmCnj、お客様用フォームは同URLの #apply）
  - ops-app/CLAUDE.md・ops-app/docs/AUTH_DESIGN.md・ops-app/docs/AUTH_ROLLOUT.md（OPSアプリ側の運用ルールと認証の切替手順）
---

# bokashi Base レンタルスペース予約管理 本番化設計書

## 0. 結論（先に）

- **アプリは OPSアプリとは別に作り、サーバー（Firebase プロジェクト `bokashi-ops-app`）は共通にします。**
  Hosting は同じプロジェクト内に**別サイト**を1つ足す形を推奨します（別プロジェクトは作りません）。
- **お客様の申込は bokashi.ink の Rental Space ページから、予約管理アプリの公開フォームへ**誘導します。
  フォームの送信は Cloud Functions が受け取り、Firestore に「仮予約」として入れ、受付メールと店舗通知を出します。
- **カレンダーは Google Calendar API、メールは Gmail API** を推奨します。
  店舗のメールは Google Workspace（manx-loaghtan.co）で運用されているため、追加のサービス契約なしで店舗アドレスから送れ、送信履歴も Gmail に残ります。
- **請求書は Functions で PDF を作り、Cloud Storage に保存してメールに添付**します。適格請求書の必須項目を満たす書式にし、番号は年ごとの連番、支払期限は発行日の翌月末です。
- **まず「台帳＋公開フォーム＋受付メール」だけを本番にし（第1段階）、カレンダー・確認メール・請求書送信の自動化を第2段階**で足します。
  第1段階でも、カレンダー登録と確認メールは「リンクを開く」「本文をコピーする」で手作業で回せます。
- **前提条件が2つあります。**
  1. OPSアプリ側で実装済み・本番未適用の「ログイン必須ルール」を先に本番へ適用すること。予約データはお客様の氏名・連絡先を含むため、今の「誰でも読める」ルールのままでは出せません（4-4 参照）。
  2. `bokashi-ops-app` を従量課金プラン（Blaze）にすること。今は課金未設定で、Cloud Functions が使えません（2-5 参照）。

判断していただきたいことは 10 章の「未確定事項」にまとめています。

---

## 1. この文書の前提

### 1-1. 業務の流れ（モックで固めたもの）

| # | 誰が | やること | 自動で起きること |
|---|---|---|---|
| 0 | お客様 | Web フォームで希望日時・プラン・連絡先を送る | 受付番号を発行、受付メールをお客様へ、新着通知を店舗へ |
| 1 | 店舗 | 新着を確認。電話・来店の申込は「新規予約」から入力 | 見積の自動計算 |
| 2 | 店舗 | 「日程を確定」 | Google カレンダーに予定を作成（変更・取消も同期） |
| 3 | 店舗 | 「確認メールを送る」 | 確定内容をお客様へメール |
| 4 | 店舗 | 当日終了後に実績（人数・終了時刻・延長・追加）を入力 | 確定額を再計算 |
| 5 | 店舗 | 請求先を確認して「請求書を送信」 | 番号を採番、PDF を生成、お客様へメール送信 |
| 6 | 店舗 | 入金を確認 | 期限超過を一覧で目立たせる |

状態は `仮予約 → 日程確定 → 共有済み → 利用終了 → 請求済み → 入金済み` の6段階です。本番ではこれに **`キャンセル`** を足します（モックにはありません）。

### 1-2. 料金（税込。「bokashi Base ケータリングプラン」資料より）

| 項目 | 金額 |
|---|---|
| スペース利用料 | 1時間 ¥15,400（1時間未満は切り上げ）、1日上限 ¥154,000 |
| 軽食 | ¥2,000／人 |
| パーティ | ¥3,000／人 |
| 飲み放題 | +¥2,000／人 |
| ゴミ回収 | ¥1,100 |
| 無断延長 | ¥10,000／30分 |

利用可能時間はモックでは「平日 18:00〜21:00／土日祝 10:00〜21:00」、席数は 28 席としています。実際の運用と違えば直します（10章）。

### 1-3. 既存のサーバー側（調べた結果）

| 項目 | 現状 |
|---|---|
| Firebase プロジェクト | `bokashi-ops-app`。Hosting サイトは `bokashi-ops-app` の1つだけ（https://bokashi-ops-app.web.app） |
| Firestore | `stores/store_bokashi/` 配下に items・sessions・purchases・dailySales・sales など（OPSアプリの在庫・仕入・売上） |
| 認証 | Firebase Authentication は有効化済み。方式は役割別の共有アカウント（現場用 `crew@bokashi-ops.app`、管理者 `staff@es-marketing.app`）。**ログイン必須のルールは実装済み・本番未適用**（es-ops リポジトリの `feature/firestore-auth-gate`） |
| Cloud Functions | **`bokashi-ops-app` には1本もありません。** bokashi 向けの既存処理（Drive からの売上取込）は `es-ops-app` 側の Functions が別プロジェクトとして `bokashi-ops-app` の Firestore に書いています |
| 料金プラン | **`bokashi-ops-app` は課金未設定（Spark）です**（2026-11-02 確認。`es-ops-app` は課金あり）。Cloud Functions と Secret Manager は従量課金プラン（Blaze）でないと使えません。対応は 2-5 |
| セキュリティルール | `firestore.rules` / `storage.rules` は **es-ops リポジトリが唯一の正**で、es-ops-app と bokashi-ops-app に同じファイルをデプロイする運用です。他のリポジトリからルールをデプロイしてはいけません（過去に事故あり） |
| 公式サイト | bokashi.ink は STUDIO 製。`/rentalspace`（Rental Space ページ）が既にあります |
| 店舗メール | `manx-loaghtan.co` は Google Workspace（MX・SPF が Google）。`bokashi.ink` にメールの設定はありません |
| 店舗カレンダー | 鈴木さんのアカウントから見える範囲に bokashi 用のカレンダーはありません。新しく作る前提です |

---

## 2. 全体構成

### 2-1. 構成図

```
お客様                                     店舗（舜さん・スタッフ・鈴木さん）
  │                                               │
  │ bokashi.ink/rentalspace（STUDIO）              │ スマホ・PC
  │   └ 「予約を申し込む」ボタン or 埋め込み         │
  ▼                                               ▼
┌──────────────────────────────────────────────────────────────┐
│ 予約管理アプリ「bokashi 予約管理」（新規・別リポジトリ）              │
│   Hosting サイト: bokashi-rental（bokashi-ops-app プロジェクト内）  │
│   /apply   … 公開フォーム（ログイン不要）                           │
│   /        … 管理画面（ログイン必須。予約一覧・新規・詳細・設定）      │
└──────────────┬───────────────────────────────┬───────────────┘
               │ HTTPS（App Check 付き）          │ Firestore SDK（ログイン済み）
               ▼                               ▼
┌──────────────────────────────────────────────────────────────┐
│ 共通 Firebase プロジェクト bokashi-ops-app                        │
│  ├ Authentication（OPSアプリと同じ共有アカウント）                  │
│  ├ Firestore  stores/store_bokashi/                              │
│  │    ├ items, purchases, dailySales …（OPSアプリ。触らない）       │
│  │    └ rentalBookings / rentalInvoices / rentalSettings（新設）    │
│  ├ Cloud Storage  stores/store_bokashi/rentalInvoices/*.pdf（新設）│
│  └ Cloud Functions  codebase "rental"（新設）                      │
│       submitRentalRequest / confirmBooking / sendConfirmation /  │
│       issueInvoice / resendInvoice / cancelBooking / 日次ジョブ    │
└──────┬───────────────┬──────────────────┬─────────────────────┘
       │               │                  │
       ▼               ▼                  ▼
 Google Calendar    Gmail API          Chatwork
 （店舗カレンダー）  （店舗アドレスから送信） （店舗の通知ルーム）
```

### 2-2. 「別アプリ・共通サーバー」の切り分け

| 要素 | OPSアプリと共通にするもの | 予約管理アプリが独自に持つもの |
|---|---|---|
| Firebase プロジェクト | `bokashi-ops-app` | — |
| 認証 | Firebase Auth と共有アカウント（舜さんのパスワードは1つのまま） | ログイン画面（OPSアプリの AuthGate と同じ作り） |
| Firestore | 同じデータベース。`stores/store_bokashi/` の下 | `rental` で始まる専用コレクション（4章） |
| セキュリティルール | es-ops リポジトリの `firestore.rules` / `storage.rules` に rental 用の match を追記し、es-ops の手順でデプロイ | — |
| Cloud Functions | プロジェクトは同じ | 別コードベース `rental`（デプロイは `--only functions:rental` に限定） |
| Hosting | 同じプロジェクト | 別サイト `bokashi-rental` |
| ソースコード | — | 新しいリポジトリ（es-ops のコードは参照のみ。コピーして流用はしてよい） |
| 外部連携の鍵 | Secret Manager（同じプロジェクト） | Calendar・Gmail 用の鍵は予約管理用に新しく登録 |

**OPSアプリのコードは一切変更しません。** OPSアプリ側に必要なのは `firestore.rules` / `storage.rules` への追記だけで、それも es-ops リポジトリで行います。

### 2-3. Hosting を「別サイト」にするか「別プロジェクト」にするか

| 観点 | A. 同じプロジェクトに別サイト（推奨） | B. 別 Firebase プロジェクト |
|---|---|---|
| オーナーの方針「アプリは別、サーバーは共通」 | 合う | アプリもサーバーも別になり、方針と違う |
| URL | `https://bokashi-rental.web.app`（任意のサイト名） | 同様に取れる |
| ログイン | OPSアプリと同じアカウント・同じパスワード | ユーザーを作り直す。パスワードが2本になる |
| データの行き来 | 同じ Firestore なので、将来レンタル売上を OPS の経営サマリーに載せるのが簡単 | プロジェクトをまたぐ読み書きに IAM 設定が要る（今の Drive 売上取込と同じ手間） |
| ルール管理 | es-ops の `firestore.rules` に追記（1ファイル運用を守る） | ルールは独立。ただし管理対象が増える |
| 事故の切り分け | 予約アプリの不具合が OPS のデータに波及しないよう、コレクション名とルールで分離する（4章） | 物理的に分離される |
| 料金 | 同じ請求。ただし `bokashi-ops-app` は今は課金未設定なので、Blaze への切替が要る（2-5） | 請求先が増える |
| 手間 | 小さい | Auth・Functions・IAM を一式作る |

**A を推奨します。** 分離はコレクション名（`rental` 接頭辞）とルールで担保し、デプロイは予約アプリのリポジトリから `hosting:bokashi-rental` と `functions:rental` だけに限定すれば、OPS側を壊す経路がありません。

### 2-4. 技術の選択（OPSアプリと揃える）

- フロント: React + TypeScript + Vite + Tailwind（OPSアプリと同じ。ログイン画面・Firebase 初期化はコピーして流用）
- Functions: Node.js 22、`firebase-functions` v2、リージョン `asia-northeast1`（es-ops と同じ）
- 外部 API: `googleapis`（Calendar・Gmail）、PDF 生成ライブラリ（7章）
- 鍵: Secret Manager（`defineSecret`。es-ops と同じ流儀）

### 2-5. Cloud Functions をどのプロジェクトに置くか

`bokashi-ops-app` は課金未設定（Spark プラン）のため、今のままでは Functions も Secret Manager も使えません。選択肢は2つです。

| 観点 | A. `bokashi-ops-app` を Blaze にして、そこに置く（推奨） | B. `es-ops-app` の Functions に置き、別プロジェクトとして `bokashi-ops-app` に書く |
|---|---|---|
| 前例 | なし | あり（Drive 売上取込 `pullBokashiSalesFromDrive` が同じ方式） |
| 必要な作業 | Firebase コンソールで `es-ops-app` と同じ請求先アカウントに紐づける（オーナーまたは鈴木さん。数分） | `es-ops-app` のサービスアカウントに `bokashi-ops-app` の Firestore・Storage の書き込み権限を追加（既に Firestore は付与済み） |
| 費用 | 予約件数の規模（月数十件）では無料枠に収まる見込み。請求先が同じなら実質変わらない | 変わらない |
| 分離 | 予約アプリの Functions は bokashi のプロジェクトで完結。鍵・ログ・権限も bokashi 側にまとまる | bokashi の処理が es のプロジェクトに同居し、es-ops リポジトリの 44 本の Functions と同じ場所にコードを置くことになる（「OPSアプリのコードは変更しない」方針と相性が悪い） |
| 公開フォームの受け口（App Check） | `bokashi-ops-app` の App Check をそのまま使える | App Check は Firebase プロジェクト単位のため、`es-ops-app` 側で bokashi のサイトを登録する必要がある |

**A を推奨します。** 「サーバーは共通」の方針どおり bokashi のプロジェクトにまとまり、es 側に手を入れずに済みます。
Blaze 化は 10 章の未確定事項 8 として判断をお願いします。

---

## 3. 画面と状態遷移

### 3-1. 画面一覧

| 画面 | 利用者 | 内容 |
|---|---|---|
| `/apply` 公開フォーム | お客様 | 入力 → 確認 → 送信完了（受付番号表示）。モックの「申込フォーム」そのまま |
| 予約一覧 | 店舗 | KPI（Web申込・未対応／今月の予約／これからの予約／請求書未送信／入金待ち）、状態フィルター、一覧 |
| 新規予約 | 店舗 | 電話・来店分の入力。見積の自動計算 |
| 予約詳細 | 店舗 | 6段階のパイプライン、各段階の操作、履歴（ログ）、請求書プレビュー |
| 設定 | 管理者 | 発行者情報・登録番号・振込先・送信元・カレンダー ID・料金表・利用可能時間（本番で新設） |

### 3-2. 状態と、状態を進める操作

| 状態 | 進める操作 | 実行場所 | 副作用 |
|---|---|---|---|
| （Web申込） | フォーム送信 | Functions `submitRentalRequest` | 仮予約を作成、受付メール、店舗通知 |
| 仮予約 | 日程を確定 | Functions `confirmBooking` | カレンダーに予定作成（重複チェック付き） |
| 日程確定 | 確認メールを送る | Functions `sendConfirmation` | Gmail で送信 |
| 共有済み | 実績を入力 | 管理画面から Firestore に直接 | 確定額の再計算 |
| 利用終了 | 請求書を送信 | Functions `issueInvoice` | 採番・PDF・Storage 保存・Gmail 送信 |
| 請求済み | 入金を確認 | 管理画面から直接 | — |
| 入金済み | — | — | 完了 |
| どの状態からも | キャンセル | Functions `cancelBooking` | カレンダー削除、（請求済みなら請求書の取消） |
| 日程確定・共有済み | 内容を修正 | 管理画面から直接。日時変更時は Functions `updateCalendar` | カレンダー更新、（共有済みなら確認メール再送を促す） |

**外部に影響する操作（カレンダー・メール・採番）は必ず Functions 経由**にします。理由は、失敗をその場で画面に返せること、鍵をブラウザに置かないこと、採番の重複を防げることです。副作用のない更新（実績入力・入金確認・メモ）はブラウザから Firestore に直接書きます。

---

## 4. Firestore の設計

### 4-1. 命名の方針（OPSアプリと衝突させない）

- すべて `stores/store_bokashi/` の下に置き、コレクション名を **`rental` で始めます**。
- **`reservations` という名前は使いません。** es-ops の `firestore.rules` には既に `stores/{storeId}/reservations`（es の予約通知メール取込。管理者のみ読める）が定義されており、同じ名前を使うと権限が意図と違うものになります。
- OPSアプリは `rental*` を読まず、予約管理アプリは `rental*` 以外を書きません。

### 4-2. コレクション

#### `rentalBookings/{bookingId}` — 予約台帳（1予約1文書）

| フィールド | 型 | 内容 |
|---|---|---|
| `id` | string | `R-2026-001` 形式。年ごとの連番（採番は 4-3） |
| `source` | `web` / `staff` | 申込経路 |
| `receiptNo` | string | Web 申込の受付番号 `RQ-261102-001`（staff は空） |
| `status` | `draft` / `confirmed` / `shared` / `done` / `invoiced` / `paid` / `cancelled` | 状態 |
| `date`, `date2` | string (YYYY-MM-DD) | 第1希望・第2希望（確定後は `date` が確定日） |
| `start`, `end` | string (HH:MM) | 予定の開始・終了 |
| `people` | number | 予定人数 |
| `kind` | string | 用途（会議・研修／交流会・パーティー／…） |
| `purpose` | string | 内容（一言） |
| `plan` | `space` / `light` / `party` | プラン |
| `drink`, `trash`, `tour` | boolean | 飲み放題・ゴミ回収・見学希望 |
| `customer` | map | `{ name, org, email, phone }` |
| `note` | string | 要望・アレルギー等（フォームの3欄を結合） |
| `estimate` | map | 申込時点の見積 `{ lines[], total, tax }`（後で料金が変わっても申込時の金額が残る） |
| `calendar` | map / null | `{ calendarId, eventId, createdAt, updatedAt }` |
| `sharedAt` | timestamp / null | 確認メール送信日時 |
| `actual` | map / null | `{ people, end, ext30, trash, extras: [{label, amount}] }` |
| `billing` | map / null | `{ org, name, email }` 請求先（予約者と違ってよい） |
| `invoiceId` | string / null | 最新の請求書 `rentalInvoices` の文書 ID |
| `paidAt` | string / null | 入金確認日 |
| `cancelledAt`, `cancelReason` | — | キャンセル情報 |
| `createdAt`, `updatedAt`, `updatedBy` | — | 監査用 |

#### `rentalBookings/{bookingId}/events/{eventId}` — 履歴（追記のみ）

`{ at, actor('system' | ログインメール), type('submitted' | 'confirmed' | 'mailSent' | …), text, meta }`。
モックの「ログ」に相当します。配列ではなくサブコレクションにするのは、同時更新で消えないようにするためです。

#### `rentalInvoices/{invoiceNo}` — 請求書（発行後は不変）

| フィールド | 内容 |
|---|---|
| `no` | `INV-2026-0001`（文書 ID と同じ） |
| `bookingId` | 元の予約 |
| `issuedDate`, `dueDate` | 発行日、支払期限（翌月末） |
| `issuer` | 発行時点の発行者情報の写し `{ name, corp, address, tel, regNo, bank }` |
| `billTo` | `{ org, name, email }` |
| `lines[]`, `subtotalExcl`, `tax`, `total`, `taxRate` | 明細と税額（7章の計算規則で確定した値） |
| `pdfPath` | Storage のパス |
| `sentAt`, `gmailMessageId`, `resentAt[]` | 送信記録 |
| `status` | `issued` / `paid` / `voided`（取消） |
| `voidedAt`, `voidReason`, `replacedBy` | 取消・再発行の記録 |

請求書は**発行後に書き換えません**。金額を直すときは取消（`voided`）して新しい番号で再発行し、両方を残します（適格請求書の写しの保存義務に合わせるため）。

#### `rentalSettings/{docId}` — 設定（管理者のみ）

- `issuer`: 発行者名・住所・電話・登録番号・振込先・送信元アドレス・Reply-To
- `pricing`: 料金表（1-2 の値。変更履歴を持つ）
- `hours`: 利用可能時間・席数の上限
- `calendar`: 店舗カレンダーの ID
- `notify`: Chatwork ルーム ID など

#### `rentalCounters/{year}` — 採番用

`{ booking: 16, receipt: 205, invoice: 12 }`。Functions のトランザクションで +1 してから使います（4-3）。

### 4-3. 採番

| 対象 | 形式 | 方法 |
|---|---|---|
| 予約 ID | `R-YYYY-NNN` | Functions のトランザクションで `rentalCounters/{year}.booking` を加算 |
| 受付番号 | `RQ-YYMMDD-NNN` | 同上 `.receipt`（モックは乱数。本番は連番で重複を排除） |
| 請求書番号 | `INV-YYYY-NNNN` | 同上 `.invoice`。**欠番を出さない・再利用しない** |

スタッフが「新規予約」をブラウザから作る場合も、ID の採番だけは Functions（`allocateBookingId`）を呼ぶか、最初から Functions 経由で作ります。

### 4-4. セキュリティルールの方針

es-ops の `firestore.rules` にある `canUseStore(storeId)`（管理者か、その店舗の現場アカウント）をそのまま使います。

| コレクション | 読み | 書き |
|---|---|---|
| `rentalBookings` | `canUseStore('store_bokashi')` | 同左。ただし `status` を `invoiced` / `paid` 以外から `invoiced` へ変える更新、`invoiceId` の変更、`calendar` の変更はクライアントから禁止（Functions の Admin SDK だけが行う） |
| `rentalBookings/*/events` | 同上 | create のみ。update / delete は禁止 |
| `rentalInvoices` | 同上 | クライアントは `status: paid` への更新（入金確認）だけ許可。作成・取消は Functions のみ |
| `rentalSettings` | `canUseStore` | `admin()` のみ |
| `rentalCounters` | 禁止 | 禁止（Functions のみ） |
| 未ログイン（お客様） | すべて禁止 | すべて禁止（フォームは Functions 経由。5章） |

Storage（請求書 PDF）: `stores/{storeId}/rentalInvoices/**` は `canUseStore` のみ読める。書き込みは Functions のみ。削除は禁止（保存義務）。

**ルールは es-ops リポジトリで変更し、`npm run test:rules`（エミュレータのテスト）に rental 用のケースを足してから、es-ops の手順（`docs/AUTH_ROLLOUT.md`、`CLAUDE.md` の「firestore.rules デプロイ時の注意」）でデプロイします。** 予約管理アプリのリポジトリからルールをデプロイすることはしません。

**前提条件:** 今の本番（bokashi-ops-app）のルールは `stores/{storeId}/{document=**}` を誰にでも開放する旧版です。この状態で `rentalBookings` を作ると、お客様の氏名・電話・メールが認証なしで読めてしまいます。したがって、**予約管理アプリの本番投入は「ログイン必須ルールの本番適用」の後**、または**同時**に行います。ルール切替の手順書は es-ops 側にあり、鈴木さんの承認待ちです。

### 4-5. 個人情報の扱い

- 読めるのは店舗のログイン済みアカウントだけです（現場用・管理者用の2種）。
- 公開フォームは書き込み専用で、送信後にお客様がデータを読む経路はありません（受付番号はメールで控えてもらう）。
- 保存期間は、請求書は7年（法令）、予約台帳はそれに合わせて同じ期間とし、削除の仕組みは第3段階以降で検討します。

---

## 5. 公開フォームからの書き込みの受け方

### 5-1. フォームの置き場所

bokashi.ink は STUDIO で作られており、サーバー側の処理を置けません。そのため**フォーム本体は予約管理アプリの Hosting（`/apply`）に置き**、STUDIO の Rental Space ページからは次のどちらかでつなぎます。

| 方法 | 内容 | 向き・不向き |
|---|---|---|
| A. ボタンで遷移（推奨） | Rental Space ページに「予約を申し込む」ボタンを置き、`https://<アプリURL>/apply` を新しいタブで開く | 確実。見た目はフォーム側を bokashi.ink に合わせる（モックは既に合わせてあります） |
| B. 埋め込み | STUDIO の埋め込み（iframe）でページ内に表示 | 一体感はあるが、STUDIO のプランで埋め込みが使えるか、スマホでの高さ調整が要る。A を先に出し、後から足してもよい |

### 5-2. 送信の受け口

```
ブラウザ（/apply）
  │ POST  { 入力内容, appCheckToken }
  ▼
Functions  submitRentalRequest（HTTPS onRequest, asia-northeast1）
  1. CORS: 許可する Origin はアプリの URL と bokashi.ink だけ
  2. Firebase App Check（reCAPTCHA Enterprise / v3）でボットを弾く
  3. 入力検証: 必須項目・メール形式・日付が過去でない・終了>開始・
               利用可能時間内・人数の上限・文字数の上限
  4. 連投の抑制: 同一メール or IP から短時間に複数件は保留扱い
  5. トランザクションで予約 ID と受付番号を採番
  6. rentalBookings に status=draft, source=web で作成、events に記録
  7. 受付メールをお客様へ（Gmail API）
  8. 店舗へ通知（Chatwork のルームに1件投稿。メール通知でも可）
  9. 受付番号を返す → 完了画面に表示
```

**ブラウザから Firestore に直接書かせない理由:** 未ログインの create を許可するとスパムや改ざんの入口になり、採番もメール送信もできません。Functions 1本にまとめると、ここを守れば全部守れます。

メール送信が一時的に失敗しても申込自体は受け付け（6→7 の順）、失敗は `events` に残して管理画面に「受付メール未送信」と出します。店舗が再送できます。

---

## 6. Google Calendar 連携

### 6-1. カレンダーと権限

1. 店舗の Google Workspace（manx-loaghtan.co）で、**レンタル専用のカレンダー「bokashi Base 貸切」を新しく作ります**（既存の個人カレンダーに混ぜない）。
2. そのカレンダーを、Functions が使う**サービスアカウント**のメールアドレスに「予定の変更権限」で共有します。
   - 共有先は `bokashi-ops-app` の Functions 既定サービスアカウント（`<プロジェクト番号>-compute@developer.gserviceaccount.com`）か、予約管理専用に作る SA。
   - カレンダーを SA に直接共有する方式なので、**Workspace のドメイン全体委任は不要**です（Gmail とは別。7章参照）。
3. カレンダー ID（`xxxx@group.calendar.google.com`）を `rentalSettings/calendar` に登録します。
4. 舜さん・スタッフは、このカレンダーを自分の Google カレンダーに追加して、スマホで予定を見ます。

### 6-2. 操作と API

| 操作 | API | 内容 |
|---|---|---|
| 日程確定 | `events.insert` | 件名「【貸切】{団体名 or 氏名}様 {人数}名」、日時（Asia/Tokyo）、場所「bokashi Base 2F」、説明（内容・プラン・担当者連絡先・備考・予約 ID）、`extendedProperties.private.bookingId` に予約 ID |
| 日時・人数・内容の修正 | `events.patch` | 同じ `eventId` を更新 |
| 仮予約に戻す／キャンセル | `events.delete` | 予定を削除し、`calendar` を null に |
| 重複の確認 | `freebusy.query` または `events.list` | 確定前に同じ時間帯の予定があれば警告（二重予約の防止） |

- `eventId` は予約文書の `calendar.eventId` に保存し、`extendedProperties` の予約 ID で逆引きもできるようにします（取りこぼしの修復用）。
- 作成に成功して Firestore 更新に失敗した場合に備え、`confirmBooking` は「既に同じ予約 ID の予定があれば作らずに使う」ようにします（二重作成の防止）。
- Calendar API はプロジェクトで有効化が必要です（10章）。

---

## 7. メール送信

### 7-1. 送る3種類

| 種類 | いつ | 宛先 | 内容 |
|---|---|---|---|
| 受付メール | Web 申込の直後（自動） | お客様 | 受付番号、入力内容の控え、「2営業日以内に連絡」、この時点では未確定の旨 |
| 確認メール | 店舗が「確認メールを送る」を押したとき | お客様 | 確定日時・内容・プラン・人数・見積明細、前日までの人数変更依頼、利用後に請求書を送る旨 |
| 請求書メール | 店舗が「請求書を送信」を押したとき | 請求先（`billing.email`） | 請求書番号・金額・支払期限、PDF 添付、振込依頼 |

本文のひな形はモックの文面をそのまま使います。送信前に画面でプレビューし、確認メールは一言添えられるようにします。

### 7-2. Gmail API と SendGrid の比較

| 観点 | Gmail API（推奨） | SendGrid |
|---|---|---|
| 前提 | 店舗の Google Workspace（あり） | SendGrid のアカウント作成と、送信ドメインの DNS 認証（SPF/DKIM） |
| 差出人 | 店舗の実在アドレス（例: `base@manx-loaghtan.co`）から送れる | 同じアドレスを名乗れるが、Gmail には送信履歴が残らない |
| 返信 | お客様の返信が店舗の Gmail にそのまま届き、送信済みも Gmail に残る。舜さんが普段の Gmail で経緯を追える | Reply-To を店舗アドレスにすれば返信は届くが、送った内容は SendGrid の画面でしか見られない |
| 添付（請求書 PDF） | 可能 | 可能 |
| 送信数の上限 | Workspace は 1 日 2,000 通（十分） | 無料枠 1 日 100 通、超えると有料 |
| 設定の難所 | **Workspace 管理コンソールでサービスアカウントにドメイン全体委任（`gmail.send` スコープ）を許可する**必要がある。管理者（オーナー側）の操作が1回要る | DNS の変更（bokashi.ink または manx-loaghtan.co）が要る |
| 費用 | 追加なし | 無料枠内なら無料 |
| 到達率 | 自ドメインの正規の送信で良好 | 認証すれば良好 |

**Gmail API を推奨します。** 決め手は「送信履歴と返信が店舗の Gmail に残る」ことです。
万一ドメイン全体委任を許可できない場合は、SendGrid（または Firebase の Trigger Email 拡張＋SMTP）に切り替えます。設計上はメール送信を1つの関数にまとめ、送信手段を差し替えられるようにしておきます。

### 7-3. 送信の記録

- 送信ごとに `events` と、請求書なら `rentalInvoices.sentAt` / `gmailMessageId` を記録します。
- 失敗は画面に出し、再送ボタンを用意します。自動で再試行はしません（二重送信の方が困るため）。

---

## 8. 請求書 PDF

### 8-1. 適格請求書（インボイス）の必須項目と対応

| 必須項目 | この請求書での扱い |
|---|---|
| ① 発行者の氏名または名称、登録番号 | `rentalSettings/issuer` の発行者名と `T` で始まる登録番号を記載（**未確定・10章**） |
| ② 取引年月日 | 利用日（`date`）。発行日も併記 |
| ③ 取引内容 | 明細行（スペース利用料 N時間／お食事 ○名／飲み放題／ゴミ回収／延長／追加）。軽減税率対象があれば行に明記 |
| ④ 税率ごとに区分した合計額と適用税率 | 「10% 対象 小計（税抜）」「10% 対象 合計（税込）」を記載 |
| ⑤ 税率ごとの消費税額 | 「消費税（10%）」を記載 |
| ⑥ 受領者の氏名または名称 | 請求先（団体名があれば団体名「御中」、担当者名を添える） |

- **税率は全項目 10% の前提**で設計します（店内でのサービス提供）。軽食・パーティ料理を持ち帰り扱いにする可能性があれば 8% の区分が必要になるため、10章で確認します。
- **消費税の計算:** 税込価格で明細を積み上げ、**請求書1枚につき税率ごとに1回だけ**税額を計算します（`税額 = 税込合計 − 税込合計 ÷ 1.1`、円未満は切り捨て。端数処理の方法は10章で確認）。行ごとに税額を出して足す方式は使いません。
- そのほか記載するもの: 請求書番号、発行日、支払期限（発行日の翌月末）、件名（利用日・用途）、振込先、振込手数料の負担、問い合わせ先電話番号。

### 8-2. 生成と保存

| 項目 | 方針 |
|---|---|
| 生成方法 | Functions 内で PDF ライブラリ（PDFKit など）に **Noto Sans JP を同梱**して描画。レイアウトはモックの請求書プレビューと同じ |
| 採用しない方法 | ブラウザを起動して HTML を PDF にする方法（Puppeteer）。メモリと起動時間が大きく、日本語フォントの扱いも手間 |
| 保存先 | Cloud Storage `stores/store_bokashi/rentalInvoices/INV-2026-0001.pdf`。削除しない（7年保存） |
| 配布 | メールに添付。管理画面からも開ける（ログイン必須の署名付き URL） |
| 再送 | 同じ PDF を再送（作り直さない） |
| 訂正 | 取消して再発行（8-3） |

### 8-3. 採番と訂正

- 番号は `INV-YYYY-NNNN`、年ごとに 1 から。トランザクションで採番し、欠番・重複を出しません。
- 金額や宛名の間違いは、**元の請求書を `voided`（取消）にして新番号で再発行**します。元の PDF も残し、取消理由を記録します。
- 支払期限は発行日の翌月末日。土日祝の繰り上げ・繰り下げはしません（必要なら10章で決める）。

---

## 9. 段階分けと工数の目安

工数は「鈴木さんが Claude Code を使って開発する」前提の目安で、確認・修正のやり取りを含みます。

### 第0段階: 準備（オーナー・舜さん側の作業が中心）

| 作業 | 誰が | 目安 |
|---|---|---|
| 10章の未確定事項を決める | オーナー・舜さん | 打合せ1回 |
| `bokashi-ops-app` を Blaze プランに切替（`es-ops-app` と同じ請求先に紐づけ） | オーナー承認・鈴木 | 0.5 日 |
| ログイン必須ルールの本番適用（es-ops の手順書どおり） | 鈴木（承認はオーナー） | 1 日 |
| 店舗カレンダー作成・SA へ共有、Calendar API 有効化 | 舜さん・鈴木 | 0.5 日 |
| Workspace でドメイン全体委任（Gmail 送信） | Workspace 管理者 | 0.5 日 |

### 第1段階: 台帳と公開フォーム（手作業と組み合わせて運用開始）

| 作業 | 目安 |
|---|---|
| リポジトリ作成、Hosting 別サイト、ログイン画面（OPS から流用） | 1 日 |
| 予約一覧・新規予約・詳細（モックの移植。Firestore 直結） | 3 日 |
| 設定画面（発行者・料金・時間・カレンダー ID） | 1 日 |
| es-ops の rules に rental を追記、テスト追加、デプロイ | 1 日 |
| `submitRentalRequest`（公開フォーム受け口・App Check・受付メール・Chatwork 通知） | 2 日 |
| 請求書 PDF 生成（ダウンロードまで。送信は手動） | 2 日 |
| 動作確認・舜さんへの説明 | 1 日 |
| **小計** | **約 11 日** |

第1段階の手作業: 日程確定時は「Google カレンダーで開く」リンクから登録、確認メールは本文コピーで Gmail から送信、請求書は PDF を保存して Gmail に添付。
モックに既にある機能なので、運用はすぐ始められます。

### 第2段階: 自動化

| 作業 | 目安 |
|---|---|
| `confirmBooking` / `updateCalendar` / `cancelBooking`（Calendar API、重複チェック） | 2 日 |
| `sendConfirmation` / `issueInvoice` / `resendInvoice`（Gmail API、PDF 添付、取消・再発行） | 3 日 |
| 失敗時の表示・再送・履歴 | 1 日 |
| 動作確認（テスト用アドレスで3種のメールを通す） | 1 日 |
| **小計** | **約 7 日** |

### 第3段階: 改善（必要に応じて）

- 前日リマインド（店舗の Chatwork へ）、支払期限超過の通知
- 空き状況カレンダーを公開フォームに表示（Calendar の空き時間を読む）
- レンタル売上を OPS の経営サマリー（`dailySales` とは別枠）に載せる
- STUDIO ページへの埋め込み、カスタムドメイン（例: `rental.bokashi.ink`）
- 入金消込の補助（銀行明細の取り込み）

---

## 10. 未確定事項（決めていただきたいこと）

| # | 項目 | 誰が決める | 今の仮置き | 影響する箇所 |
|---|---|---|---|---|
| 1 | 請求書の **発行者名（法人名）**・住所・電話 | オーナー | 「bokashi Base」＋二番館ビルの住所・011-596-7770 | 請求書 ①、設定 |
| 2 | **インボイス登録番号**（T + 13桁） | オーナー | 未記入 | 請求書 ① |
| 3 | **振込先**（銀行・支店・種別・口座番号・名義） | オーナー | 未記入 | 請求書、請求書メール |
| 4 | **送信元メールアドレス**（manx-loaghtan.co 配下。例: `base@manx-loaghtan.co`）と返信先 | オーナー・舜さん | 未定 | Gmail API、ドメイン全体委任 |
| 5 | **店舗カレンダーの ID**（新規作成を推奨。作成後に ID を登録） | 舜さん | 未作成 | Calendar 連携 |
| 6 | **アプリの URL**（Hosting サイト名。例: `bokashi-rental.web.app`。将来 `rental.bokashi.ink` にするか） | オーナー | `bokashi-rental` | Hosting、フォームの CORS、STUDIO のボタン |
| 7 | 店舗への新着通知先（Chatwork のルーム。bokashi 用のルームがあるか） | 舜さん | 未定 | `submitRentalRequest` |
| 8 | `bokashi-ops-app` を Blaze プランにしてよいか（今は課金未設定。Functions に必須。`es-ops-app` と同じ請求先に紐づける案） | オーナー | 2-5 の A 案 | 第0段階、2-5 |
| 9 | ログイン必須ルールの本番適用の時期 | オーナー承認 | 未適用 | 第0段階（前提条件） |
| 10 | STUDIO のプランで埋め込み（iframe）が使えるか | 舜さん | 不明（ボタン遷移なら不要） | 5-1 |
| 11 | 食事提供の消費税率（全て 10% でよいか。持ち帰りがあるか） | オーナー | 全て 10% | 請求書 ④⑤ |
| 12 | 消費税の端数処理（切り捨て／四捨五入） | オーナー | 切り捨て | 請求書 ⑤ |
| 13 | 利用可能時間と席数（モックは平日 18〜21 時・土日祝 10〜21 時・28 席） | 舜さん | モックのまま | フォームの検証、設定 |
| 14 | キャンセル規定（期限・キャンセル料）と、キャンセル時の請求 | オーナー | 規定なし（請求しない） | `cancelBooking`、フォームの注意書き |
| 15 | 支払期限が土日祝のときの扱い | オーナー | 繰り上げ・繰り下げなし | 請求書 |
| 16 | レンタル売上を OPS の売上（dailySales）とどう分けて集計するか | オーナー・鈴木 | OPS には載せない（第3段階で別枠） | 経営サマリー |
| 17 | 予約データの保存期間と、お客様からの削除依頼への対応 | オーナー | 請求書と同じ 7 年 | 4-5 |

---

## 11. 運用ルール（開発・デプロイ時に守ること）

1. 予約管理アプリのリポジトリからデプロイするのは `hosting:bokashi-rental` と `functions:rental` だけ。`firestore:rules` / `storage` は**デプロイしない**。
2. ルールの変更は es-ops リポジトリで行い、`git diff` で意図した差分だけか確認し、テストを通してから、デプロイと同時にコミットする（es-ops `CLAUDE.md` の手順）。
3. `rental` 以外のコレクションには書かない。OPSアプリのコードは変更しない。
4. 鍵（カレンダー・Gmail の SA 鍵、API キー）は Secret Manager に置き、リポジトリとチャットには書かない。
5. メール・カレンダーの操作は必ず Functions 経由。失敗はログ（`events`）に残し、再試行は人が押す。
6. 本番投入前に、テスト用のメールアドレスとテスト用カレンダーで 3 種のメールと予定の作成・更新・削除を通す。

---

## 付録 A. モックとの対応

| モック | 本番 |
|---|---|
| 共有 DB `reservations` コレクション | Firestore `stores/store_bokashi/rentalBookings`（名前を変更。理由は 4-1） |
| 予約文書の `log[]` 配列 | サブコレクション `events` |
| 予約文書の `invoice` マップ | 別コレクション `rentalInvoices`（不変・取消/再発行） |
| `SHOP` 定数（発行者情報の仮置き） | `rentalSettings/issuer` |
| 受付番号の乱数 | トランザクションで連番 |
| 「Google カレンダーで開く」リンク | Calendar API（第1段階ではリンクのまま） |
| 送信したメールの画面表示 | Gmail API（第1段階ではコピーして手動送信） |
| 請求書プレビュー（HTML） | 同じレイアウトで PDF 生成 |
| 「サンプルデータに戻す」ボタン | なし（本番にサンプルは入れない） |
| 状態 6 段階 | 同じ ＋ `cancelled` |

## 付録 B. 参照した資料

- モック: `docs/mockups/rental-space-tool.html`、旧単体フォーム `docs/mockups/rental-space-request-form.html`
- 料金資料: 「bokashi Base ケータリングプラン」（https://claude.ai/artifact/ATVKjzZGDEXAAxQEpfc9tk）
- OPS アプリ: `ops-app/CLAUDE.md`、`ops-app/firebase.json`、`ops-app/.firebaserc`、`ops-app/firestore.rules`、`ops-app/storage.rules`、`ops-app/src/config/tenants/bokashi.ts`、`ops-app/src/lib/{firebase,auth}.ts`、`ops-app/functions/index.js`（bokashi 売上取込の実装）
- 認証: `ops-app/docs/AUTH_DESIGN.md`、`ops-app/docs/AUTH_ROLLOUT.md`
- 公式サイト: https://bokashi.ink/rentalspace（STUDIO 製であることを確認）
- DNS: `manx-loaghtan.co` の MX / SPF が Google であることを確認（2026-11-02）
