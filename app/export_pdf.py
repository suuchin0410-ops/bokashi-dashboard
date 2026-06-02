"""売上レポートをPDFとして書き出す（チャートは画像埋め込み）"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yaml, base64, io
from pathlib import Path
from datetime import datetime

from data_loader import load_daily, load_product, load_customer, load_department

CONFIG_DIR = Path(__file__).parent / "config"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "reports"
COLORS = ["#c4a882", "#5a3e2b", "#8b7355", "#d4c5a9", "#a0522d", "#deb887"]


def load_config(store_id):
    with open(CONFIG_DIR / f"{store_id}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)

def fig_to_img(fig, w=1000, h=450):
    img_bytes = fig.to_image(format="png", width=w, height=h, scale=2)
    b64 = base64.b64encode(img_bytes).decode()
    return f'<img src="data:image/png;base64,{b64}" style="width:100%; max-width:{w}px;">'

def build_pdf(store_id="bokashi"):
    config = load_config(store_id)
    store = config["store"]
    sd = Path(__file__).parent / config["data"]["sales_dir"]

    df = load_daily(sd)
    df_prod = load_product(sd)
    df_cust = load_customer(sd)
    df_dept = load_department(sd)

    total_sales = df["純売上"].sum()
    total_cust = df["客数"].sum()
    avg_cust = total_sales/total_cust if total_cust>0 else 0
    days = len(df)
    avg_daily = total_sales/days if days>0 else 0
    gp = df["粗利"].sum()
    gp_rate = (gp/total_sales*100) if total_sales>0 else 0
    disc = df["値引き"].sum()
    d_from = df["日付"].min().strftime("%Y/%m/%d")
    d_to = df["日付"].max().strftime("%Y/%m/%d")
    now = datetime.now().strftime("%Y/%m/%d %H:%M")

    imgs = []

    # 日別売上
    daily = df[["日付","純売上"]].copy()
    daily["7日移動平均"] = daily["純売上"].rolling(7, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily["日付"],y=daily["純売上"],name="日別売上",marker_color="#c4a882",opacity=0.7))
    fig.add_trace(go.Scatter(x=daily["日付"],y=daily["7日移動平均"],name="7日移動平均",line=dict(color="#5a3e2b",width=2)))
    fig.update_layout(title="日別売上推移",yaxis_title="売上（円）",legend=dict(orientation="h",yanchor="bottom",y=1.02),margin=dict(t=50,b=30),plot_bgcolor="white")
    imgs.append(fig_to_img(fig))

    # 曜日別
    wn=["月","火","水","木","金","土","日"]
    wd=df.groupby("曜日番号").agg(平均売上=("純売上","mean"),平均客数=("客数","mean")).reset_index()
    wd["曜日"]=wd["曜日番号"].map(lambda x:wn[x])
    fig=go.Figure()
    fig.add_trace(go.Bar(x=wd["曜日"],y=wd["平均売上"],name="平均売上",marker_color="#c4a882"))
    fig.add_trace(go.Scatter(x=wd["曜日"],y=wd["平均客数"],name="平均客数",line=dict(color="#5a3e2b",width=2),yaxis="y2"))
    fig.update_layout(title="曜日別パフォーマンス",yaxis=dict(title="平均売上（円）"),yaxis2=dict(title="平均客数（人）",overlaying="y",side="right"),legend=dict(orientation="h",yanchor="bottom",y=1.02),margin=dict(t=50,b=30),plot_bgcolor="white")
    imgs.append(fig_to_img(fig, 500, 350))

    # 客数・客単価
    fig=go.Figure()
    fig.add_trace(go.Bar(x=df["日付"],y=df["客数"],name="客数",marker_color="#c4a882",opacity=0.7))
    fig.add_trace(go.Scatter(x=df["日付"],y=df["客単価"],name="客単価",line=dict(color="#5a3e2b",width=2),yaxis="y2"))
    fig.update_layout(title="客数・客単価推移",yaxis=dict(title="客数（人）"),yaxis2=dict(title="客単価（円）",overlaying="y",side="right"),legend=dict(orientation="h",yanchor="bottom",y=1.02),margin=dict(t=50,b=30),plot_bgcolor="white")
    imgs.append(fig_to_img(fig, 500, 350))

    # 商品ランキング
    prod_img = ""
    if not df_prod.empty:
        rk=df_prod.groupby("商品名").agg(売上=("純売上","sum")).sort_values("売上",ascending=True).tail(15).reset_index()
        fig=px.bar(rk,x="売上",y="商品名",orientation="h",color_discrete_sequence=["#c4a882"],text=rk["売上"].apply(lambda x:f"¥{x:,.0f}"))
        fig.update_layout(title="商品別売上ランキング（TOP15）",xaxis_title="売上（円）",yaxis_title="",margin=dict(t=50,b=30,l=150),plot_bgcolor="white")
        fig.update_traces(textposition="outside")
        prod_img = fig_to_img(fig, 1000, 500)

    # 部門別
    dept_img = ""
    if not df_dept.empty:
        dept=df_dept.groupby("部門名").agg(売上=("純売上","sum")).sort_values("売上",ascending=False).reset_index()
        fig=px.pie(dept,values="売上",names="部門名",color_discrete_sequence=COLORS)
        fig.update_layout(title="部門別売上構成",margin=dict(t=50,b=30))
        dept_img = fig_to_img(fig, 500, 400)

    # 客層別
    cust_html = ""
    if not df_cust.empty:
        new=df_cust[df_cust["ラベル"]=="新規"]
        rep=df_cust[df_cust["ラベル"]=="リピーター"]
        ns,rs=new["純売上"].sum(),rep["純売上"].sum()
        nc,rc=new["客数"].sum(),rep["客数"].sum()
        tc=nc+rc
        rr=(rc/tc*100) if tc>0 else 0
        nu=ns/nc if nc>0 else 0
        ru=rs/rc if rc>0 else 0

        seg=df_cust.groupby("ラベル").agg(客数=("客数","sum")).reset_index()
        fig=px.pie(seg,values="客数",names="ラベル",color="ラベル",color_discrete_map={"新規":"#c4a882","リピーター":"#5a3e2b"})
        fig.update_layout(title="客数構成（新規 vs リピーター）",margin=dict(t=50,b=30))
        cust_pie = fig_to_img(fig, 500, 400)

        cust_html = f"""
