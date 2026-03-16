import streamlit as st
import pandas as pd
import requests

# --- 1. CONFIGURATION & SECRETS ---
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"

if "SHIPHERO_TOKEN" not in st.secrets:
    st.error("❌ 'SHIPHERO_TOKEN' not found in Streamlit Secrets.")
    st.stop()

token = st.secrets["SHIPHERO_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# --- 2. STORAGE RATE CARD (From your Billing Profile PDF) ---
STORAGE_TYPES = {
    "Standard Bin": 0.0442,
    "Bin": 0.0442,
    "Blue Bin Small": 0.0488,
    "Blue Bin Medium": 0.1462,
    "Blue Bin Large": 0.2925,
    "Gray Bin Small": 0.1846,
    "Gray Bin Medium": 0.2275,
    "Gray Bin Large": 0.325,
    "Pallet": 2.093,
    "Pallet Tall": 2.7274,
    "Pallet TALL": 2.7274,
    "Pallet Large": 2.652,
    "Pallet Medium Large": 1.7914,
    "Pallet Medium Small": 1.443,
    "Pallet Small Large": 0.9581,
    "Pallet Small": 0.5902,
    "Half Pallet": 1.0472,
    "Tractor Trailer Load Floor Storage": 52.00,
    "Wall - Back": 12.116,
    "Wall - Front": 4.4096,
    "Pallite_16": 0.0537,
    "Pallite - 48": 0.0357,
    "Pallite_48": 0.0357,
    "Palite_48": 0.0357,
    "Jumbo Receiving Pallet": 3.90,
    "HD": 2.275,
    "DT - Pallet": 2.2074
}

# --- 3. LOAD YOUR UPLOADED FILENAME ---
@st.cache_data
def get_location_lookup():
    try:
        # Matches your exact GitHub filename
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'], df['Type']))
    except FileNotFoundError:
        st.error("❌ The file 'ShipHero - Location Names and Info.csv' was not found on GitHub.")
        return {}

location_map = get_location_lookup()

# --- 4. API DATA FETCHING ---
@st.cache_data(ttl=300)
def fetch_shiphero_data():
    query = """
    query {
      products {
        data(first: 100) {
          edges {
            node {
              sku
              name
              tags
              warehouse_products {
                locations(first: 25) {
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
        return r.json() if r.status_code == 200 else None
    except:
        return None

# --- 5. APP INTERFACE ---
st.set_page_config(page_title="Storage Cost Report", layout="wide")
st.title("📦 Storage Cost Report")

data_response = fetch_shiphero_data()

if data_response and 'data' in data_response:
    product_edges = data_response.get('data', {}).get('products', {}).get('data', {}).get('edges', [])
    
    if not product_edges:
        st.warning("No products found in the account.")
        st.stop()

    # 1. Gather Tags for the Dropdown
    available_tags = sorted(list({t for e in product_edges for t in e['node'].get('tags', []) if t}))
    selected_tag = st.sidebar.selectbox("Filter by Product Tag", ["Show All"] + available_tags)

    # 2. Process and Filter Data
    report_list = []
    for edge in product_edges:
        node = edge['node']
        node_tags = node.get('tags', [])
        
        if selected_tag == "Show All" or selected_tag in node_tags:
            for wh_prod in node.get('warehouse_products', []):
                for loc_edge in wh_prod.get('locations', {}).get('edges', []):
                    l_name = loc_edge['node']['location']['name']
                    l_qty = loc_edge['node']['quantity']
                    
                    # Look up Type from CSV, then Rate from STORAGE_TYPES
                    l_type = location_map.get(l_name, "Unknown")
                    daily_fee = STORAGE_TYPES.get(l_type, 0.0)

                    report_list.append({
                        "SKU": node.get('sku'),
                        "Location": l_name,
