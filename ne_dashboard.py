import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date

st.set_page_config(
    page_title="売上ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.stApp { background-color: #f5f7fa; }

/* サイドバー全体 */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d2137 0%, #1a3a5c 100%);
    min-width: 220px !important;
}
section[data-testid="stSidebar"] * { color: #c8dcf0 !important; }
section[data-testid="stSidebar"] hr { border-color: #2a4a6c !important; }

/* サイドバーのボタン（統一スタイル） */
section[data-testid="stSidebar"] .stButton > button {
    background-color: transparent !important;
    color: #c8dcf0 !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 6px !important;
    text-align: left !important;
    font-size: 13px !important;
    padding: 8px 12px !important;
    margin-bottom: 2px !important;
    width: 100% !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background-color: rgba(255,255,255,0.1) !important;
    color: white !important;
    border-color: rgba(255,255,255,0.3) !important;
}

/* サイドバーのエクスパンダー（ボタンと統一） */
section[data-testid="stSidebar"] details {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 6px !important;
    margin-bottom: 4px !important;
    padding: 2px 0 !important;
}
section[data-testid="stSidebar"] details summary {
    color: #c8dcf0 !important;
    font-size: 13px !important;
    padding: 6px 12px !important;
}
section[data-testid="stSidebar"] details summary:hover {
    background: rgba(255,255,255,0.08) !important;
}
section[data-testid="stSidebar"] details[open] {
    background: rgba(255,255,255,0.05) !important;
}
section[data-testid="stSidebar"] details[open] summary {
    color: white !important;
    font-weight: 600 !important;
}

/* KPIカード */
.kpi-wrap {
    background: white;
    border-radius: 10px;
    padding: 16px 18px 10px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    margin-bottom: 4px;
}
.kpi-label { font-size: 12px; color: #6b7280; font-weight: 600; margin-bottom: 4px; }
.kpi-main  { font-size: 26px; font-weight: 800; color: #111827; line-height: 1.1; }
.kpi-sub   { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.kpi-diff-up   { color: #16a34a; font-weight: 700; font-size: 12px; }
.kpi-diff-down { color: #dc2626; font-weight: 700; font-size: 12px; }
.sec-title {
    font-size: 14px; font-weight: 700; color: #1a3a5c;
    margin: 16px 0 8px 0; padding-bottom: 6px;
    border-bottom: 2px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)

if 'access_token' not in st.session_state:
    try:
        st.session_state.access_token  = st.secrets['nextengine']['access_token']
        st.session_state.refresh_token = st.secrets['nextengine']['refresh_token']
        st.session_state.client_id     = st.secrets['nextengine']['client_id']
        st.session_state.client_secret = st.secrets['nextengine']['client_secret']
    except Exception:
        st.error("⚠️ 認証情報が設定されていません。")
        st.stop()

if 'page' not in st.session_state:
    st.session_state.page = '全体サマリー'

BASE_URL = 'https://api.next-engine.org/'

def ne_request(endpoint, params=None):
    data = {
        'access_token':  st.session_state.access_token,
        'refresh_token': st.session_state.refresh_token,
    }
    if params:
        data.update(params)
    res = requests.post(BASE_URL + endpoint, data=data)
    result = res.json()
    if 'access_token' in result:
        st.session_state.access_token  = result['access_token']
        st.session_state.refresh_token = result['refresh_token']
    return result

@st.cache_data(ttl=300)
def get_orders(_dummy, start=None, end=None):
    all_orders = []
    offset, limit = 0, 100
    while True:
        params = {
            'limit': str(limit), 'offset': str(offset),
            'fields': 'receive_order_id,receive_order_shop_id,receive_order_date,receive_order_total_amount,receive_order_order_status_name',
        }
        if start:
            params['receive_order_date-gte'] = f'{start} 00:00:00'
        if end:
            params['receive_order_date-lte'] = f'{end} 23:59:59'
        result = ne_request('api_v1_receiveorder_base/search', params)
        if result.get('result') != 'success':
            break
        data = result.get('data', [])
        all_orders.extend(data)
        if len(data) < limit:
            break
        offset += limit
    return all_orders

@st.cache_data(ttl=300)
def get_stock(_dummy, threshold=10):
    result = ne_request('api_v1_master_stock/search', {
        'limit': '100', 'offset': '0',
        'fields': 'goods_id,goods_name,stock_quantity,stock_free_quantity',
    })
    if result.get('result') != 'success':
        return []
    return [s for s in result.get('data', []) if
            float(s.get('stock_free_quantity') or s.get('stock_quantity') or 0) <= threshold]

def make_df(orders):
    if not orders:
        return pd.DataFrame()
    df = pd.DataFrame(orders)
    df['receive_order_date'] = pd.to_datetime(df['receive_order_date'])
    df['receive_order_total_amount'] = pd.to_numeric(df['receive_order_total_amount'], errors='coerce').fillna(0)
    df['date']  = df['receive_order_date'].dt.strftime('%Y-%m-%d')
    df['month'] = df['receive_order_date'].dt.strftime('%Y-%m')
    df['week']  = df['receive_order_date'].dt.strftime('%Y-W%U')
    df['weekday_num']  = df['receive_order_date'].dt.weekday
    df['weekday_name'] = df['weekday_num'].map({0:'月',1:'火',2:'水',3:'木',4:'金',5:'土',6:'日'})
    df['hour'] = df['receive_order_date'].dt.hour
    return df

def sparkline(series, color='#00bfa5'):
    vals = list(series.values) if len(series) > 0 else [0, 0]
    fig = go.Figure(go.Scatter(
        y=vals, mode='lines',
        line=dict(color=color, width=2)
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=50,
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        showlegend=False
    )
    return fig

def pct_diff(cur, prev):
    if prev and prev != 0:
        p = (cur - prev) / abs(prev) * 100
        sym = '▲' if p >= 0 else '▼'
        cls = 'kpi-diff-up' if p >= 0 else 'kpi-diff-down'
        return f'<span class="{cls}">{sym}{abs(p):.1f}%</span>'
    return ''

COLORS = ['#00bfa5','#1a6bc8','#ea580c','#7c3aed','#0891b2','#be185d']

# =====================
# サイドバー
# =====================
with st.sidebar:
    st.markdown("### 📊 売上ダッシュボード")
    st.markdown("---")
    nav_items = {
        'TOP': [],
        '全体サマリー': [],
        '商品分析': ['商品別売上', '商品ランキング'],
        '店舗分析': ['店舗別売上', '曜日別分析', '時間帯別分析'],
        '受注分析': ['受注一覧', 'リピート分析'],
        '在庫管理': ['在庫アラート'],
    }
    for nav, subs in nav_items.items():
        if not subs:
            if st.button(nav, key=f'nav_{nav}', use_container_width=True):
                st.session_state.page = nav
        else:
            with st.expander(nav, expanded=(st.session_state.page in subs)):
                for sub in subs:
                    if st.button(sub, key=f'nav_{sub}', use_container_width=True):
                        st.session_state.page = sub
    st.markdown("---")
    if st.button("🔄 データ更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# =====================
# フィルターバー
# =====================
page = st.session_state.page
today = date.today()

fc1, fc2, fc3, fc4, fc5 = st.columns([2.5, 1.5, 1.5, 1.5, 1.5])
with fc1:
    st.markdown(f"**{page}**　<small style='color:#6b7280'>※当日時点のデータを集計しています</small>", unsafe_allow_html=True)
with fc2:
    period = st.selectbox("対象期間", ['今月','先月','今週','先週','カスタム'], label_visibility='collapsed')
with fc3:
    if period == 'カスタム':
        start_d = st.date_input("開始日", today.replace(day=1), label_visibility='collapsed')
    elif period == '今月':
        start_d = today.replace(day=1)
    elif period == '先月':
        start_d = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    elif period == '今週':
        start_d = today - timedelta(days=today.weekday())
    else:
        start_d = today - timedelta(days=today.weekday() + 7)
    if period != 'カスタム':
        st.markdown(f"<small style='color:#6b7280'>{start_d}</small>", unsafe_allow_html=True)
with fc4:
    if period == 'カスタム':
        end_d = st.date_input("終了日", today, label_visibility='collapsed')
    elif period == '先月':
        end_d = today.replace(day=1) - timedelta(days=1)
    elif period == '先週':
        end_d = today - timedelta(days=today.weekday() + 1)
    else:
        end_d = today
    if period != 'カスタム':
        st.markdown(f"<small style='color:#6b7280'>{end_d}</small>", unsafe_allow_html=True)
with fc5:
    unit = st.selectbox("集計単位", ['日','週','月'], label_visibility='collapsed')

st.markdown("---")

# =====================
# データ取得
# =====================
start_str  = str(start_d)
end_str    = str(end_d)
prev_start = str(start_d - timedelta(days=365))
prev_end   = str(end_d   - timedelta(days=365))

with st.spinner('データを取得中...'):
    orders_cur  = get_orders(st.session_state.access_token, start_str, end_str)
    orders_prev = get_orders(st.session_state.access_token + '_prev', prev_start, prev_end)

df_cur  = make_df(orders_cur)
df_prev = make_df(orders_prev)

if df_cur.empty:
    st.warning("選択期間に受注データがありません。")
    st.stop()

unit_col = {'日': 'date', '週': 'week', '月': 'month'}[unit]

# =====================
# 全体サマリー / TOP
# =====================
if page in ('全体サマリー', 'TOP'):
    cur_sales  = df_cur['receive_order_total_amount'].sum()
    prev_sales = df_prev['receive_order_total_amount'].sum() if not df_prev.empty else 0
    cur_count  = len(df_cur)
    prev_count = len(df_prev) if not df_prev.empty else 0
    cur_tanka  = cur_sales / cur_count if cur_count else 0
    prev_tanka = prev_sales / prev_count if prev_count else 0

    ts_cur = df_cur.groupby(unit_col)['receive_order_total_amount'].sum().reset_index()
    ts_cur.columns = ['period', '売上']

    fig_main = go.Figure()
    fig_main.add_trace(go.Scatter(
        x=ts_cur['period'], y=ts_cur['売上'],
        mode='lines+markers', name='対象',
        line=dict(color='#00bfa5', width=2.5), marker=dict(size=5)
    ))
    if not df_prev.empty:
        ts_prev = df_prev.groupby(unit_col)['receive_order_total_amount'].sum().reset_index()
        ts_prev.columns = ['period', '売上']
        fig_main.add_trace(go.Scatter(
            x=ts_prev['period'], y=ts_prev['売上'],
            mode='lines', name='前年',
            line=dict(color='#d1d5db', width=1.5, dash='dot')
        ))
    fig_main.update_layout(
        height=200, margin=dict(l=0,r=0,t=10,b=0),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation='h', y=1.15, x=1, xanchor='right'),
        xaxis=dict(showgrid=False, tickfont=dict(size=10), type='category'),
        yaxis=dict(showgrid=True, gridcolor='#f3f4f6', tickformat=',.0f'),
    )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-wrap">
            <div class="kpi-label">受注金額</div>
            <div class="kpi-main">¥{int(cur_sales):,}</div>
            <div class="kpi-sub">前年 ¥{int(prev_sales):,} {pct_diff(cur_sales, prev_sales)}</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(sparkline(ts_cur['売上']), use_container_width=True, config={'displayModeBar': False})
    with k2:
        ts_c = df_cur.groupby(unit_col)['receive_order_id'].count()
        st.markdown(f"""<div class="kpi-wrap">
            <div class="kpi-label">受注件数</div>
            <div class="kpi-main">{cur_count:,}</div>
            <div class="kpi-sub">前年 {prev_count:,} {pct_diff(cur_count, prev_count)}</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(sparkline(ts_c, '#1a6bc8'), use_container_width=True, config={'displayModeBar': False})
    with k3:
        ts_t = df_cur.groupby(unit_col).apply(
            lambda x: x['receive_order_total_amount'].sum() / len(x) if len(x) > 0 else 0
        )
        st.markdown(f"""<div class="kpi-wrap">
            <div class="kpi-label">受注単価</div>
            <div class="kpi-main">¥{int(cur_tanka):,}</div>
            <div class="kpi-sub">前年 ¥{int(prev_tanka):,} {pct_diff(cur_tanka, prev_tanka)}</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(sparkline(ts_t, '#ea580c'), use_container_width=True, config={'displayModeBar': False})
    with k4:
        st.markdown(f"""<div class="kpi-wrap">
            <div class="kpi-label">対象店舗数</div>
            <div class="kpi-main">{df_cur['receive_order_shop_id'].nunique()}</div>
            <div class="kpi-sub">{start_str} ～ {end_str}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="sec-title">📈 受注金額推移</div>', unsafe_allow_html=True)
    st.plotly_chart(fig_main, use_container_width=True, config={'displayModeBar': False})

    t1, t2 = st.columns(2)
    with t1:
        st.markdown('<div class="sec-title">🏪 店舗別データ</div>', unsafe_allow_html=True)
        shop_cur  = df_cur.groupby('receive_order_shop_id')['receive_order_total_amount'].sum()
        shop_prev = df_prev.groupby('receive_order_shop_id')['receive_order_total_amount'].sum() if not df_prev.empty else pd.Series(dtype=float)
        shop_tbl  = pd.DataFrame({'対象': shop_cur, '前年': shop_prev}).fillna(0).reset_index()
        shop_tbl.columns = ['店舗ID','対象','前年']
        shop_tbl['前年比'] = shop_tbl.apply(lambda r: f"{r['対象']/r['前年']*100:.0f}%" if r['前年'] > 0 else '-', axis=1)
        shop_tbl['対象'] = shop_tbl['対象'].apply(lambda x: f"¥{int(x):,}")
        shop_tbl['前年'] = shop_tbl['前年'].apply(lambda x: f"¥{int(x):,}" if x > 0 else '-')
        st.dataframe(shop_tbl, use_container_width=True, hide_index=True)
    with t2:
        st.markdown('<div class="sec-title">📊 ステータス別データ</div>', unsafe_allow_html=True)
        status_tbl = df_cur.groupby('receive_order_order_status_name').agg(
            受注件数=('receive_order_id','count'),
            売上合計=('receive_order_total_amount','sum')
        ).reset_index()
        status_tbl.columns = ['ステータス','受注件数','売上合計']
        status_tbl['売上合計'] = status_tbl['売上合計'].apply(lambda x: f"¥{int(x):,}")
        st.dataframe(status_tbl, use_container_width=True, hide_index=True)

elif page == '商品別売上':
    st.markdown("## 📦 商品別売上")
    ts = df_cur.groupby(unit_col)['receive_order_total_amount'].sum().reset_index()
    ts.columns = ['period','売上']
    fig = px.line(ts, x='period', y='売上', markers=True, color_discrete_sequence=['#00bfa5'])
    fig.update_xaxes(type='category')
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', height=250, margin=dict(t=10,b=0))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    tbl = df_cur.groupby('receive_order_shop_id').agg(
        受注件数=('receive_order_id','count'), 売上合計=('receive_order_total_amount','sum')
    ).reset_index().sort_values('売上合計', ascending=False)
    tbl.columns = ['店舗ID','受注件数','売上合計']
    tbl['売上合計'] = tbl['売上合計'].apply(lambda x: f"¥{int(x):,}")
    st.dataframe(tbl, use_container_width=True, hide_index=True)

elif page == '商品ランキング':
    st.markdown("## 🏆 商品ランキング")
    st.info("商品別ランキングには受注明細APIが必要です。現在は店舗別ランキングを表示しています。")
    rank = df_cur.groupby('receive_order_shop_id').agg(
        受注件数=('receive_order_id','count'), 売上合計=('receive_order_total_amount','sum')
    ).reset_index().sort_values('売上合計', ascending=False).reset_index(drop=True)
    rank.index += 1
    rank.columns = ['店舗ID','受注件数','売上合計']
    rank['売上合計'] = rank['売上合計'].apply(lambda x: f"¥{int(x):,}")
    st.dataframe(rank, use_container_width=True)

elif page == '店舗別売上':
    st.markdown("## 🏪 店舗別売上")
    shop = df_cur.groupby('receive_order_shop_id').agg(
        売上合計=('receive_order_total_amount','sum'), 受注件数=('receive_order_id','count')
    ).reset_index().sort_values('売上合計', ascending=False)
    shop.columns = ['店舗ID','売上合計','受注件数']
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(shop, x='店舗ID', y='売上合計', color='店舗ID',
                     color_discrete_sequence=COLORS, text='受注件数')
        fig.update_xaxes(type='category')
        fig.update_traces(texttemplate='%{text}件', textposition='outside')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', showlegend=False, height=280, margin=dict(t=10,b=0))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    with c2:
        fig2 = px.pie(shop, names='店舗ID', values='売上合計', hole=0.45, color_discrete_sequence=COLORS)
        fig2.update_layout(paper_bgcolor='white', height=280, margin=dict(t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
    shop['売上合計'] = shop['売上合計'].apply(lambda x: f"¥{int(x):,}")
    st.dataframe(shop, use_container_width=True, hide_index=True)

elif page == '曜日別分析':
    st.markdown("## 📅 曜日別分析")
    weekday_order = ['月','火','水','木','金','土','日']
    wday = df_cur.groupby('weekday_name').agg(
        売上合計=('receive_order_total_amount','sum'), 受注件数=('receive_order_id','count')
    ).reset_index()
    wday['weekday_name'] = pd.Categorical(wday['weekday_name'], categories=weekday_order, ordered=True)
    wday = wday.sort_values('weekday_name')
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(wday, x='weekday_name', y='売上合計', color_discrete_sequence=['#00bfa5'], labels={'weekday_name':'曜日'})
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', height=300, margin=dict(t=10,b=0))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    with c2:
        fig2 = px.bar(wday, x='weekday_name', y='受注件数', color_discrete_sequence=['#1a6bc8'], labels={'weekday_name':'曜日'})
        fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', height=300, margin=dict(t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})

elif page == '時間帯別分析':
    st.markdown("## 🕐 時間帯別分析")
    hour_df = df_cur.groupby('hour').agg(
        売上合計=('receive_order_total_amount','sum'), 受注件数=('receive_order_id','count')
    ).reset_index().sort_values('hour')
    hour_df['hour_label'] = hour_df['hour'].apply(lambda x: f"{x:02d}時")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(hour_df, x='hour_label', y='売上合計', color_discrete_sequence=['#00bfa5'], labels={'hour_label':'時間帯'})
        fig.update_xaxes(type='category')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', height=300, margin=dict(t=10,b=0))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    with c2:
        fig2 = px.bar(hour_df, x='hour_label', y='受注件数', color_discrete_sequence=['#ea580c'], labels={'hour_label':'時間帯'})
        fig2.update_xaxes(type='category')
        fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', height=300, margin=dict(t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})

elif page == '受注一覧':
    st.markdown("## 📋 受注一覧")
    st.caption(f"対象件数: {len(df_cur)}件")
    show = df_cur[['receive_order_id','date','receive_order_shop_id',
                   'receive_order_total_amount','receive_order_order_status_name']].copy()
    show.columns = ['受注ID','注文日','店舗ID','合計金額(円)','ステータス']
    show['合計金額(円)'] = show['合計金額(円)'].apply(lambda x: f"¥{int(x):,}")
    st.dataframe(show, use_container_width=True, hide_index=True, height=600)

elif page == 'リピート分析':
    st.markdown("## 🔁 リピート分析")
    st.info("リピート分析には購入者IDが必要です。現在は店舗別月次推移を表示しています。")
    monthly = df_cur.groupby(['month','receive_order_shop_id'])['receive_order_total_amount'].sum().reset_index()
    monthly.columns = ['月','店舗ID','売上']
    fig = px.line(monthly, x='月', y='売上', color='店舗ID', color_discrete_sequence=COLORS, markers=True)
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', height=350, margin=dict(t=10,b=0))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

elif page == '在庫アラート':
    st.markdown("## ⚠️ 在庫アラート")
    threshold = st.slider("アラート閾値（個以下）", 1, 100, 10)
    with st.spinner('在庫データ確認中...'):
        alerts = get_stock(st.session_state.access_token, threshold)
    if alerts:
        st.error(f"⚠️ {len(alerts)}件の商品が在庫{threshold}個以下です")
        alert_df = pd.DataFrame(alerts)[['goods_id','goods_name','stock_free_quantity']]
        alert_df.columns = ['商品ID','商品名','フリー在庫数']
        st.dataframe(alert_df, use_container_width=True, hide_index=True)
    else:
        st.success(f"✅ 在庫{threshold}個以下の商品はありません")
