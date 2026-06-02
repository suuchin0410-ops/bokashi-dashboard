"""売上レポートをスタンドアロンHTMLとして書き出す"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yaml
from pathlib import Path
from datetime import datetime

from data_loader import load_daily, load_product, load_customer, load_department

CONFIG_DIR = Path(__file__).parent / "config"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "reports"
COLORS = ["#c4a882", "#5a3e2b", "#8b7355", "#d4c5a9", "#a0522d", "#deb887"]


def load_config(store_id: str) -> dict:
    with open(CONFIG_DIR / f"{store_id}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_report(store_id: str = "bokashi"):
    config = load_config(store_id)
    store = config["store"]
    sales_dir = Path(__file__).parent / config["data"]["sales_dir"]

    df = load_daily(sales_dir)
    df_prod = load_product(sales_dir)
    df_cust = load_customer(sales_dir)
    df_dept = load_department(sales_dir)

    total_sales = df["純売上"].sum()
    total_customers = df["客数"].sum()
    avg_customer = total_sales / total_customers if total_customers > 0 else 0
    active_days = len(df)
    avg_daily = total_sales / active_days if active_days > 0 else 0
    gross_profit = df["粗利"].sum()
    gross_rate = (gross_profit / total_sales * 100) if total_sales > 0 else 0
    discount_total = df["値引き"].sum()

    date_from = df["日付"].min().strftime("%Y/%m/%d")
    date_to = df["日付"].max().strftime("%Y/%m/%d")
    generated = datetime.now().strftime("%Y/%m/%d %H:%M")

    charts = []

    # 日別売上
    daily = df[["日付", "純売上"]].copy()
    daily["7日移動平均"] = daily["純売上"].rolling(7, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily["日付"], y=daily["純売上"], name="日別売上", marker_color="#c4a882", opacity=0.7))
    fig.add_trace(go.Scatter(x=daily["日付"], y=daily["7日移動平均"], name="7日移動平均", line=dict(color="#5a3e2b", width=2)))
    fig.update_layout(title="日別売上推移", yaxis_title="売上（円）", legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(t=50, b=30))
    charts.append(fig)

    # 曜日別
    wn = ["月", "火", "水", "木", "金", "土", "日"]
    wd = df.groupby("曜日番号").agg(平均売上=("純売上", "mean"), 平均客数=("客数", "mean")).reset_index()
    wd["曜日"] = wd["曜日番号"].map(lambda x: wn[x])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=wd["曜日"], y=wd["平均売上"], name="平均売上", marker_color="#c4a882"))
    fig.add_trace(go.Scatter(x=wd["曜日"], y=wd["平均客数"], name="平均客数", line=dict(color="#5a3e2b", width=2), yaxis="y2"))
    fig.update_layout(title="曜日別パフォーマンス", yaxis=dict(title="平均売上（円）"), yaxis2=dict(title="平均客数（人）", overlaying="y", side="right"), legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(t=50, b=30))
    charts.append(fig)

    # 客数・客単価
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["日付"], y=df["客数"], name="客数", marker_color="#c4a882", opacity=0.7))
    fig.add_trace(go.Scatter(x=df["日付"], y=df["客単価"], name="客単価", line=dict(color="#5a3e2b", width=2), yaxis="y2"))
    fig.update_layout(title="客数・客単価推移", yaxis=dict(title="客数（人）"), yaxis2=dict(title="客単価（円）", overlaying="y", side="right"), legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(t=50, b=30))
    charts.append(fig)

    # 商品ランキング
    if not df_prod.empty:
        ranking = df_prod.groupby("商品名").agg(売上=("純売上", "sum")).sort_values("売上", ascending=True).tail(15).reset_index()
        fig = px.bar(ranking, x="売上", y="商品名", orientation="h", color_discrete_sequence=["#c4a882"], text=ranking["売上"].apply(lambda x: f"¥{x:,.0f}"))
        fig.update_layout(title="商品別売上ランキング（TOP15）", xaxis_title="売上（円）", yaxis_title="", margin=dict(t=50, b=30, l=150))
        fig.update_traces(textposition="outside")
        charts.append(fig)

    # 部門別
    if not df_dept.empty:
        dept = df_dept.groupby("部門名").agg(売上=("純売上", "sum")).sort_values("売上", ascending=False).reset_index()
        fig = px.pie(dept, values="売上", names="部門名", color_discrete_sequence=COLORS)
        fig.update_layout(title="部門別売上構成", margin=dict(t=50, b=30))
        charts.append(fig)

    # 客層別 KPI + チャート
    cust_kpi_html = ""
    if not df_cust.empty:
        new = df_cust[df_cust["ラベル"] == "新規"]
        repeat = df_cust[df_cust["ラベル"] == "リピーター"]
        new_sales, repeat_sales = new["純売上"].sum(), repeat["純売上"].sum()
        new_count, repeat_count = new["客数"].sum(), repeat["客数"].sum()
        total_count = new_count + repeat_count
        repeat_rate = (repeat_count / total_count * 100) if total_count > 0 else 0
        new_unit = new_sales / new_count if new_count > 0 else 0
        repeat_unit = repeat_sales / repeat_count if repeat_count > 0 else 0

        cust_kpi_html = f"""
