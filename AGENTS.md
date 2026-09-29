# bokashi - カフェコンサルティング & 売上管理システム

## プロジェクト概要
札幌市中央区のカフェ「bokashi」の売上管理・分析・顧客管理を行うコンサルティングプロジェクト。
ウェブアプリの開発とコンサルティング資料を一元管理する。

## 店舗情報
- **店名:** bokashi
- **所在地:** 北海道札幌市中央区南2条西1-7-1 二番館ビル 1F
- **最寄駅:** 大通駅 35番出口すぐ / 西4丁目駅 徒歩295m
- **営業時間:** 10:00〜18:00（L.O. 17:00）
- **定休日:** 不定休
- **席数:** 20席
- **電話:** 011-596-7770
- **ウェブサイト:** https://bokashi.ink/
- **食べログ:** https://tabelog.com/hokkaido/A0101/A010103/1073057/

## 事業の特徴
- 循環社会の形成を目指す「bokashi」プロジェクトの拠点
- bokashi Base: 会員制コワーキングスペース + レンタルスペース + カフェの多目的空間
- 季節の素材を使った手作りスイーツが中心（バスクチーズケーキ、タルトタタン等）
- 余市・長沼など北海道の生産者から仕入れ
- コーヒーはProlog Coffee（コペンハーゲン）の豆を使用

## メニュー（ドリンク）
- 浅煎り珈琲 ¥600
- カフェラテ ¥600
- 穀物コーヒー / ラテ ¥600
- ブレンドハーブティー ¥500
- ハーブソーダ ¥800
- 葡萄のストレートジュース ¥800
- スイーツ: さつまいものバスクチーズケーキ、りんごのタルトタタン、ぶどうのタルトレット、ティラミス、クラシックプリン、フォンダンショコラ 等

## 客単価
¥1,000〜¥1,999

## データフロー（重要）

```
舜さん（店長）がスマレジからCSVエクスポート
  ↓
Google Drive「コンサルティング/bokashi/sales/」に格納
  ↓
Streamlitアプリが起動時にGoogle Drive APIで直接CSV取得（5分キャッシュ）
  ↓
ダッシュボード表示
```

**データ更新:**
ダッシュボードは起動時にGoogle Driveから直接CSVを取得するため、
舜さんがDriveにCSVを置けばリロードで自動反映される。
手動同期やgit pushは不要。

**注意:** Google DriveフォルダIDやサービスアカウントキーはStreamlit Secretsで管理。
リポジトリには含めない。

## 売上管理の現状
- **レジ:** スマレジ
- **データ出力:** CSV書き出し（Shift-JIS、日別集計形式）
- **CSVカラム:** 日付, 純売上, 純売上(税抜), 消費税, 免税額, 総売上, 値引き, ポイント利用, 外税受領, 売上対象外, 送料, 手数料, 原価, 粗利, 販売点数, 返品数, 取引数, 取引単価, 客数, 客単価, 予算設定金額, 予算達成率, クーポン利用
- **注意:** CSV末尾に合計・前月比・前年比の行あり（読み込み時に除外が必要）

## アプリの利用者
- **メイン:** 鈴木（コンサルタント）
- **閲覧:** オーナー、スタッフ

## 開発の優先順位
1. **売上の可視化・分析**（最優先）
   - 日別の売上推移
   - 時間帯別の売上（ピークタイム把握）
   - 商品別ランキング
2. **顧客リピート率アップの仕組み**（次フェーズ）

## 技術スタック
- **MVP:** Python + Streamlit（スピード重視）
- **将来:** URL共有（Streamlit Cloud等でデプロイ）
- **汎用性:** 設定ファイルで店舗を切り替え可能な設計。他クライアントにも展開予定。

## フォルダ構成
```
bokashi/
├── app/                        # 売上分析アプリ（汎用）
│   ├── app.py                  # Streamlitダッシュボード
│   ├── data_loader.py          # CSV読み込み共通モジュール
│   ├── sync_drive.py           # Google Drive同期ユーティリティ
│   ├── export_report.py        # HTMLレポート出力
│   ├── export_pdf.py           # PDFレポート出力
│   ├── notion_reader.py        # Notion議事録取得
│   ├── generate_dummy_data.py  # ダミーデータ生成（開発用）
│   ├── config/
│   │   └── bokashi.yaml        # bokashi固有の設定
│   └── requirements.txt
├── docs/
│   ├── meeting-notes/          # 議事録（Notionから取得・構造化）
│   ├── reports/                # 生成済みレポート（HTML/PDF）
│   ├── strategy/               # 戦略資料・分析
│   └── proposals/              # 提案書
├── data/
│   └── sales/                  # 売上CSV（Google Driveから同期）
│       └── .sync_log.json      # 同期履歴（自動生成）
└── AGENTS.md
```

## 合言葉ワークフロー

### 「会議の準備をして」→ 会議ページ作成 + AI分析レポート

以下を実行する:

1. `app/notion_writer.create_meeting_page()` で Notion に新規ページを自動作成
   - 親ページ「bokashi 議事録」の子ページとして作成（権限は自動継承、接続作業不要）
2. Google Driveから最新の売上CSVデータを確認
3. `docs/meeting-notes/` の最新議事録から前回のアクションアイテムを取得
4. 売上データからAI分析レポートを生成（推測・予測を付加）
5. Notionページに分析レポートを書き込み
6. ページURLを慎也に共有

### 「議事録更新して」→ 構造化議事録 + 本質的課題分析

以下を実行する:

1. `app/notion_reader.fetch_page()` で Notion から文字起こしテキストを取得
2. 音声文字起こしの名前マッピングを適用（`memory/reference_name_mapping.md` 参照）
3. 売上データ × 議論内容 → 構造化議事録 + 本質的課題を分析
4. Notionページに書き戻し（分析を上部、文字起こしはトグルに格納）
5. `docs/meeting-notes/YYYY-MM-DD.md` にローカル保存
6. 決定事項・アクションアイテムを報告

**Notion連携:**
- 読み取り: `app/notion_reader.fetch_page(url_or_id)`
- 書き込み: `app/notion_writer` の各関数
- ページ作成: `app/notion_writer.create_meeting_page(date)`
- トークン: `app/config/.notion_token`（Codex integration）
- **新規ページは親ページから権限を自動継承するため、手動での接続追加は不要**

**議事録テンプレート:**
```markdown
---
date: YYYY-MM-DD
duration: X時間XX分
participants: 参加者名
source: Notion URL
---

# YYYY-MM-DD 定例会議

## 議題・要点
## 決定事項・アクション
## 数値メモ
## 前回アクション進捗
## 次回に向けて
```

**詳細なワークフロー定義:** `docs/meeting-notes/workflow.md` を参照
