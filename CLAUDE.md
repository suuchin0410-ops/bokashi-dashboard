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
駿さん（店長）がスマレジからCSVエクスポート
  ↓
Google Drive「コンサルティング/bokashi/sales/」に格納
  ↓
Claude が Google Drive MCP でCSVを取得 → ローカル data/sales/ に同期
  ↓
Streamlitダッシュボード / HTMLレポート / PDFレポート
```

**Google Drive フォルダ構成:**
```
マイドライブ/コンサルティング/bokashi/ (ID: 13RiWJdT-eic_s2Fom9WxnM-IvEur4etL)
  ├── sales/          (ID: 1Ligr0RnQOo7aPB9iZ2YMS0CefsgGHuBC) ← CSVはここ
  ├── meeting-notes/  (ID: 17tjzCgCJl-HorsIjwncpWhKo-xiVRyBf)
  └── reports/        (ID: 1HyHL2Ar29r1QQcHb2ro89GNBCcVP-N7f)
```

**データ更新手順（「更新して」「データ見て」「KPI」等のキーワードで実行）:**
1. `search_files` で salesフォルダを検索: `parentId = '1Ligr0RnQOo7aPB9iZ2YMS0CefsgGHuBC'`
2. `app/sync_drive.py` の `get_sync_status(drive_files)` で差分チェック
3. new/updated があれば `download_file_content` で取得
4. `save_from_base64(b64, local_name)` でローカルに保存
5. `record_sync(synced_files)` で同期ログを記録（ダッシュボードのサイドバーに反映）

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
└── CLAUDE.md
```