<div class="section-title">客層分析（新規 vs リピーター）</div>
<div class="kpi-grid">
  <div class="kpi"><div class="kv">{rr:.1f}%</div><div class="kl">リピーター率</div></div>
  <div class="kpi"><div class="kv">{nc:,.0f}人</div><div class="kl">新規客数</div></div>
  <div class="kpi"><div class="kv">{rc:,.0f}人</div><div class="kl">リピーター客数</div></div>
  <div class="kpi"><div class="kv">¥{nu:,.0f}</div><div class="kl">新規客単価</div></div>
  <div class="kpi"><div class="kv">¥{ru:,.0f}</div><div class="kl">リピーター客単価</div></div>
</div>
<div class="chart">{cust_pie}</div>"""

    two_col_row1 = f'<div class="two-col"><div class="col">{imgs[1]}</div><div class="col">{imgs[2]}</div></div>'
    two_col_row2 = ""
    if dept_img:
        two_col_row2 = f'<div class="two-col"><div class="col">{dept_img}</div><div class="col"></div></div>'

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>{store['name']} 売上レポート</title>
<style>
@page {{ size: A4 landscape; margin: 15mm; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: "Helvetica Neue","Hiragino Sans",sans-serif; color:#333; font-size:11px; }}
h1 {{ font-size:20px; color:#5a3e2b; margin-bottom:3px; }}
.sub {{ color:#888; font-size:10px; margin-bottom:15px; }}
.section-title {{ font-size:15px; color:#5a3e2b; font-weight:bold; margin:20px 0 10px; border-bottom:2px solid #c4a882; padding-bottom:5px; }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:8px; margin-bottom:15px; }}
.kpi {{ background:#faf9f7; border-radius:8px; padding:12px; text-align:center; border:1px solid #e8e4df; }}
.kv {{ font-size:16px; font-weight:bold; color:#5a3e2b; }}
.kl {{ font-size:9px; color:#888; margin-top:3px; }}
.chart {{ margin-bottom:15px; text-align:center; }}
.chart img {{ max-width:100%; }}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:15px; }}
.col {{ text-align:center; }}
.col img {{ max-width:100%; }}
.footer {{ text-align:center; color:#aaa; font-size:9px; margin-top:20px; padding:10px; border-top:1px solid #eee; }}
.page-break {{ page-break-before:always; }}
</style>
</head>
<body>
<h1>{store['name']} 売上レポート</h1>
<div class="sub">{d_from} 〜 {d_to} ｜ 作成日: {now}</div>

<div class="kpi-grid">
  <div class="kpi"><div class="kv">¥{total_sales:,.0f}</div><div class="kl">純売上</div></div>
  <div class="kpi"><div class="kv">{total_cust:,.0f}人</div><div class="kl">客数</div></div>
  <div class="kpi"><div class="kv">¥{avg_cust:,.0f}</div><div class="kl">客単価</div></div>
  <div class="kpi"><div class="kv">¥{avg_daily:,.0f}</div><div class="kl">日販平均</div></div>
  <div class="kpi"><div class="kv">{days}日</div><div class="kl">営業日数</div></div>
  <div class="kpi"><div class="kv">¥{gp:,.0f}</div><div class="kl">粗利</div></div>
  <div class="kpi"><div class="kv">{gp_rate:.1f}%</div><div class="kl">粗利率</div></div>
  <div class="kpi"><div class="kv">¥{disc:,.0f}</div><div class="kl">値引き合計</div></div>
</div>

<div class="section-title">日別売上推移</div>
<div class="chart">{imgs[0]}</div>

<div class="section-title">曜日別 ／ 客数・客単価</div>
{two_col_row1}

<div class="page-break"></div>

<div class="section-title">商品別売上ランキング</div>
<div class="chart">{prod_img}</div>

{"<div class='section-title'>部門別売上構成</div>" + '<div class="chart">' + dept_img + "</div>" if dept_img else ""}

{cust_html}

<div class="footer">このレポートはスマレジの売上データから自動生成されました</div>
</body>
</html>"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_name = f"report_{store_id}_{d_from.replace('/','')}-{d_to.replace('/','')}.pdf"
    html_tmp = OUTPUT_DIR / "_tmp_pdf.html"
    pdf_path = OUTPUT_DIR / pdf_name

    with open(html_tmp, "w", encoding="utf-8") as f:
        f.write(html)

    import subprocess
    result = subprocess.run([
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--headless", "--disable-gpu", "--no-sandbox",
        f"--print-to-pdf={pdf_path}",
        "--print-to-pdf-no-header",
        str(html_tmp),
    ], capture_output=True, text=True, timeout=30)

    html_tmp.unlink(missing_ok=True)

    if pdf_path.exists():
        print(f"PDF生成完了: {pdf_path}")
    else:
        print(f"Chrome PDF失敗。HTMLを代替出力します。")
        alt_path = OUTPUT_DIR / pdf_name.replace(".pdf", ".html")
        with open(alt_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML出力: {alt_path}")

    return pdf_path

if __name__ == "__main__":
    build_pdf()
