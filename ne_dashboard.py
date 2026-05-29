import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
import json

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

def get_all_orders():
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

def get_stock_alert(threshold=10):
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

with st.spinner('データを取得中...'):
    orders = get_all_orders()

if not orders:
    st.warning("受注データがありません。")
    st.stop()

df = pd.DataFrame(orders)
df['receive_order_date']         = pd.to_datetime(df['receive_order_date'])
df['receive_order_total_amount'] = pd.t
