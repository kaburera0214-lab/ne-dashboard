import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(
    page_title="売上ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================
# カスタムCSS
# =====================
st.markdown("""
<style>
/* 全体背景 */
.stApp { background-color: #f0f4f8; }

/* サイドバー */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a3a5c 0%, #0d2137 100%);
}
section[data-testid="stSidebar"] * { color: white !important; }
section[data-testid="stSidebar"] .stSelectbox label { color: #aac4e0 !important; }

/* メインエリア */
.main .block-container { padding-top: 1.5rem; }

/* KPIカード */
.kpi-card {
    background: white;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    border-left: 4px solid #1a6bc8;
    margin-bottom: 8px;
}
.kpi-label {
    font-size: 13px;
    color: #6b7280;
    font-weight: 500;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 28px;
    font-weight: 700;
    color: #1a3a5c;
    line-height: 1;
}
.kpi-card.green  { border-left-color: #16a34a; }
.kpi-card.orange { border-left-color: #ea580c; }
.kpi-card.purple { border-left-color: #7c3aed; }

/* セクションヘッダー */
.section-header {
    background: white;
    border-radius: 10px;
    padding: 12px 20px;
    margin-bottom: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    font-size: 16px;
    font-weight: 700;
    color: #1a3a5c;
    border-left: 4px solid #1a6bc8;
}

/* グラフカード */
.chart-card {
    background: white;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

/* テーブル */
.stDataFrame { border-radius: 10px; overflow: hidden; }

/* タブ */
.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background: #1a6bc8 !important;
    color: white !important;
}

/* ボタン */
.stButton > button {
    background: #1a6bc8;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
}
.stButton > button:hover { background: #1558a8; }
</style>
""", unsafe_allow_html=True)

# =====================
# 認証情報
# =====================
if 'access_token' not in st.session_state:
    try:
        st.session_state.access_token  = st.secrets['nextengine']['access_token']
        st.session_state.refresh_token = st.secrets['nextengine']['refresh_token']
        st.session_state.client_id     = st.secrets['nextengine']['client_id']
        st.session_state.client_secret = st.secrets['nextengine']['client_secret']
    except Exception:
        st.error("⚠️ 認証情報が設定されていません。")
        st.stop()

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
def get_all_orders(_dummy=None):
    all_orders = []
    offset, limit = 0, 100
    while True:
        result = ne_request('api_v1_receiveorder_base/search', {
            'limit': str(limit), 'offset': str(offset),
            'fields': 'receive_order_id,receive_order_shop_id,receive_order_date,receive_order_total_amount,receive_order_order_status_name',
        })
        if result.get('result') != 'success':
            break
        data = result.get('data', [])
        all_orders.extend(data)
        if len(data) < limit:
            break
        offset += limit
    return all_orders

@st.cache_data(ttl=300)
def get_stock_alert(_dummy=None, threshold=10):
    result = ne_request('api_v1_master_stock/search', {
        'limit': '100', 'offset': '0',
        'fields': 'stock_id,goods_id,goods_name,stock_quantity,stock_free_quantity',
    })
    if result.get('result') != 'success':
        return []
    alerts = []
    for s in result.get('data', []):
        qty = s.get('stock_free_quantity') or s.get('stock_quantity') or 0
        try:
            if float(qty) <= threshold:
                alerts.append(s)
        except Exception:
            pass
    return alerts

# =====================
# サイドバー
# =====================
with st.sidebar:
    st.markdown("## 📊 売上ダッシュボード")
    st.markdown("---")
    page = st.selectbox("📂 分析メニュー", [
        "🏠 全体サマリー",
        "🏪 店舗別分析",
        "📅 曜日別分析",
        "🕐 時間帯別分析",
        "📋 受注一覧",
        "⚠️ 在庫アラート",
    ])
    st.markdown("---")
    if st.button("🔄 データ更新"):
        st.cache_data.clear()
        st.rerun()
    st.markdown(f"<small>最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}</small>", unsafe_allow_html=True)

# =====================
# データ取得
# =====================
with st.spinner('データを取得中...'):
    orders = get_all_orders(_dummy=st.session_state.access_token)

if not orders:
    st.warning("受注データがありません。")
    st.stop()

df = pd.DataFrame(orders)
df['receive_order_date']         = pd.to_datetime(df['receive_order_date'])
df['receive_order_total_amount'] = pd.to_numeric(df['receive_order_total_amount'], errors='coerce').fillna(0)
df['date']         = df['receive_order_date'].dt.strftime('%Y-%m-%d')
df['month']        = df['receive_order_date'].dt.strftime('%Y-%m')
df['weekday']      = df['receive_order_date'].dt.weekday
df['weekday_name'] = df['weekday'].map({0:'月',1:'火',2:'水',3:'木',4:'金',5:'土',6:'日'})
df['hour']         = df['receive_order_date'].dt.hour

today      = datetime.now().strftime('%Y-%m-%d')
this_month = datetime.now().strftime('%Y-%m')
today_df   = df[df['date']  == today]
month_df   = df[df['month'] == this_month]

COLORS = ['#1a6bc8','#16a34a','#ea580c','#7c3aed','#0891b2','#be185d']

def kpi(label, value, color=''):
    st.markdown(f"""
    <div class="kpi-card {color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
    </div>""", unsafe_allow_html=True)

def section(title):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

# =====================
# ページ描画
# =====================
if page == "🏠 全体サマリー":
    st.markdown("# 🏠 全体サマリー")
    section("📌 今日の状況")
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("今日の売上", f"¥{int(today_df['receive_order_total_amount'].sum()):,}")
    with c2: kpi("今日の受注数", f"{len(today_df)}件", "green")
    with c3: kpi("今月の売上", f"¥{int(month_df['receive_order_total_amount'].sum()):,}", "orange")
    with c4: kpi("今月の受注数", f"{len(month_df)}件", "purple")

    st.markdown("<br>", unsafe_allow_html=True)
    section("📈 売上推移")
    tab1, tab2 = st.tabs(["日別", "月別"])
    with tab1:
        daily = df.groupby('date').agg(売上合計=('receive_order_total_amount','sum'), 受注件数=('receive_order_id','count')).reset_index().sort_values('date')
        fig = px.bar(daily, x='date', y='売上合計', text='受注件数', color_discrete_sequence=[COLORS[0]])
        fig.update_xaxes(type='category')
        fig.update_traces(texttemplate='%{text}件', textposition='outside')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', margin=dict(t=30,b=0))
        st.plotly_chart(fig, use_container_width=True)
    with tab2:
        monthly = df.groupby('month').agg(売上合計=('receive_order_total_amount','sum'), 受注件数=('receive_order_id','count')).reset_index().sort_values('month')
        fig2 = px.bar(monthly, x='month', y='売上合計', text='受注件数', color_discrete_sequence=[COLORS[1]])
        fig2.update_xaxes(type='category')
        fig2.update_traces(texttemplate='%{text}件', textposition='outside')
        fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', margin=dict(t=30,b=0))
        st.plotly_chart(fig2, use_container_width=True)

elif page == "🏪 店舗別分析":
    st.markdown("# 🏪 店舗別分析")
    shop = df.groupby('receive_order_shop_id').agg(
        売上合計=('receive_order_total_amount','sum'),
        受注件数=('receive_order_id','count')
    ).reset_index().sort_values('売上合計', ascending=False)
    shop.columns = ['店舗ID','売上合計','受注件数']

    section("📊 店舗別売上")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(shop, x='店舗ID', y='売上合計', text='受注件数', color_discrete_sequence=COLORS)
        fig.update_xaxes(type='category')
        fig.update_traces(texttemplate='%{text}件', textposition='outside')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.pie(shop, names='店舗ID', values='売上合計', title='売上構成比', color_discrete_sequence=COLORS, hole=0.4)
        fig2.update_layout(paper_bgcolor='white')
        st.plotly_chart(fig2, use_container_width=True)

    section("📋 店舗別集計表")
    shop['売上合計'] = shop['売上合計'].apply(lambda x: f"¥{int(x):,}")
    st.dataframe(shop, use_container_width=True, hide_index=True)

elif page == "📅 曜日別分析":
    st.markdown("# 📅 曜日別分析")
    weekday_order = ['月','火','水','木','金','土','日']
    wday = df.groupby('weekday_name').agg(
        売上合計=('receive_order_total_amount','sum'),
        受注件数=('receive_order_id','count')
    ).reset_index()
    wday['weekday_name'] = pd.Categorical(wday['weekday_name'], categories=weekday_order, ordered=True)
    wday = wday.sort_values('weekday_name')

    section("📊 曜日別売上・受注件数")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(wday, x='weekday_name', y='売上合計', text='売上合計',
                     color_discrete_sequence=[COLORS[0]], labels={'weekday_name':'曜日'})
        fig.update_traces(texttemplate='¥%{text:,.0f}', textposition='outside')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.bar(wday, x='weekday_name', y='受注件数',
                      color_discrete_sequence=[COLORS[1]], labels={'weekday_name':'曜日'})
        fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig2, use_container_width=True)

