import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="売上ダッシュボード", page_icon="📊", layout="wide")

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
    offset = 0
    limit  = 100
    while True:
        result = ne_request('api_v1_receiveorder_base/search', {
            'limit':  str(limit),
            'offset': str(offset),
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
        'limit':  '100',
        'offset': '0',
        'fields': 'stock_id,goods_id,goods_name,stock_quantity,stock_free_quantity',
    })
    if result.get('result') != 'success':
        return []
    stocks = result.get('data', [])
    alerts = []
    for s in stocks:
        qty = s.get('stock_free_quantity') or s.get('stock_quantity') or 0
        try:
            if float(qty) <= threshold:
                alerts.append(s)
        except Exception:
            pass
    return alerts

# データ取得
with st.spinner('データを取得中...'):
    orders = get_all_orders(_dummy=st.session_state.access_token)

if not orders:
    st.warning("受注データがありません。")
    st.stop()

df = pd.DataFrame(orders)
df['receive_order_date']         = pd.to_datetime(df['receive_order_date'])
df['receive_order_total_amount'] = pd.to_numeric(df['receive_order_total_amount'], errors='coerce').fillna(0)
df['date']    = df['receive_order_date'].dt.strftime('%Y-%m-%d')
df['month']   = df['receive_order_date'].dt.strftime('%Y-%m')
df['weekday'] = df['receive_order_date'].dt.weekday  # 0=月, 6=日
df['hour']    = df['receive_order_date'].dt.hour

WEEKDAY_NAMES = {0:'月', 1:'火', 2:'水', 3:'木', 4:'金', 5:'土', 6:'日'}
df['weekday_name'] = df['weekday'].map(WEEKDAY_NAMES)

# ヘッダー
st.title("📊 売上ダッシュボード")
col_title, col_btn = st.columns([6, 1])
with col_title:
    st.caption(f"最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
with col_btn:
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# サマリーカード
today      = datetime.now().strftime('%Y-%m-%d')
this_month = datetime.now().strftime('%Y-%m')
today_df   = df[df['date']  == today]
month_df   = df[df['month'] == this_month]

col1, col2, col3, col4 = st.columns(4)
col1.metric("今日の売上",   f"¥{int(today_df['receive_order_total_amount'].sum()):,}")
col2.metric("今日の受注数", f"{len(today_df)}件")
col3.metric("今月の売上",   f"¥{int(month_df['receive_order_total_amount'].sum()):,}")
col4.metric("今月の受注数", f"{len(month_df)}件")

st.divider()

# グラフタブ
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📅 日別売上", "📆 月別売上", "🏪 店舗別分析", "📅 曜日別分析", "🕐 時間帯別分析"
])

