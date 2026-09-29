"""定例会議 Phase 2 レポート生成（固定フォーマット）

ページ構成（2026-09-08 オーナー指示で固定）:
  [callout] タイムテーブル / タスクの使い方
  1️⃣ 前回会議の振り返り（決定事項と確認ポイント、前回発生アクションのチェック）
  2️⃣ 数字ダイジェスト（1行サマリー、月別推移、同期間比較＋差分、直近1週間、注目ポイント、詳細toggle）
  3️⃣ 提案と本日の論点（着地見通し、優先施策、任意の試算、論点）
  4️⃣ AI売上フィードバック（6観点）
  5️⃣ 【後半】タスク棚卸しと担当者別負荷（to_do＝チェックで完了）
  文字起こし全文（貼り付け欄）

数値は全て data_loader 経由で算出し、ctx（JSON）の文章は {キー} で数値を埋め込む。
使い方:
  python meeting_report.py --ctx ../docs/meeting-notes/ctx/2026-09-08.json --page <page_id> [--rebuild] [--dry]
  python meeting_report.py --ctx ... --keys      # 文章で使える {キー} 一覧を表示
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

import data_loader as dl
import notion_writer as nw
import task_ledger as tl
from notion_writer import bulleted, callout, divider, heading, table, toggle

SALES_DIR = Path(__file__).parent.parent / "data" / "sales"
DASHBOARD = "https://bokashi-dashboard.streamlit.app"
DOW = ["月", "火", "水", "木", "金", "土", "日"]
DEFAULT_DEPS = ["ランチ", "かき氷", "コーヒー,ラテ", "スイーツ", "パンケーキ", "ソーダ，ジュース，ティー", "2F シェアラウンジ", "テイクアウト"]
DEP_ALIAS = {"シェアラウンジ 2F": "2F シェアラウンジ", "イベント 2F": "2F イベント"}


def yen(v) -> str:
    return f"¥{int(round(float(v))):,}"


def pct(a, b) -> str:
    return f"{(float(a) / float(b) - 1) * 100:+.1f}%" if b else "—"


def rt(text: str, bold=False, color=None) -> dict:
    d = {"type": "text", "text": {"content": str(text)}}
    ann = {}
    if bold:
        ann["bold"] = True
    if color:
        ann["color"] = color
    if ann:
        d["annotations"] = ann
    return d


def para(parts) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": parts}}


def key(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z぀-ヿ一-鿿]", "_", s)


# ============================================================
# 1. メトリクス算出
# ============================================================
def compute_metrics(ctx: dict) -> dict:
    S = Path(ctx.get("sales_dir", SALES_DIR))
    ev = int(ctx.get("event_threshold", 80000))
    end = ctx["target_end"]                       # "2026-09-07"
    y, m, d = end.split("-")
    tgt = f"{y}-{m}"
    start = f"{tgt}-01"
    M = {}

    df = dl.load_daily(S)
    cur = df[df["日付"].dt.strftime("%Y-%m") == tgt]
    M["_validate"] = dl.validate_daily(cur, tgt)
    comp = dl.compare_same_period(S, start, end, ev).set_index("年月")
    months = sorted(comp.index, reverse=True)
    if tgt not in months:
        raise SystemExit(f"{tgt} のデータがありません")
    prv = [x for x in months if x < tgt][0]
    prv2 = [x for x in months if x < prv][0] if len([x for x in months if x < prv]) else prv
    c9, c8, c7 = comp.loc[tgt], comp.loc[prv], comp.loc[prv2]
    ml = lambda ym: f"{int(ym.split('-')[1])}月"
    M.update(tgt=tgt, prv=prv, prv2=prv2, tgt_label=ml(tgt), prv_label=ml(prv), prv2_label=ml(prv2),
             period=f"{int(m)}/1〜{int(m)}/{int(d)}", end_md=f"{int(m)}/{int(d)}", days=int(c9["全営業日数"]))
    for k, row in (("", c9), ("_prv", c8), ("_prv2", c7)):
        M[f"sales{k}"] = int(row["通常純売上"]); M[f"sales_all{k}"] = int(row["全純売上"])
        M[f"daily{k}"] = int(row["通常日販"]); M[f"cust{k}"] = int(row["通常客数"]); M[f"unit{k}"] = int(row["通常客単価"])
        M[f"ndays{k}"] = int(row["通常営業日数"]); M[f"events{k}"] = row["イベント日"]
    M["daily_pct"] = pct(M["daily"], M["daily_prv"]); M["cust_pct"] = pct(M["cust"], M["cust_prv"]); M["unit_pct"] = pct(M["unit"], M["unit_prv"])
    M["sales_pct"] = pct(M["sales"], M["sales_prv"])
    M["_c"] = (c9, c8, c7); M["_df"] = df; M["_S"] = S; M["_ev"] = ev

    # イベント日・週次（通常営業日＝0円・イベント日を除く）
    M["sales_ev"] = M["sales_all"] - M["sales"]; M["ev_share"] = M["sales_ev"] / M["sales_all"] * 100 if M["sales_all"] else 0
    for _, r in cur[cur["純売上"] > ev].iterrows():
        k = r["日付"].strftime("%m%d"); M[f"ev_{k}"] = int(r["純売上"]); M[f"evc_{k}"] = int(r["客数"]); M[f"evu_{k}"] = int(r["客単価"])
    normal = cur[(cur["純売上"] > 0) & (cur["純売上"] <= ev)]
    def wkavg(s, e):
        x = normal[(normal["日付"] >= s) & (normal["日付"] <= e)]["純売上"]
        return float(x.mean()) if len(x) else 0.0
    for i in range(5):                                     # 1-7日, 8-14日, … の7日区切り
        s = pd.Timestamp(f"{start}") + pd.Timedelta(days=7 * i)
        M[f"w{i+1}_daily"] = wkavg(s, s + pd.Timedelta(days=6))
    M["wk_daily"] = wkavg(ctx["week_start"], ctx["week_end"]); M["pwk_daily"] = wkavg(ctx["prev_week_start"], ctx["prev_week_end"])

    monthly = df.groupby(df["日付"].dt.strftime("%Y-%m")).agg(売上=("純売上", "sum"), 日数=("純売上", "size"), 客数=("客数", "sum"))
    monthly["日販"] = monthly["売上"] / monthly["日数"]; monthly["客単価"] = monthly["売上"] / monthly["客数"]
    M["_monthly"] = monthly
    M["month_sales_prv"] = int(monthly.loc[prv, "売上"]); M["month_sales_prv2"] = int(monthly.loc[prv2, "売上"])

    # 部門
    dep = dl.load_department(S)
    def dep_agg(ym):
        x = dep[dep["年月"] == ym].copy(); x["部門名"] = x["部門名"].replace(DEP_ALIAS)
        g = x.groupby("部門名")["純売上"].sum().sort_values(ascending=False)
        return g, (g / g.sum() * 100 if g.sum() else g)
    d9, d9s = dep_agg(tgt); d8, d8s = dep_agg(prv)
    M["_dep"] = (d9, d9s, d8, d8s)
    for name in set(list(d9.index) + list(d8.index)):
        k = key(name)
        M[f"amt_{k}"] = int(d9.get(name, 0)); M[f"sh_{k}"] = float(d9s.get(name, 0.0)); M[f"shp_{k}"] = float(d8s.get(name, 0.0))
        M[f"shd_{k}"] = M[f"sh_{k}"] - M[f"shp_{k}"]

    # 時間帯
    hr = dl.load_hourly(S); hr9 = hr[hr["年月"] == tgt]
    M["_hr9"] = hr9
    M["after17"] = int(hr9[hr9["時間"] >= 17]["純売上"].sum()); M["after17_pct"] = M["after17"] / M["sales_all"] * 100 if M["sales_all"] else 0
    M["after18"] = int(hr9[hr9["時間"] >= 18]["純売上"].sum())
    pk = hr9.sort_values("純売上", ascending=False).iloc[0] if len(hr9) else None
    M["peak_hour"] = pk["時間帯"] if pk is not None else "—"; M["peak_share"] = float(pk["構成比"]) if pk is not None else 0

    # 曜日（daily から）
    def dow_stats(x):
        g = x.groupby("曜日番号").agg(売上=("純売上", "sum"), 日数=("純売上", "size"), 客数=("客数", "sum"))
        g["日販"] = g["売上"] / g["日数"]; g["客単価"] = g["売上"] / g["客数"]; return g
    prv_normal = df[(df["日付"].dt.strftime("%Y-%m") == prv) & (df["純売上"] <= ev)]
    dow9 = dow_stats(cur); dow8 = dow_stats(prv_normal); M["_dow"] = (dow9, dow8)
    for i, n in enumerate(DOW):
        M[f"dow_{n}"] = int(dow9.loc[i, "売上"]) if i in dow9.index else 0
        M[f"dowd_{n}"] = int(dow9.loc[i, "日販"]) if i in dow9.index else 0
        M[f"dowc_{n}"] = int(dow9.loc[i, "客数"]) if i in dow9.index else 0
        M[f"dowu_{n}"] = int(dow9.loc[i, "客単価"]) if i in dow9.index else 0
        M[f"dowpd_{n}"] = int(dow8.loc[i, "日販"]) if i in dow8.index else 0
        M[f"dowpu_{n}"] = int(dow8.loc[i, "客単価"]) if i in dow8.index else 0
    M["weekend_share"] = (M["dow_土"] + M["dow_日"]) / M["sales_all"] * 100 if M["sales_all"] else 0

    # 顧客
    cus = dl.load_customer(S); cus9 = cus[cus["年月"] == tgt].set_index("ラベル"); cus8 = cus[cus["年月"] == prv].set_index("ラベル")
    M["_cus"] = (cus9, cus8)
    for lab, k in (("新規", "new"), ("リピーター", "rep")):
        M[f"{k}_pct"] = float(cus9.loc[lab, "純売上構成比"]) if lab in cus9.index else 0
        M[f"{k}_pct_prv"] = float(cus8.loc[lab, "純売上構成比"]) if lab in cus8.index else 0
        M[f"{k}_up"] = int(cus9.loc[lab, "客単価"]) if lab in cus9.index else 0
        M[f"{k}_up_prv"] = int(cus8.loc[lab, "客単価"]) if lab in cus8.index else 0
        M[f"{k}_n"] = int(cus9.loc[lab, "客数"]) if lab in cus9.index else 0
    age = dl.load_customer_age(S); age9 = age[age["年月"] == tgt]; age8 = age[age["年月"] == prv]; M["_age"] = (age9, age8)
    for lab in ["20代", "30代", "40代", "50代", "60代〜"]:
        r9 = age9[age9["ラベル"] == lab]; r8 = age8[age8["ラベル"] == lab]
        M[f"age_{key(lab)}"] = float(r9["純売上構成比"].iloc[0]) if len(r9) else 0; M[f"agep_{key(lab)}"] = float(r8["純売上構成比"].iloc[0]) if len(r8) else 0
    nat = dl.load_customer_nationality(S); nat9 = nat[nat["年月"] == tgt].set_index("ラベル"); nat8 = nat[nat["年月"] == prv].set_index("ラベル"); M["_nat"] = (nat9, nat8)
    M["foreign_pct"] = float(nat9.loc["海外", "純売上構成比"]) if "海外" in nat9.index else 0
    M["foreign_pct_prv"] = float(nat8.loc["海外", "純売上構成比"]) if "海外" in nat8.index else 0

    # 商品
    prod = dl.load_product(S); p9 = prod[prod["年月"] == tgt]; p8 = prod[prod["年月"] == prv]; M["_prod"] = (p9, p8)
    M["prod_total"] = int(p9["純売上"].sum())
    for _, r in p9.iterrows():                             # 単品: {p_商品名} 売上 / {pn_商品名} 点数
        k = key(r["商品名"]); M[f"p_{k}"] = M.get(f"p_{k}", 0) + int(r["純売上"]); M[f"pn_{k}"] = M.get(f"pn_{k}", 0) + int(r["販売点数"])
    prv_days = int(monthly.loc[prv, "日数"])
    for g, names in ctx.get("product_groups", {}).items():
        k = key(g); s9 = int(p9[p9["商品名"].isin(names)]["純売上"].sum()); s8 = int(p8[p8["商品名"].isin(names)]["純売上"].sum())
        M[f"pg_{k}"] = s9; M[f"pg_{k}_daily"] = s9 / M["days"]; M[f"pg_{k}_prv"] = s8; M[f"pg_{k}_prv_daily"] = s8 / prv_days
        M[f"pg_{k}_share"] = s9 / M["prod_total"] * 100 if M["prod_total"] else 0
        M[f"pg_{k}_ratio"] = (s9 / M["days"]) / (s8 / prv_days) if s8 else 0

    # 着地見通し
    fc = ctx.get("forecast", {})
    biz_days = int(fc.get("business_days", calendar.monthrange(int(y), int(m))[1] - 1))
    rest = biz_days - M["days"]; M["rest_days"] = rest
    base = M["sales_all"] + M["daily"] * rest
    drop_daily = M.get(f"pg_{key(fc.get('drop_group',''))}_daily", 0) if fc.get("drop_group") else 0
    drop_after = int(fc.get("drop_after_days", 0))
    M["drop_daily"] = drop_daily; M["drop_rest"] = drop_daily * max(rest - drop_after, 0)
    M["fc_low"] = int(base - M["drop_rest"]); M["fc_mid"] = M["fc_low"] + int(fc.get("mid_add", 0)); M["fc_high"] = M["fc_mid"] + int(fc.get("high_add", 0))
    M["fc_mid_vs_prv"] = (1 - M["fc_mid"] / M["month_sales_prv"]) * 100 if M["month_sales_prv"] else 0

    # 価格改定シミュレーション（任意）
    ps = ctx.get("price_sim")
    if ps:
        q = p8[p8["商品名"].isin(ps["items"])]; pts = int(q["販売点数"].sum()); sales = int(q["純売上"].sum()); avg = sales / pts if pts else 0
        M["ps_pts"] = pts; M["ps_sales"] = sales; M["ps_avg"] = avg
        M["_ps_rows"] = [[f"+¥{dlt}", *[f"{int(pts * (1 - c) * (avg + dlt)) - sales:+,}" for c in ps.get("churns", [0, .05, .10, .15])]] for dlt in ps.get("deltas", [100, 200])]
        M["_ps_header"] = ["値上げ幅"] + [f"客離れ {int(c*100)}%" for c in ps.get("churns", [0, .05, .10, .15])]
        for dlt in ps.get("deltas", [100, 200]):
            M[f"ps_be_{dlt}"] = int(dlt / (avg + dlt) * 100) if avg else 0
    return M


def fmt_ns(M: dict) -> dict:
    """文章埋め込み用: 金額系は ¥書式済み文字列も併せて提供（{daily_y} 等）"""
    ns = {k: v for k, v in M.items() if not k.startswith("_")}
    for k, v in list(ns.items()):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            ns[k + "_y"] = yen(v)
    return ns


def F(s: str, ns: dict) -> str:
    try:
        return s.format(**ns)
    except KeyError as e:
        raise SystemExit(f"ctx の文章に未定義キー {e}: {s[:60]}… （--keys で一覧表示）")


# ============================================================
# 2. ブロック生成
# ============================================================
def build_blocks(ctx: dict, M: dict) -> list[dict]:
    ns = fmt_ns(M)
    c9, c8, c7 = M["_c"]; df = M["_df"]; S = M["_S"]; ev = M["_ev"]
    date = ctx["meeting_date"]; prev_date = ctx["prev_meeting_date"]
    owners = ctx.get("owners", ["舜", "慎也", "準", "とし"])
    max_tasks = int(ctx.get("max_tasks_per_person", 10))

    tasks = tl.load(); open_t = tl.open_tasks(tasks)
    stagnant = [t for t in open_t if t["carry"] >= 3]; twice = [t for t in open_t if t["carry"] == 2]; fresh = [t for t in open_t if t["carry"] == 1]
    load = Counter(); by_owner = defaultdict(list)
    for t in open_t:
        for o in t["owner"].split("・"):
            load[o] += 1; by_owner[o].append(t)
    ns.update(n_open=len(open_t), n_stagnant=len(stagnant), n_twice=len(twice), n_fresh=len(fresh))
    n_issues = len(ctx.get("discussion_points", [])) or 4
    est = len(stagnant) * 2 + n_issues * 10 + 20
    ns["est_minutes"] = est

    B = []
    tt = [F(x, ns) for x in ctx.get("timetable", [])]
    B.append(callout(f"📋 推奨タイムテーブル（概算{est}分" + ("・60分超のため後半の棚卸しはAI判断の一括承認で圧縮）" if est > 60 else "）") + "\n" + "\n".join(tt), "⏱️"))
    B.append(para([rt("データ: ", True), rt(F("{period}（{days}営業日）。", ns) + ctx.get("data_note", "") + " "), rt("ダッシュボード: ", True), rt(DASHBOARD)]))
    B.append(callout("タスクの使い方: 各タスクの先頭にチェックボックスと状態タグ（🔄 進行中 / ⏸ 保留）があります。会議中に完了したものはチェックを入れてください。チェック済み＝完了として台帳に記録され、翌週以降のページからは削除されます。", "☑️"))
    w = M["_validate"]["warnings"]
    if w:
        B.append(callout("データ検証: " + " / ".join(w), "🔍"))
    B.append(divider())

    # ---- 1️⃣ 前回の振り返り ----
    B.append(heading(f"1️⃣ 前回（{prev_date}）会議の振り返り", 1))
    B.append(heading("前回の決定事項と今回の確認ポイント", 2))
    B.append(table([["前回の決定事項", "今回の確認ポイント"]] + [[F(a, ns), F(b, ns)] for a, b in ctx["prev_points"]]))
    B.append(heading(f"前回（{prev_date}）発生アクションのチェック（{len(fresh)}件）", 2))
    B.append(para([rt("完了したものにチェック。未完了は次回に持ち越し（持越回数+1）。", color="gray")]))
    B.extend(tl.todo_blocks(fresh, show_ai=False))
    B.append(divider())

    # ---- 2️⃣ 数字ダイジェスト ----
    B.append(heading(F("2️⃣ 数字ダイジェスト（{period}）", ns), 1))
    B.append(callout(F(ctx.get("digest", "通常日販 {daily_y}（{prv_label}同期間 {daily_prv_y}、{daily_pct}）｜客数 {cust}人（{cust_pct}）｜客単価 {unit_y}（{unit_pct}）"), ns), "📌"))
    B.append(heading("月別売上推移", 2))
    rows = [["月", "売上", "営業日", "日販平均", "客数", "客単価", "前月比"]]; prev_sales = None
    for ym, r in M["_monthly"].iterrows():
        label = f"{int(ym.split('-')[1])}月" + (f"（1-{int(M['end_md'].split('/')[1])}日）" if ym == M["tgt"] else "")
        rows.append([label, yen(r["売上"]), f"{int(r['日数'])}日", yen(r["日販"]), f"{int(r['客数']):,}", yen(r["客単価"]), (pct(r["売上"], prev_sales) if prev_sales and ym != M["tgt"] else "—")])
        prev_sales = r["売上"]
    B.append(table(rows))
    B.append(heading("売上サマリー（同期間比較）", 2))
    B.append(table(dl.build_summary_table(S, ctx["target_end"], ev)))
    evp = f"（除{c8['イベント日']}）" if c8["イベント日"] != "なし" else ""
    B.append(table([["指標（通常営業日ベース）", F("{tgt_label} {period}", ns), F("{prv_label}同期間", ns) + evp, "差額", "前月比", F("{prv2_label}同期間", ns)],
        ["通常純売上", yen(c9["通常純売上"]), yen(c8["通常純売上"]), f"{int(c9['通常純売上']-c8['通常純売上']):+,}", pct(c9["通常純売上"], c8["通常純売上"]), yen(c7["通常純売上"])],
        ["通常日販", yen(c9["通常日販"]), yen(c8["通常日販"]), f"{int(c9['通常日販']-c8['通常日販']):+,}", pct(c9["通常日販"], c8["通常日販"]), yen(c7["通常日販"])],
        ["通常客数", f"{int(c9['通常客数'])}人", f"{int(c8['通常客数'])}人", f"{int(c9['通常客数']-c8['通常客数']):+}人", pct(c9["通常客数"], c8["通常客数"]), f"{int(c7['通常客数'])}人"],
        ["通常客単価", yen(c9["通常客単価"]), yen(c8["通常客単価"]), f"{int(c9['通常客単価']-c8['通常客単価']):+,}", pct(c9["通常客単価"], c8["通常客単価"]), yen(c7["通常客単価"])],
        ["営業日数", f"{int(c9['通常営業日数'])}日", f"{int(c8['通常営業日数'])}日", "—", "—", f"{int(c7['通常営業日数'])}日"]]))
    ws, we = ctx["week_start"], ctx["week_end"]; pws, pwe = ctx["prev_week_start"], ctx["prev_week_end"]
    _md = lambda s: f"{int(s[5:7])}/{int(s[8:10])}"
    B.append(heading(f"直近1週間の勢い（{_md(ws)}〜{_md(we)}）", 2))
    B.append(table(dl.build_weekly_table(df, ws, we, ev)))
    B.append(toggle("前週との日別比較", [table(dl.build_weekly_table(df, pws, pwe, ev))]))
    B.append(heading("注目ポイント", 2))
    B.append(heading("🟢 ポジティブ", 3))
    for k, t in ctx["positives"]: B.append(bulleted(F(t, ns), k))
    B.append(heading("🔴 要注意", 3))
    for k, t in ctx["negatives"]: B.append(bulleted(F(t, ns), k))
    B.append(toggle("📊 詳細データ（時間帯・曜日・部門・商品・顧客）— クリックで展開", _detail_blocks(ctx, M)))
    B.append(divider())

    # ---- 3️⃣ 提案と論点 ----
    B.append(heading("3️⃣ 提案と本日の論点", 1))
    B.append(heading(F("{tgt_label}の着地見通し", ns), 2))
    fc = ctx.get("forecast", {})
    B.append(table([["シナリオ", "前提", F("{tgt_label}売上", ns)],
                    ["悲観", F(fc.get("low_note", "現在の通常日販が続く"), ns), yen(M["fc_low"])],
                    ["中立", F(fc.get("mid_note", ""), ns), yen(M["fc_mid"])],
                    ["楽観", F(fc.get("high_note", ""), ns), yen(M["fc_high"])]]))
    if fc.get("comment"):
        B.append(para([rt(F(fc["comment"], ns))]))
    B.append(heading("優先施策", 2))
    for k, t in ctx["proposals"]: B.append(bulleted(F(t, ns), k))
    ps = ctx.get("price_sim")
    if ps:
        B.append(heading(ps.get("title", "💴 価格改定シミュレーション"), 2))
        B.append(para([rt(F(ps.get("intro", "{ps_pts}点・{ps_sales_y}・平均単価{ps_avg_y}"), ns))]))
        B.append(table([M["_ps_header"]] + M["_ps_rows"]))
        for k, t in ps.get("notes", []): B.append(bulleted(F(t, ns), k))
    B.append(heading("🗣️ 本日の論点", 2))
    for i, t in enumerate(ctx["discussion_points"], 1): B.append(bulleted(F(t, ns), f"{i}"))
    B.append(divider())

    # ---- 4️⃣ AI売上フィードバック ----
    B.append(heading(F("4️⃣ AI売上フィードバック（{period}）", ns), 1))
    ai = ctx["ai_feedback"]
    B.append(heading("1. 全体評価", 2)); B.append(para([rt(F(ai["overall"], ns))]))
    B.append(heading("2. 売上構造の変化", 2))
    d9, d9s, d8, d8s = M["_dep"]
    rows = [["部門", M["prv_label"], F("{tgt_label}{period}", ns), "変化"]]
    for name in ctx.get("departments", DEFAULT_DEPS):
        a = float(d9s.get(name, 0)); b = float(d8s.get(name, 0)); rows.append([name, f"{b:.1f}%", f"{a:.1f}%", f"{a-b:+.1f}pt"])
    B.append(table(rows)); B.append(para([rt(F(ai["structure"], ns))]))
    B.append(heading("3. 顧客動向", 2))
    B.append(table([["区分", f"{M['prv_label']} 客単価", f"{M['tgt_label']} 客単価", f"{M['prv_label']} 構成比", f"{M['tgt_label']} 構成比"],
                    ["新規", yen(M["new_up_prv"]), yen(M["new_up"]), f"{M['new_pct_prv']:.1f}%", f"{M['new_pct']:.1f}%"],
                    ["リピーター", yen(M["rep_up_prv"]), yen(M["rep_up"]), f"{M['rep_pct_prv']:.1f}%", f"{M['rep_pct']:.1f}%"]]))
    B.append(para([rt(F(ai["customers"], ns))]))
    B.append(heading("4. 曜日別格差", 2)); B.append(para([rt(F(ai["weekday"], ns))]))
    B.append(heading("5. 季節リスクと代替シナリオ", 2))
    if ai.get("season_table"):
        B.append(table([[F(c, ns) for c in row] for row in ai["season_table"]]))
    B.append(para([rt(F(ai["season"], ns))]))
    B.append(heading("6. 戦略的問い", 2)); B.append(callout(F(ai["question"], ns), "❓"))
    B.append(divider())

    # ---- 5️⃣ 後半: タスク棚卸し ----
    B.append(heading("5️⃣ 【後半】タスク棚卸しと担当者別負荷", 1))
    B.append(callout("AI判断に異論がなければ「承認」で一括処理。取り下げ・統合と決まったものもチェックを入れる（＝台帳から削除、翌週非表示）。", "🧹"))
    B.append(heading(f"⚠️ 3回以上持ち越し（{len(stagnant)}件）", 2))
    B.extend(tl.todo_blocks(stagnant, show_ai=True))
    why = [bulleted(f"#{t['id']} {t['task'][:28]}… → {t['why']}") for t in stagnant if t.get("why")]
    if why: B.append(toggle("AI判断の根拠（クリックで展開）", why))
    B.append(heading(f"🟡 2回持ち越し（{len(twice)}件）", 2))
    B.extend(tl.todo_blocks(twice, show_ai=True))
    B.append(heading("👥 担当者別タスク負荷（未完了）", 2))
    rows = [["担当", "未完了", "3回以上", "2回", "新規", "状態"]]
    for o in owners:
        ts = by_owner[o]
        rows.append([o, f"{load[o]}件", sum(1 for t in ts if t["carry"] >= 3), sum(1 for t in ts if t["carry"] == 2), sum(1 for t in ts if t["carry"] == 1), (f"🔴 上限{max_tasks}件を超過" if load[o] > max_tasks else "🟢")])
    B.append(table(rows))
    for o in owners:
        if load[o] > max_tasks:
            B.append(callout(f"{o}さんが{load[o]}件で上限{max_tasks}件の{load[o]/max_tasks:.1f}倍。" + F(ctx.get("load_note", {}).get(o, ""), ns), "⚠️"))
    for o in owners:
        ts = sorted(by_owner[o], key=lambda t: -t["carry"])
        if ts:
            B.append(toggle(f"{o}（{load[o]}件）の詳細", [table([["#", "カテゴリ", "タスク", "初出", "持越", "AI判断"]] + [[t["id"], t["cat"], t["task"], t["since"], f"{t['carry']}回", t.get("ai", "")] for t in ts])]))
    B.append(divider())
    B.append(callout("このレポートはAIによる分析です。数値はスマレジCSV（Google Drive）から data_loader 経由で算出。現場の感覚と突き合わせて活用してください。", "🤖"))
    B.append(divider())
    B.append(heading("文字起こし全文", 2))
    B.append(callout("会議後、Plaud Noteの文字起こしテキストをこの下に貼り付けてください", "👇"))
    return B


def _detail_blocks(ctx: dict, M: dict) -> list[dict]:
    kids = []
    tgt, prv = M["tgt_label"], M["prv_label"]
    hr9 = M["_hr9"]
    kids.append(heading(f"時間帯別（{tgt}{M['period']}）", 3))
    rows = [["時間帯", "純売上", "構成比", "客数", "客単価"]]
    for _, r in hr9.sort_values("時間").iterrows(): rows.append([r["時間帯"], yen(r["純売上"]), f"{r['構成比']:.1f}%", int(r["客数"]), yen(r["客単価"])])
    kids.append(table(rows))
    dow9, dow8 = M["_dow"]
    kids.append(heading(f"曜日別（{tgt} vs {prv}通常営業日）", 3))
    rows = [["曜日", f"{tgt} 売上", f"{tgt} 客数", f"{tgt} 客単価", f"{prv} 日販", f"{prv} 客単価", "日販差"]]
    for i in range(7):
        a = dow9.loc[i] if i in dow9.index else None; b = dow8.loc[i] if i in dow8.index else None
        rows.append([DOW[i], yen(a["売上"]) if a is not None else "—", int(a["客数"]) if a is not None else "—", yen(a["客単価"]) if a is not None else "—",
                     yen(b["日販"]) if b is not None else "—", yen(b["客単価"]) if b is not None else "—", f"{int(a['売上']-b['日販']):+,}" if a is not None and b is not None else "—"])
    kids.append(table(rows))
    d9, d9s, d8, d8s = M["_dep"]
    kids.append(heading(f"部門別（{tgt} vs {prv}）", 3))
    rows = [["部門", f"{tgt} 売上", f"{tgt} 構成比", f"{prv} 売上", f"{prv} 構成比", "構成比差"]]
    for name in list(d9.index) + [n for n in d8.index if n not in d9.index]:
        rows.append([name, yen(d9.get(name, 0)), f"{float(d9s.get(name, 0)):.1f}%", yen(d8.get(name, 0)), f"{float(d8s.get(name, 0)):.1f}%", f"{float(d9s.get(name, 0))-float(d8s.get(name, 0)):+.1f}pt"])
    kids.append(table(rows))
    p9, _ = M["_prod"]
    kids.append(heading(f"商品別 Top15（{tgt}）", 3))
    rows = [["順位", "商品", "部門", "純売上", "点数", "構成比"]]
    for i, (_, r) in enumerate(p9.sort_values("純売上", ascending=False).head(15).iterrows(), 1): rows.append([i, r["商品名"], r["部門名"], yen(r["純売上"]), int(r["販売点数"]), f"{r['純売上構成比']:.1f}%"])
    kids.append(table(rows))
    cus9, cus8 = M["_cus"]
    kids.append(heading("顧客動向", 3))
    rows = [["区分", f"{tgt} 売上", f"{tgt} 構成比", f"{tgt} 客数", f"{tgt} 客単価", f"{prv} 構成比", f"{prv} 客単価"]]
    for lab in ["新規", "リピーター"]:
        if lab in cus9.index:
            rows.append([lab, yen(cus9.loc[lab, "純売上"]), f"{cus9.loc[lab,'純売上構成比']:.1f}%", int(cus9.loc[lab, "客数"]), yen(cus9.loc[lab, "客単価"]), f"{cus8.loc[lab,'純売上構成比']:.1f}%" if lab in cus8.index else "—", yen(cus8.loc[lab, "客単価"]) if lab in cus8.index else "—"])
    kids.append(table(rows))
    age9, age8 = M["_age"]
    rows = [["年代", f"{tgt} 構成比", f"{tgt} 客単価", f"{prv} 構成比", f"{prv} 客単価"]]
    for lab in ["20代", "30代", "40代", "50代", "60代〜", "〜10代"]:
        r9 = age9[age9["ラベル"] == lab]; r8 = age8[age8["ラベル"] == lab]
        rows.append([lab, f"{float(r9['純売上構成比'].iloc[0]):.1f}%" if len(r9) else "—", yen(r9["客単価"].iloc[0]) if len(r9) else "—", f"{float(r8['純売上構成比'].iloc[0]):.1f}%" if len(r8) else "—", yen(r8["客単価"].iloc[0]) if len(r8) else "—"])
    kids.append(table(rows))
    nat9, nat8 = M["_nat"]
    rows = [["国籍", f"{tgt} 構成比", f"{tgt} 客単価", f"{prv} 構成比", f"{prv} 客単価"]]
    for lab in ["日本", "海外"]:
        if lab in nat9.index:
            rows.append([lab, f"{nat9.loc[lab,'純売上構成比']:.1f}%", yen(nat9.loc[lab, "客単価"]), f"{nat8.loc[lab,'純売上構成比']:.1f}%" if lab in nat8.index else "—", yen(nat8.loc[lab, "客単価"]) if lab in nat8.index else "—"])
    kids.append(table(rows))
    return kids


# ============================================================
# 3. CLI
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True, help="会議コンテキストJSON")
    ap.add_argument("--page", help="NotionページID/URL（省略時は ctx.page）")
    ap.add_argument("--rebuild", action="store_true", help="ページの既存ブロックを全削除してから書き込む")
    ap.add_argument("--dry", action="store_true", help="書き込まずブロック数だけ表示")
    ap.add_argument("--keys", action="store_true", help="文章で使える {キー} を表示")
    a = ap.parse_args()
    ctx = json.loads(Path(a.ctx).read_text(encoding="utf-8"))
    M = compute_metrics(ctx)
    if a.keys:
        for k, v in sorted(fmt_ns(M).items()):
            print(f"{k} = {v}")
        return
    print("validate:", M["_validate"]["warnings"] or "ok")
    B = build_blocks(ctx, M)
    print("blocks:", len(B))
    if a.dry:
        return
    page = a.page or ctx["page"]
    if a.rebuild:
        old = nw.get_blocks(page)
        print("delete:", nw.delete_blocks([b["id"] for b in old]))
    print("append:", nw.append_blocks(page, B))


if __name__ == "__main__":
    main()
