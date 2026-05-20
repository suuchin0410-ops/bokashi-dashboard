"""カフェ売上分析ダッシュボード（スマレジCSV対応）"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml
from pathlib import Path

from data_loader import load_daily, load_product, load_customer, load_department, save_uploaded_csv
from sync_drive import get_last_sync_info, get_local_file_summary

CONFIG_DIR = Path(__file__).parent / "config"
COLORS = ["#c4a882", "#5a3e2b", "#8b7355", "#d4c5a9", "#a0522d", "#deb887", "#8B4513"]


def load_config(store_id: str) -> dict:
    with open(CONFIG_DIR / f"{store_id}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 日別分析 ──

def render_kpi(df: pd.DataFrame):
    col1, col2, col3, col4, col5 = st.columns(5)
    total_sales = df["純売上"].sum()
    total_customers = df["客数"].sum()
    avg_per_customer = total_sales / total_customers if total_customers > 0 else 0
    active_days = len(df)
    avg_daily = total_sales / active_days if active_days > 0 else 0
    col1.metric("純売上", f"¥{total_sales:,.0f}")
    col2.metric("客数", f"{total_customers:,.0f}人")
    col3.metric("客単価", f"¥{avg_per_customer:,.0f}")
    col4.metric("営業日数", f"{active_days}日")
    col5.metric("日販平均", f"¥{avg_daily:,.0f}")


def render_monthly_summary(df: pd.DataFrame):
    st.subheader("月別サマリー")
    df_m = df.copy()
    df_m["年月"] = df_m["日付"].dt.to_period("M").astype(str)
    monthly = df_m.groupby("年月").agg(
        純売上=("純売上", "sum"), 客数=("客数", "sum"), 客単価=("客単価", "mean"),
        粗利=("粗利", "sum"), 営業日数=("純売上", "count"), 値引き=("値引き", "sum"),
    ).reset_index()
    monthly["日販平均"] = (monthly["純売上"] / monthly["営業日数"]).round(0)
    monthly["粗利率"] = (monthly["粗利"] / monthly["純売上"] * 100).round(1)
    monthly["客単価"] = monthly["客単価"].round(0)
    display = monthly[["年月", "純売上", "客数", "客単価", "日販平均", "粗利", "粗利率", "値引き", "営業日数"]].copy()
    display.columns = ["年月", "純売上", "客数", "客単価", "日販平均", "粗利", "粗利率(%)", "値引き", "営業日数"]
    st.dataframe(
        display.style.format({
            "純売上": "¥{:,.0f}", "客数": "{:,.0f}人", "客単価": "¥{:,.0f}",
            "日販平均": "¥{:,.0f}", "粗利": "¥{:,.0f}", "粗利率(%)": "{:.1f}%", "値引き": "¥{:,.0f}",
        }), use_container_width=True, hide_index=True,
    )


def render_daily_sales(df: pd.DataFrame):
    st.subheader("日別売上推移")
    daily = df[["日付", "純売上"]].copy()
    daily["7日移動平均"] = daily["純売上"].rolling(7, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily["日付"], y=daily["純売上"], name="日別売上", marker_color="#c4a882", opacity=0.7))
    fig.add_trace(go.Scatter(x=daily["日付"], y=daily["7日移動平均"], name="7日移動平均", line=dict(color="#5a3e2b", width=2)))
    fig.update_layout(xaxis_title="", yaxis_title="売上（円）", legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)


def render_weekday_analysis(df: pd.DataFrame):
    st.subheader("曜日別パフォーマンス")
    wn = ["月", "火", "水", "木", "金", "土", "日"]
    wd = df.groupby("曜日番号").agg(平均売上=("純売上", "mean"), 平均客数=("客数", "mean"), 日数=("純売上", "count")).reset_index()
    wd["曜日"] = wd["曜日番号"].map(lambda x: wn[x])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=wd["曜日"], y=wd["平均売上"], name="平均売上", marker_color="#c4a882"))
    fig.add_trace(go.Scatter(x=wd["曜日"], y=wd["平均客数"], name="平均客数", line=dict(color="#5a3e2b", width=2), yaxis="y2"))
    fig.update_layout(yaxis=dict(title="平均売上（円）"), yaxis2=dict(title="平均客数（人）", overlaying="y", side="right"), legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)


def render_customer_metrics(df: pd.DataFrame):
    st.subheader("客数・客単価推移")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["日付"], y=df["客数"], name="客数", marker_color="#c4a882", opacity=0.7))
    fig.add_trace(go.Scatter(x=df["日付"], y=df["客単価"], name="客単価", line=dict(color="#5a3e2b", width=2), yaxis="y2"))
    fig.update_layout(yaxis=dict(title="客数（人）"), yaxis2=dict(title="客単価（円）", overlaying="y", side="right"), legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)


def render_profitability(df: pd.DataFrame):
    st.subheader("粗利分析")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["日付"], y=df["粗利"], name="粗利", marker_color="#8b7355", opacity=0.7))
    fig.add_trace(go.Scatter(x=df["日付"], y=df["粗利率"], name="粗利率(%)", line=dict(color="#c0392b", width=2), yaxis="y2"))
    fig.update_layout(yaxis=dict(title="粗利（円）"), yaxis2=dict(title="粗利率(%)", overlaying="y", side="right", range=[0, 100]), legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)


def render_discount_analysis(df: pd.DataFrame):
    st.subheader("値引き・クーポン")
    discount_total = df["値引き"].sum()
    coupon_total = df["クーポン利用"].sum()
    sales_total = df["総売上"].sum()
    discount_rate = (discount_total / sales_total * 100) if sales_total > 0 else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("値引き合計", f"¥{discount_total:,.0f}")
    c2.metric("クーポン利用", f"¥{coupon_total:,.0f}")
    c3.metric("値引き率", f"{discount_rate:.1f}%")


# ── 商品分析 ──

def render_product_ranking(df_product: pd.DataFrame):
    st.subheader("商品別売上ランキング")
    ranking = df_product.groupby("商品名").agg(売上=("純売上", "sum"), 販売点数=("販売点数", "sum")).sort_values("売上", ascending=True).tail(15).reset_index()
    fig = px.bar(ranking, x="売上", y="商品名", orientation="h", color_discrete_sequence=["#c4a882"], text=ranking["売上"].apply(lambda x: f"¥{x:,.0f}"))
    fig.update_layout(xaxis_title="売上（円）", yaxis_title="", margin=dict(t=30, b=30, l=150))
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def render_category_breakdown(df_product: pd.DataFrame):
    st.subheader("カテゴリ別売上構成")
    cat = df_product.groupby("カテゴリ").agg(売上=("純売上", "sum"), 点数=("販売点数", "sum")).sort_values("売上", ascending=False).reset_index()
    fig = px.pie(cat, values="売上", names="カテゴリ", color_discrete_sequence=COLORS)
    fig.update_layout(margin=dict(t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(cat.style.format({"売上": "¥{:,.0f}", "点数": "{:,.0f}"}), use_container_width=True, hide_index=True)


def render_product_cost(df_product: pd.DataFrame):
    st.subheader("商品別原価率")
    data = df_product[df_product["原価"] > 0].copy()
    cost = data.groupby("商品名").agg(売上=("純売上", "sum"), 原価=("原価", "sum")).reset_index()
    cost["原価率"] = (cost["原価"] / cost["売上"] * 100).round(1)
    cost = cost.sort_values("原価率", ascending=False).head(15)
    fig = px.bar(cost, x="原価率", y="商品名", orientation="h", color="原価率", color_continuous_scale=["#c4a882", "#c0392b"], text=cost["原価率"].apply(lambda x: f"{x:.1f}%"))
    fig.update_layout(xaxis_title="原価率(%)", yaxis_title="", margin=dict(t=30, b=30, l=150), coloraxis_showscale=False)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


# ── 部門別分析 ──

def render_department_sales(df_dept: pd.DataFrame):
    st.subheader("部門別売上構成")
    dept = df_dept.groupby("部門名").agg(
        売上=("純売上", "sum"), 原価=("原価", "sum"),
        販売点数=("販売点数", "sum"),
    ).sort_values("売上", ascending=False).reset_index()
    dept["粗利"] = dept["売上"] - dept["原価"]
    dept["粗利率"] = (dept["粗利"] / dept["売上"] * 100).round(1)
    dept["構成比"] = (dept["売上"] / dept["売上"].sum() * 100).round(1)

    col_l, col_r = st.columns(2)
    with col_l:
        fig = px.pie(dept, values="売上", names="部門名", color_discrete_sequence=COLORS)
        fig.update_layout(margin=dict(t=30, b=30))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        fig = px.bar(dept, x="部門名", y="売上", color="部門名", color_discrete_sequence=COLORS, text=dept["売上"].apply(lambda x: f"¥{x:,.0f}"))
        fig.update_layout(xaxis_title="", yaxis_title="売上（円）", showlegend=False, margin=dict(t=30, b=30))
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        dept[["部門名", "売上", "原価", "粗利", "粗利率", "販売点数", "構成比"]].style.format({
            "売上": "¥{:,.0f}", "原価": "¥{:,.0f}", "粗利": "¥{:,.0f}",
            "粗利率": "{:.1f}%", "販売点数": "{:,.0f}", "構成比": "{:.1f}%",
        }), use_container_width=True, hide_index=True,
    )


def render_department_profitability(df_dept: pd.DataFrame):
    st.subheader("部門別粗利率比較")
    dept = df_dept.groupby("部門名").agg(売上=("純売上", "sum"), 原価=("原価", "sum")).reset_index()
    dept["粗利率"] = ((dept["売上"] - dept["原価"]) / dept["売上"] * 100).round(1)
    dept = dept.sort_values("粗利率", ascending=True)

    fig = px.bar(dept, x="粗利率", y="部門名", orientation="h", color="粗利率",
                 color_continuous_scale=["#c0392b", "#c4a882", "#27ae60"],
                 text=dept["粗利率"].apply(lambda x: f"{x:.1f}%"))
    fig.update_layout(xaxis_title="粗利率(%)", yaxis_title="", margin=dict(t=30, b=30, l=150), coloraxis_showscale=False)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


# ── 客層別分析 ──

def render_customer_segment_kpi(df_cust: pd.DataFrame):
    st.subheader("新規 vs リピーター")

    new = df_cust[df_cust["ラベル"] == "新規"]
    repeat = df_cust[df_cust["ラベル"] == "リピーター"]

    new_sales = new["純売上"].sum()
    repeat_sales = repeat["純売上"].sum()
    new_count = new["客数"].sum()
    repeat_count = repeat["客数"].sum()
    total_count = new_count + repeat_count
    new_unit = new_sales / new_count if new_count > 0 else 0
    repeat_unit = repeat_sales / repeat_count if repeat_count > 0 else 0
    repeat_rate = (repeat_count / total_count * 100) if total_count > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("リピーター率", f"{repeat_rate:.1f}%")
    c2.metric("リピーター客数", f"{repeat_count:,.0f}人")
    c3.metric("リピーター客単価", f"¥{repeat_unit:,.0f}")
    c4.metric("新規客単価", f"¥{new_unit:,.0f}")


def render_customer_segment_charts(df_cust: pd.DataFrame):
    total = df_cust.groupby("ラベル").agg(
        売上=("純売上", "sum"), 客数=("客数", "sum"), 販売点数=("販売点数", "sum"),
    ).reset_index()
    total["客単価"] = (total["売上"] / total["客数"]).round(0)
    total["点数/人"] = (total["販売点数"] / total["客数"]).round(1)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("**売上構成**")
        fig = px.pie(total, values="売上", names="ラベル", color="ラベル",
                     color_discrete_map={"新規": "#c4a882", "リピーター": "#5a3e2b"})
        fig.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("**客数構成**")
        fig = px.pie(total, values="客数", names="ラベル", color="ラベル",
                     color_discrete_map={"新規": "#c4a882", "リピーター": "#5a3e2b"})
        fig.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        total[["ラベル", "売上", "客数", "客単価", "販売点数", "点数/人"]].style.format({
            "売上": "¥{:,.0f}", "客数": "{:,.0f}人", "客単価": "¥{:,.0f}",
            "販売点数": "{:,.0f}", "点数/人": "{:.1f}",
        }), use_container_width=True, hide_index=True,
    )


def render_customer_segment_monthly(df_cust: pd.DataFrame):
    if df_cust["年月"].nunique() < 2:
        return
    st.subheader("月別 新規/リピーター推移")
    monthly = df_cust.groupby(["年月", "ラベル"]).agg(客数=("客数", "sum"), 売上=("純売上", "sum")).reset_index()

    fig = px.bar(monthly, x="年月", y="客数", color="ラベル", barmode="group",
                 color_discrete_map={"新規": "#c4a882", "リピーター": "#5a3e2b"},
                 text="客数")
    fig.update_layout(xaxis_title="", yaxis_title="客数（人）", margin=dict(t=30, b=30))
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


# ── トレンド分析 ──

def _calc_daily_rate(df_product: pd.DataFrame, df_daily: pd.DataFrame) -> pd.DataFrame:
    months = sorted(df_product["年月"].unique())
    df_d = df_daily.copy()
    df_d["年月"] = df_d["日付"].dt.to_period("M").astype(str)
    days_per_month = df_d.groupby("年月")["日付"].nunique().to_dict()

    rows = []
    for month in months:
        days = days_per_month.get(month, 1)
        mp = df_product[df_product["年月"] == month]
        for _, r in mp.groupby("商品名").agg(
            純売上=("純売上", "sum"), 販売点数=("販売点数", "sum"), カテゴリ=("カテゴリ", "first"),
        ).reset_index().iterrows():
            rows.append({
                "年月": month, "商品名": r["商品名"], "カテゴリ": r["カテゴリ"],
                "純売上": r["純売上"], "販売点数": r["販売点数"],
                "営業日数": days,
                "日販売上": round(r["純売上"] / days),
                "日販点数": round(r["販売点数"] / days, 1),
            })
    return pd.DataFrame(rows)


def render_product_trend(df_product: pd.DataFrame, df_daily: pd.DataFrame):
    months = sorted(df_product["年月"].unique())
    if len(months) < 2:
        st.info("トレンド分析には2ヶ月以上のデータが必要です。")
        return

    rate_df = _calc_daily_rate(df_product, df_daily)

    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        base_month = st.selectbox("比較元（前月）", months[:-1], index=len(months) - 2, key="trend_base")
    with col_sel2:
        idx = months.index(base_month)
        compare_months = months[idx + 1:]
        comp_month = st.selectbox("比較先（当月）", compare_months, index=0, key="trend_comp")

    base = rate_df[rate_df["年月"] == base_month][["商品名", "カテゴリ", "日販売上", "日販点数"]].rename(
        columns={"日販売上": "前月日販", "日販点数": "前月点数"})
    comp = rate_df[rate_df["年月"] == comp_month][["商品名", "日販売上", "日販点数"]].rename(
        columns={"日販売上": "当月日販", "日販点数": "当月点数"})

    merged = pd.merge(base, comp, on="商品名", how="outer").fillna(0)
    merged["売上変化"] = merged["当月日販"] - merged["前月日販"]
    merged["変化率"] = merged.apply(
        lambda r: round(r["売上変化"] / r["前月日販"] * 100, 1) if r["前月日販"] > 0 else (
            100.0 if r["当月日販"] > 0 else 0.0), axis=1)

    growing = merged[merged["売上変化"] > 0].sort_values("売上変化", ascending=True).tail(10)
    declining = merged[merged["売上変化"] < 0].sort_values("売上変化", ascending=False).tail(10)

    base_days = rate_df[rate_df["年月"] == base_month]["営業日数"].iloc[0] if len(rate_df[rate_df["年月"] == base_month]) > 0 else 0
    comp_days = rate_df[rate_df["年月"] == comp_month]["営業日数"].iloc[0] if len(rate_df[rate_df["年月"] == comp_month]) > 0 else 0

    st.caption(f"{base_month}（{base_days}営業日）→ {comp_month}（{comp_days}営業日）の日販ベース比較")

    col_up, col_down = st.columns(2)
    with col_up:
        st.subheader("伸びている商品")
        if growing.empty:
            st.info("伸びている商品はありません。")
        else:
            fig = go.Figure(go.Bar(
                x=growing["売上変化"], y=growing["商品名"], orientation="h",
                marker_color="#27ae60",
                text=growing.apply(lambda r: f"+¥{r['売上変化']:,.0f}/日 ({r['変化率']:+.0f}%)", axis=1),
            ))
            fig.update_layout(xaxis_title="日販変化（円）", yaxis_title="", margin=dict(t=10, b=30, l=150))
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

    with col_down:
        st.subheader("落ちている商品")
        if declining.empty:
            st.info("落ちている商品はありません。")
        else:
            dec_sorted = declining.sort_values("売上変化", ascending=True)
            fig = go.Figure(go.Bar(
                x=dec_sorted["売上変化"].abs(), y=dec_sorted["商品名"], orientation="h",
                marker_color="#c0392b",
                text=dec_sorted.apply(lambda r: f"¥{r['売上変化']:,.0f}/日 ({r['変化率']:+.0f}%)", axis=1),
            ))
            fig.update_layout(xaxis_title="日販減少（円）", yaxis_title="", margin=dict(t=10, b=30, l=150))
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("カテゴリ別トレンド")
    cat_trend = merged.groupby("カテゴリ").agg(
        前月日販=("前月日販", "sum"), 当月日販=("当月日販", "sum"),
    ).reset_index()
    cat_trend["変化"] = cat_trend["当月日販"] - cat_trend["前月日販"]
    cat_trend["変化率"] = cat_trend.apply(
        lambda r: round(r["変化"] / r["前月日販"] * 100, 1) if r["前月日販"] > 0 else 0, axis=1)
    cat_trend = cat_trend.sort_values("変化", ascending=False)

    fig = go.Figure()
    fig.add_trace(go.Bar(name=base_month, x=cat_trend["カテゴリ"], y=cat_trend["前月日販"],
                         marker_color="#c4a882"))
    fig.add_trace(go.Bar(name=comp_month, x=cat_trend["カテゴリ"], y=cat_trend["当月日販"],
                         marker_color="#5a3e2b"))
    fig.update_layout(barmode="group", yaxis_title="日販合計（円）", margin=dict(t=30, b=30),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        cat_trend.style.format({
            "前月日販": "¥{:,.0f}", "当月日販": "¥{:,.0f}",
            "変化": "¥{:,.0f}", "変化率": "{:+.1f}%",
        }), use_container_width=True, hide_index=True,
    )

    st.divider()
    st.subheader("全商品トレンド一覧")
    detail = merged.sort_values("売上変化", ascending=False).copy()
    detail = detail[detail["前月日販"] + detail["当月日販"] > 0]
    st.dataframe(
        detail[["商品名", "カテゴリ", "前月日販", "当月日販", "売上変化", "変化率"]].style.format({
            "前月日販": "¥{:,.0f}", "当月日販": "¥{:,.0f}",
            "売上変化": "¥{:,.0f}", "変化率": "{:+.1f}%",
        }), use_container_width=True, hide_index=True,
    )


# ── メイン ──

def main():
    st.set_page_config(page_title="bokashi 売上分析", layout="wide")

    configs = [f.stem for f in CONFIG_DIR.glob("*.yaml")]
    if not configs:
        st.error("設定ファイルが見つかりません。config/フォルダを確認してください。")
        return

    store_id = configs[0] if len(configs) == 1 else st.sidebar.selectbox("店舗を選択", configs)
    config = load_config(store_id)
    store = config["store"]

    st.title(f"{store['name']} 売上分析")
    st.caption(f"{store['location']} | 営業時間 {store['business_hours']['open']}〜{store['business_hours']['close']}")

    sales_dir = Path(__file__).parent / config["data"]["sales_dir"]

    with st.sidebar:
        st.header("データ取り込み")
        uploaded = st.file_uploader(
            "スマレジCSVをアップロード",
            type=["csv"],
            accept_multiple_files=True,
            help="daily_YYYY_MM.csv / product_YYYY_MM.csv / department_YYYY_MM.csv / customer_YYYY_MM.csv",
        )
        if uploaded:
            for f in uploaded:
                dest = save_uploaded_csv(f, sales_dir)
                st.success(f"{f.name} を保存しました")
            st.rerun()

        sync_info = get_last_sync_info()
        local_files = get_local_file_summary()
        with st.expander(f"Google Drive同期（{len(local_files)}ファイル）", expanded=False):
            if sync_info:
                st.caption(f"最終同期: {sync_info['last_sync']}")
            else:
                st.caption("未同期（Claudeに「データ更新して」と伝えてください）")
            if local_files:
                for f in local_files:
                    st.text(f"  {f['name']}  ({f['size']:,}B)")
            st.info("💡 Claudeが Google Drive から最新CSVを取得・同期します。")

        st.divider()

    df_daily_all = load_daily(sales_dir)
    df_product_all = load_product(sales_dir)
    df_customer_all = load_customer(sales_dir)
    df_department_all = load_department(sales_dir)

    if df_daily_all.empty:
        st.warning("売上データが見つかりません。サイドバーからCSVをアップロードしてください。")
        return

    df_daily_all["年月"] = df_daily_all["日付"].dt.to_period("M").astype(str)
    all_months = sorted(df_daily_all["年月"].unique())

    with st.sidebar:
        st.header("フィルター")
        view_mode = st.radio("表示モード", ["月別", "期間指定"], horizontal=True, key="view_mode")

        if view_mode == "月別":
            selected_month = st.selectbox("月を選択", ["全期間"] + all_months,
                                          index=len(all_months), key="month_filter")
        else:
            date_range = st.date_input(
                "期間",
                value=(df_daily_all["日付"].min(), df_daily_all["日付"].max()),
                min_value=df_daily_all["日付"].min(),
                max_value=df_daily_all["日付"].max(),
            )

    if view_mode == "月別" and selected_month != "全期間":
        df_daily = df_daily_all[df_daily_all["年月"] == selected_month].copy()
        df_product = df_product_all[df_product_all["年月"] == selected_month].copy() if not df_product_all.empty else df_product_all
        df_customer = df_customer_all[df_customer_all["年月"] == selected_month].copy() if not df_customer_all.empty else df_customer_all
        df_department = df_department_all[df_department_all["年月"] == selected_month].copy() if not df_department_all.empty else df_department_all
    elif view_mode == "期間指定" and isinstance(date_range, tuple) and len(date_range) == 2:
        df_daily = df_daily_all[
            (df_daily_all["日付"] >= pd.Timestamp(date_range[0]))
            & (df_daily_all["日付"] <= pd.Timestamp(date_range[1]))
        ].copy()
        df_product = df_product_all.copy()
        df_customer = df_customer_all.copy()
        df_department = df_department_all.copy()
    else:
        df_daily = df_daily_all.copy()
        df_product = df_product_all.copy()
        df_customer = df_customer_all.copy()
        df_department = df_department_all.copy()

    tab_daily, tab_product, tab_dept, tab_customer, tab_trend = st.tabs(
        ["日別分析", "商品分析", "部門別分析", "客層分析", "トレンド分析"]
    )

    with tab_daily:
        render_kpi(df_daily)
        st.divider()
        render_monthly_summary(df_daily)
        render_daily_sales(df_daily)
        col_l, col_r = st.columns(2)
        with col_l:
            render_weekday_analysis(df_daily)
        with col_r:
            render_customer_metrics(df_daily)
        col_l2, col_r2 = st.columns(2)
        with col_l2:
            render_profitability(df_daily)
        with col_r2:
            render_discount_analysis(df_daily)

    with tab_product:
        if df_product.empty:
            st.warning("商品別売上データが見つかりません。")
        else:
            render_product_ranking(df_product)
            col_l3, col_r3 = st.columns(2)
            with col_l3:
                render_category_breakdown(df_product)
            with col_r3:
                render_product_cost(df_product)

    with tab_dept:
        if df_department.empty:
            st.warning("部門別売上データが見つかりません。")
        else:
            render_department_sales(df_department)
            render_department_profitability(df_department)

    with tab_customer:
        if df_customer.empty:
            st.warning("客層別売上データが見つかりません。")
        else:
            render_customer_segment_kpi(df_customer)
            render_customer_segment_charts(df_customer)
            render_customer_segment_monthly(df_customer)

    with tab_trend:
        if df_product_all.empty:
            st.warning("商品別売上データが見つかりません。")
        else:
            render_product_trend(df_product_all, df_daily_all)

if __name__ == "__main__":
    main()