with tab1:
    daily = df.groupby('date').agg(
        売上合計=('receive_order_total_amount', 'sum'),
        受注件数=('receive_order_id', 'count')
    ).reset_index().sort_values('date')
    fig = px.bar(daily, x='date', y='売上合計',
                 title='日別売上', labels={'date': '日付', '売上合計': '売上(円)'},
                 color_discrete_sequence=['#1a5c38'], text='受注件数')
    fig.update_xaxes(type='category')
    fig.update_traces(texttemplate='%{text}件', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    monthly = df.groupby('month').agg(
        売上合計=('receive_order_total_amount', 'sum'),
        受注件数=('receive_order_id', 'count')
    ).reset_index().sort_values('month')
    fig2 = px.bar(monthly, x='month', y='売上合計',
                  title='月別売上', labels={'month': '月', '売上合計': '売上(円)'},
                  color_discrete_sequence=['#2d8a5c'], text='受注件数')
    fig2.update_xaxes(type='category')
    fig2.update_traces(texttemplate='%{text}件', textposition='outside')
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    shop = df.groupby('receive_order_shop_id').agg(
        売上合計=('receive_order_total_amount', 'sum'),
        受注件数=('receive_order_id', 'count')
    ).reset_index().sort_values('売上合計', ascending=False)
    shop.columns = ['店舗ID', '売上合計', '受注件数']

    col_a, col_b = st.columns(2)
    with col_a:
        fig3 = px.bar(shop, x='店舗ID', y='売上合計',
                      title='店舗別売上', color_discrete_sequence=['#1a5c38'],
                      text='受注件数')
        fig3.update_xaxes(type='category')
        fig3.update_traces(texttemplate='%{text}件', textposition='outside')
        st.plotly_chart(fig3, use_container_width=True)
    with col_b:
        fig4 = px.pie(shop, names='店舗ID', values='売上合計',
                      title='店舗別売上構成比',
                      color_discrete_sequence=px.colors.sequential.Greens_r)
        st.plotly_chart(fig4, use_container_width=True)

    st.dataframe(shop, use_container_width=True, hide_index=True)

with tab4:
    weekday_order = ['月', '火', '水', '木', '金', '土', '日']
    wday = df.groupby('weekday_name').agg(
        売上合計=('receive_order_total_amount', 'sum'),
        受注件数=('receive_order_id', 'count')
    ).reset_index()
    wday['weekday_name'] = pd.Categorical(wday['weekday_name'], categories=weekday_order, ordered=True)
    wday = wday.sort_values('weekday_name')

    col_a, col_b = st.columns(2)
    with col_a:
        fig5 = px.bar(wday, x='weekday_name', y='売上合計',
                      title='曜日別売上', labels={'weekday_name': '曜日', '売上合計': '売上(円)'},
                      color_discrete_sequence=['#1a5c38'], text='受注件数')
        fig5.update_traces(texttemplate='%{text}件', textposition='outside')
        st.plotly_chart(fig5, use_container_width=True)
    with col_b:
        fig6 = px.bar(wday, x='weekday_name', y='受注件数',
                      title='曜日別受注件数', labels={'weekday_name': '曜日', '受注件数': '件数'},
                      color_discrete_sequence=['#2d8a5c'])
        st.plotly_chart(fig6, use_container_width=True)

with tab5:
    hour_df = df.groupby('hour').agg(
        売上合計=('receive_order_total_amount', 'sum'),
        受注件数=('receive_order_id', 'count')
    ).reset_index().sort_values('hour')
    hour_df['hour_label'] = hour_df['hour'].apply(lambda x: f"{x:02d}時")

    col_a, col_b = st.columns(2)
    with col_a:
        fig7 = px.bar(hour_df, x='hour_label', y='売上合計',
                      title='時間帯別売上', labels={'hour_label': '時間帯', '売上合計': '売上(円)'},
                      color_discrete_sequence=['#1a5c38'])
        fig7.update_xaxes(type='category')
        st.plotly_chart(fig7, use_container_width=True)
    with col_b:
        fig8 = px.bar(hour_df, x='hour_label', y='受注件数',
                      title='時間帯別受注件数', labels={'hour_label': '時間帯', '受注件数': '件数'},
                      color_discrete_sequence=['#2d8a5c'])
        fig8.update_xaxes(type='category')
        st.plotly_chart(fig8, use_container_width=True)

st.divider()

# 受注一覧
st.subheader("📋 受注一覧")
show_df = df[['receive_order_id', 'date', 'receive_order_shop_id',
              'receive_order_total_amount', 'receive_order_order_status_name']].copy()
show_df.columns = ['受注ID', '注文日', '店舗ID', '合計金額(円)', 'ステータス']
show_df['合計金額(円)'] = show_df['合計金額(円)'].apply(lambda x: f"¥{int(x):,}")
st.dataframe(show_df, use_container_width=True, hide_index=True)

st.divider()

# 在庫アラート
st.subheader("⚠️ 在庫アラート（在庫10個以下）")
with st.spinner('在庫データ確認中...'):
    alerts = get_stock_alert(_dummy=st.session_state.access_token, threshold=10)

if alerts:
    alert_df = pd.DataFrame(alerts)[['goods_id', 'goods_name', 'stock_free_quantity']]
    alert_df.columns = ['商品ID', '商品名', 'フリー在庫数']
    st.dataframe(alert_df, use_container_width=True, hide_index=True)
else:
    st.success("在庫アラート対象商品はありません ✅")
