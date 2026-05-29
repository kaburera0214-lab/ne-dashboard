import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
import json

st.set_page_config(page_title="売上ダッシュボード", page_icon="📊", layout="wide")

# =====================
# 認証情報の読み込み
# =====================
if 'access_token' not in st.session_state:
    try:
        st.session_state.access_token  = st.secrets['nextengine']['access_token']
        st.session_state.refresh_token = st.secrets['nextengine']['refresh_token']
        st.session_state.client_id     = st.secrets['nextengine']['client_id']
        st.session_state.client_secret = st.secrets['nextengine']['client_secret']
    except Exception:
        st.error("⚠️ 認証情報が設定されていません。Streamlit SecretsにNextEngine認証情報を設定してください。")
        st.stop()

# =====================
# API呼び出し共通関数
# =====================
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
    # トークン更新
    if 'access_token' in result:
        st.session_state.access_token  = result['access_token']
        st.session_state.refresh_token = result['refresh_token']
    return result

def get_all_orders():
    """全受注データを取得（ページネーション対応）"""
    all_orders = []
    offset = 0
    limit  = 100
    while True:
        result = ne_request('api_v1_receiveorder_base/search', {
            'limit':  str(limit),
            'offset': str(offset),
            'fields': (
                'receive_order_id,'
                'receive_order_shop_id,'
                'receive_order_date,'
                'receive_order_total_amount,'
                'receive_order_order_status_name'
            ),
        })
        if result.get('result') != 'success':
            break
        data = result.get('data', [])
        all_orders.extend(data)
        if len(data) < limit:
            break
        offset += limit
    return all_orders

def get_stock_alert(threshold=10):
    """在庫アラート対象商品を取得"""
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

# =====================
# データ取得
# =====================
with st.spinner('データを取得中...'):
    orders = get_all_orders()

if not orders:
    st.warning("受注データがありません。")
    st.stop()

df = pd.DataFrame(orders)
df['receive_order_date']         = pd.to_datetime(df['receive_order_date'])
df['receive_order_total_amount'] = pd.to_numeric(df['receive_order_total_amount'], errors='coerce').fillna(0)
df['date']  = df['receive_order_date'].dt.date
df['month'] = df['receive_order_date'].dt.to_period('M').astype(str)

# =====================
# ヘッダー
# =====================
st.title("📊 売上ダッシュボード")
st.caption(f"最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.divider()

# =====================
# サマリーカード
# =====================
today       = datetime.now().date()
this_month  = datetime.now().strftime('%Y-%m')

today_df  = df[df['date'] == today]
month_df  = df[df['month'] == this_month]

col1, col2, col3, col4 = st.columns(4)
col1.metric("今日の売上",   f"¥{int(today_df['receive_order_total_amount'].sum()):,}")
col2.metric("今日の受注数", f"{len(today_df)}件")
col3.metric("今月の売上",   f"¥{int(month_df['receive_order_total_amount'].sum()):,}")
col4.metric("今月の受注数", f"{len(month_df)}件")

st.divider()

# =====================
# グラフセクション
# =====================
tab1, tab2 = st.tabs(["📅 日別売上", "📆 月別売上"])

with tab1:
    daily = df.groupby('date').agg(
        売上合計=('receive_order_total_amount', 'sum'),
        受注件数=('receive_order_id', 'count')
    ).reset_index()
    daily['date'] = daily['date'].astype(str)

    fig = px.bar(daily, x='date', y='売上合計',
                 title='日別売上',
                 labels={'date': '日付', '売上合計': '売上(円)'},
                 color_discrete_sequence=['#1a5c38'])
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    monthly = df.groupby('month').agg(
        売上合計=('receive_order_total_amount', 'sum'),
        受注件数=('receive_order_id', 'count')
    ).reset_index()

    fig2 = px.bar(monthly, x='month', y='売上合計',
                  title='月別売上',
                  labels={'month': '月', '売上合計': '売上(円)'},
                  color_discrete_sequence=['#2d8a5c'])
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# =====================
# 受注一覧表
# =====================
st.subheader("📋 受注一覧")

show_df = df[['receive_order_id', 'receive_order_date', 'receive_order_shop_id',
              'receive_order_total_amount', 'receive_order_order_status_name']].copy()
show_df.columns = ['受注ID', '注文日', 'ショップID', '合計金額(円)', 'ステータス']
show_df['注文日'] = show_df['注文日'].dt.strftime('%Y-%m-%d')
show_df['合計金額(円)'] = show_df['合計金額(円)'].apply(lambda x: f"¥{int(x):,}")

st.dataframe(show_df, use_container_width=True, hide_index=True)

st.divider()

# =====================
# 在庫アラート
# =====================
st.subheader("⚠️ 在庫アラート（在庫10個以下）")

with st.spinner('在庫データ確認中...'):
    alerts = get_stock_alert(threshold=10)

if alerts:
    alert_df = pd.DataFrame(alerts)[['goods_id', 'goods_name', 'stock_free_quantity']]
    alert_df.columns = ['商品ID', '商品名', 'フリー在庫数']
    st.dataframe(alert_df, use_container_width=True, hide_index=True)
else:
    st.success("在庫アラート対象商品はありません ✅")