elif page == "🕐 時間帯別分析":
    st.markdown("# 🕐 時間帯別分析")
    hour_df = df.groupby('hour').agg(
        売上合計=('receive_order_total_amount','sum'),
        受注件数=('receive_order_id','count')
    ).reset_index().sort_values('hour')
    hour_df['hour_label'] = hour_df['hour'].apply(lambda x: f"{x:02d}時")

    section("📊 時間帯別売上・受注件数")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(hour_df, x='hour_label', y='売上合計',
                     color_discrete_sequence=[COLORS[0]], labels={'hour_label':'時間帯'})
        fig.update_xaxes(type='category')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.bar(hour_df, x='hour_label', y='受注件数',
                      color_discrete_sequence=[COLORS[2]], labels={'hour_label':'時間帯'})
        fig2.update_xaxes(type='category')
        fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig2, use_container_width=True)

elif page == "📋 受注一覧":
    st.markdown("# 📋 受注一覧")
    section(f"全 {len(df)} 件")
    show_df = df[['receive_order_id','date','receive_order_shop_id','receive_order_total_amount','receive_order_order_status_name']].copy()
    show_df.columns = ['受注ID','注文日','店舗ID','合計金額(円)','ステータス']
    show_df['合計金額(円)'] = show_df['合計金額(円)'].apply(lambda x: f"¥{int(x):,}")
    st.dataframe(show_df, use_container_width=True, hide_index=True, height=600)

elif page == "⚠️ 在庫アラート":
    st.markdown("# ⚠️ 在庫アラート")
    threshold = st.slider("アラート閾値（個以下）", 1, 50, 10)
    with st.spinner('在庫データ確認中...'):
        alerts = get_stock_alert(_dummy=st.session_state.access_token, threshold=threshold)
    if alerts:
        section(f"⚠️ {len(alerts)}件の商品が在庫{threshold}個以下です")
        alert_df = pd.DataFrame(alerts)[['goods_id','goods_name','stock_free_quantity']]
        alert_df.columns = ['商品ID','商品名','フリー在庫数']
        st.dataframe(alert_df, use_container_width=True, hide_index=True)
    else:
        st.success(f"✅ 在庫{threshold}個以下の商品はありません")
