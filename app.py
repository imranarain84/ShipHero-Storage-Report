import streamlit as st
import pandas as pd
import requests

# 1. Access the API Key from Streamlit's Cloud Settings
# You will set this up in the Streamlit Cloud dashboard in the next step
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"
token = st.secrets["SHIPHERO_TOKEN"]
HEADERS = {"Authorization": f"Bearer {token}"}

# 2. Daily Rate Card (Mapped from your PDF)
# These rates aggregate to Ryan's $0.65/cuft target over 30 days
STORAGE_RATES = {
    "Standard Bin": 0.0442,
    "Blue Bin Small": 0.0488,
    "Blue Bin Medium": 0.1462,
    "Blue Bin Large": 0.2925,
    "Gray Bin Small": 0.1846,
    "Gray Bin Medium": 0.2275,
    "Gray Bin Large": 0.325,
    "Pallet": 2.093,
    "Pallet Large": 2.652,
    "Pallet Small": 0.5902,
    "Half Pallet": 1.0472,
    "Tractor Trailer Load Floor": 52.00,
    "Wall - Back": 12.116,
    "Wall - Front": 4.4096
}

st.title("📦 Backmarket Storage Report")

# 3. ShipHero API Call
def fetch_data():
    query = """
    query {
      products(tags: ["backmarket"]) {
        data(first: 100) {
          edges {
            node {
              sku
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
    try:
        r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS)
        return r.json()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# 4. Processing & Display
raw_data = fetch_data()

if raw_data and 'data' in raw_data:
    rows = []
    for edge in raw_data['data']['products']['data']['edges']:
        node = edge['node']
        for wh_prod in node['warehouse_products']:
            for loc_edge in wh_prod['locations']['edges']:
                loc_name = loc_edge['node']['location']['name']
                qty = loc_edge['node']['quantity']
                
                # Match location to rate card [cite: 5, 10, 24, 64]
                daily_rate = next((rate for key, rate in STORAGE_RATES.items() if key in loc_name), 0.0)
                
                rows.append({
                    "SKU": node['sku'],
                    "Location": loc_name,
                    "Quantity": qty,
                    "Daily Cost": f"${daily_rate:.4f}",
                    "Est. Monthly": round(daily_rate * 30, 2)
                })

    df = pd.DataFrame(rows)
    st.metric("Total Monthly Storage (Est.)", f"${df['Est. Monthly'].sum():,.2f}")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("No data found or API key is invalid.")