<h2 style="color:#5a3e2b; margin: 30px 0 15px;">客層分析（新規 vs リピーター）</h2>
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-value">{repeat_rate:.1f}%</div><div class="kpi-label">リピーター率</div></div>
  <div class="kpi"><div class="kpi-value">{new_count:,.0f}人</div><div class="kpi-label">新規客数</div></div>
  <div class="kpi"><div class="kpi-value">{repeat_count:,.0f}人</div><div class="kpi-label">リピーター客数</div></div>
  <div class="kpi"><div class="kpi-value">¥{new_unit:,.0f}</div><div class="kpi-label">新規客単価</div></div>
  <div class="kpi"><div class="kpi-value">¥{repeat_unit:,.0f}</div><div class="kpi-label">リピーター客単価</div></div>
  <div class="kpi"><div class="kpi-value">¥{new_sales:,.0f}</div><div class="kpi-label">新規売上</div></div>
  <div class="kpi"><div class="kpi-value">¥{repeat_sales:,.0f}</div><div class="kpi-label">リピーター売上</div></div>
</div>"""

        seg = df_cust.groupby("ラベル").agg(売上=("純売上", "sum"), 客数=("客数", "sum")).reset_index()
        fig = px.pie(seg, values="客数", names="ラベル", color="ラベル",
                     color_discrete_map={"新規": "#c4a882", "リピーター": "#5a3e2b"})
        fig.update_layout(title="客数構成（新規 vs リピーター）", margin=dict(t=50, b=30))
        charts.append(fig)

    charts_html = "".join(c.to_html(full_html=False, include_plotlyjs=False) for c in charts)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{store['name']} 売上レポート</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: "Helvetica Neue", "Hiragino Sans", sans-serif; background: #faf9f7; color: #333; padding: 20px; max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 1.8em; color: #5a3e2b; margin-bottom: 5px; }}
  h2 {{ font-size: 1.4em; }}
  .subtitle {{ color: #888; font-size: 0.9em; margin-bottom: 30px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 30px; }}
  .kpi {{ background: white; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .kpi-value {{ font-size: 1.5em; font-weight: bold; color: #5a3e2b; }}
  .kpi-label {{ font-size: 0.85em; color: #888; margin-top: 5px; }}
  .chart-section {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .footer {{ text-align: center; color: #aaa; font-size: 0.8em; margin-top: 40px; padding: 20px; }}
</style>
</head>
<body>
<h1>{store['name']} 売上レポート</h1>
<div class="subtitle">{date_from} 〜 {date_to} | 作成日: {generated}</div>

<div class="kpi-grid">
  <div class="kpi"><div class="kpi-value">¥{total_sales:,.0f}</div><div class="kpi-label">純売上</div></div>
  <div class="kpi"><div class="kpi-value">{total_customers:,.0f}人</div><div class="kpi-label">客数</div></div>
  <div class="kpi"><div class="kpi-value">¥{avg_customer:,.0f}</div><div class="kpi-label">客単価</div></div>
  <div class="kpi"><div class="kpi-value">¥{avg_daily:,.0f}</div><div class="kpi-label">日販平均</div></div>
  <div class="kpi"><div class="kpi-value">{active_days}日</div><div class="kpi-label">営業日数</div></div>
  <div class="kpi"><div class="kpi-value">¥{gross_profit:,.0f}</div><div class="kpi-label">粗利</div></div>
  <div class="kpi"><div class="kpi-value">{gross_rate:.1f}%</div><div class="kpi-label">粗利率</div></div>
  <div class="kpi"><div class="kpi-value">¥{discount_total:,.0f}</div><div class="kpi-label">値引き合計</div></div>
</div>

<div class="chart-section">{charts_html}</div>

{cust_kpi_html}

<div class="footer">このレポートはスマレジの売上データから自動生成されました</div>
</body>
</html>"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"report_{store_id}_{date_from.replace('/', '')}_{date_to.replace('/', '')}.html"
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"レポート生成完了: {output_path}")
    return output_path

if __name__ == "__main__":
    build_report()
