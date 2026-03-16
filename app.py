import streamlit as st
import pandas as pd
import requests

# --- 1. CONFIGURATION & SECRETS ---
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"

if "SHIPHERO_TOKEN" not in st.secrets:
    st.error("❌ 'SHIPHERO_TOKEN' not found in Streamlit Secrets. Please check your dashboard settings.")
    st.stop()

token = st.secrets["SHIPHERO_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# --- 2. STORAGE RATE CARD (Extracted from Billing Profile) ---
# [cite: 5, 10, 15, 20, 24, 29, 34, 39, 44, 48, 54, 59, 64, 69, 73, 79, 84, 89, 94, 98, 104, 109]
STORAGE_RATES = {
    "Standard Bin": 0.0442,      # [cite: 10, 15]
    "Blue Bin Small": 0.0488,    # [cite: 39]
    "Blue Bin Medium": 0.1462,   # [cite: 34]
    "Blue Bin Large": 0.2925,    # [cite: 29]
    "Gray Bin Small": 0.1846,    # [cite: 44]
    "Gray Bin Medium": 0.2275,   # [cite: 48]
    "Gray Bin Large": 0.325,     # [cite: 54]
    "Pallet": 2.093,             # [cite: 5]
    "Pallet Tall": 2.7274,       # [cite: 59]
    "Pallet Large": 2.652,       # [cite: 64]
    "Pallet Medium Large": 1.7914, # [cite: 69]
    "Pallet Medium Small": 1.443,  # [cite: 73]
    "Pallet Small Large": 0.9581,  # [cite: 79]
    "Pallet Small": 0.5902,      # [cite: 84]
    "Half Pallet": 1.0472,       # [cite: 20]
    "Tractor Trailer Load Floor": 52.00, # [cite: 24]
    "Wall - Back": 12.116,       # [cite: 89]
    "Wall - Front": 4.4096,      # [cite: 99]
    "Pallite 16": 0.0537,        #
    "Pallite 48": 0.0357,        #
    "DT - Pallet": 2.2074        # [cite: 104, 109]
}

# --- 3. API DATA FETCHING ---
@st.cache_data(ttl=300)
def fetch_shiphero_data():
    query = """
    query {
      products(first: 100) {
        data {
          edges {
            node {
              sku
              name
              tags
              warehouse_products {
                warehouse_id
                locations(first: 20) {
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
        if r.status_code != 200:
            st.error(f"HTTP Error {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

# --- 4. APP INTERFACE ---
st.set_page_config(page_title="Storage Report", layout="wide")
st.title("📦 Storage Cost Report")

raw_json = fetch_shiphero_data()

# Defensive check: Ensure raw_json and 'data' exist
if raw_json and 'data' in raw_json and raw_json['data'] and 'products' in raw_json['data']:
    
    # Safely navigate the nested dictionary
    product_connection = raw_json['data']['products']
    if product_connection and 'data' in product_connection:
        all_products = product_connection['data'].get('edges', [])
    else:
        all_products = []
    
    if not all_products:
        st.warning("No products returned from the API.")
        st.stop()

    # Extract unique tags
    unique_tags = set()
    for edge in all_products:
        node = edge.get('node', {})
        for tag in node.get('tags', []):
            if tag: unique_tags.add(tag)
    
    sorted_tags = sorted(list(unique_tags))
    
    # Sidebar Selection
    st.sidebar.header("Filters")
    selected_tag = st.sidebar.selectbox("Filter by Product Tag", ["Select a Tag"] + sorted_tags)

    if selected_tag != "Select a Tag":
        report_data = []
        for edge in all_products:
            node = edge.get('node', {})
            tags = node.get('tags', [])
            
            if selected_tag in tags:
                for wh_prod in node.get('warehouse_products', []):
                    # Ensure locations exist
                    loc_connection = wh_prod.get('locations', {})
                    if loc_connection and 'edges' in loc_connection:
                        for loc_edge in loc_connection['edges']:
                            loc_node = loc_edge.get('node', {})
                            loc_name = loc_node.get('location', {}).get('name', 'Unknown')
                            qty = loc_node.get('quantity', 0)
                            
                            # Match Rate
                            daily_rate = 0.0
                            for key, rate in STORAGE_RATES.items():
                                if key.lower() in loc_name.lower():
                                    daily_rate = rate
                                    break
                            
                            report_data.append({
                                "SKU": node.get('sku'),
                                "Location": loc_name,
                                "Quantity": qty,
                                "Daily Cost": daily_rate,
                                "Monthly Est.": round(daily_rate * 30, 2)
                            })

        if report_data:
            df = pd.DataFrame(report_data)
            st.metric(f"Total Monthly Cost for {selected_tag}", f"${df['Monthly Est.'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)
        else:
            st.info(f"No inventory found for products tagged '{selected_tag}'.")
    else:
        st.info("Please select a tag in the sidebar to generate the report.")

else:
    st.error("The API returned an unexpected format. Please check the 'Manage App' logs in Streamlit.")
    if raw_json and 'errors' in raw_json:
        st.json(raw_json['errors'])
