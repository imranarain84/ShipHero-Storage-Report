import streamlit as st
import pandas as pd
import requests
from rates import STORAGE_RATES

# ShipHero API Configuration (Uses Streamlit Secrets)
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"
HEADERS = {"Authorization": f"Bearer {st.secrets['SHIPHERO_TOKEN']}"}

def fetch_backmarket_inventory():
    query = """
    query {
      products(tags: ["backmarket"]) {
        data(first: 100) {
          edges {
            node {
              sku
              name
              warehouse_products {
                locations(first: 50) {
                  edges {
                    node {
                      quantity
                      location { name }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    response = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS)
    return response.json()

st.set_page_config(page_title="Backmarket Storage Report", layout="wide")
st.title("📦 Storage Cost Report: 'backmarket'")

# Logic to process and match locations to rates
data = fetch_backmarket_inventory()
rows = []

for edge in data['data']['products']['data']['edges']:
    node = edge['node']
    for wh_prod in node['warehouse_products']:
        for loc_edge in wh_prod['locations']['edges']:
            loc_name = loc_edge['node']['location']['name']
            qty = loc_edge['node']['quantity']
            
            # Find the best match in our rate card
            daily_rate = next((rate for key, rate in STORAGE_RATES.items() if key in loc_name), 0.0)
            
            rows.append({
                "SKU": node['sku'],
                "Location": loc_name,
                "Qty": qty,
                "Daily Cost": daily_rate,
                "Monthly (30 Day)": round(daily_rate * 30, 2)
            })

df = pd.DataFrame(rows)

# Dashboard Display
m1, m2 = st.columns(2)
total_monthly = df["Monthly (30 Day)"].sum()
m1.metric("Total Monthly Estimate", f"${total_monthly:,.2/f}")
m2.metric("Target (Ryan's Calc)", "$0.65/cuft Avg")

st.dataframe(df, use_container_width=True)
