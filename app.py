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

# --- 2. STORAGE RATE CARD (From Billing Profile PDF) ---
# Extracted from your provided billing documentation [cite: 5, 10, 20, 24, 29, 34, 39, 43, 48, 54, 59, 64, 69, 73, 79, 84, 89, 94, 98, 104, 109]
STORAGE_RATES = {
    "Standard Bin": 0.0442,      # [cite: 10]
    "Blue Bin Small": 0.0488,    # [cite: 39]
    "Blue Bin Medium": 0.1462,   # [cite: 34]
    "Blue Bin Large": 0.2925,    # [cite: 29]
    "Gray Bin Small": 0.1846,    # [cite: 43]
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
    "DT - Pallet": 2.2074        # 
}

# --- 3. API DATA FETCHING ---
@st.cache_data(ttl=600) # Caches data for 10 minutes to stay within API limits
def fetch_shiphero_data():
    query = """
    query {
      products {
        data(first: 250) {
          edges {
            node {
              sku
              name
              tags
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
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# --- 4. APP INTERFACE ---
st.set_page_config(page_title="Storage Cost Report", layout="wide")
st.title("📦 Dynamic Storage Cost Report")

raw_data = fetch_shiphero_data()

if raw_data and 'data' in raw_data:
    all_products = raw_data['data']['products']['data']['edges']
    
    # Extract unique tags for the dropdown
    unique_tags = set()
    for edge in all_products:
        for tag in edge['node'].get('tags', []):
            if tag: unique_tags.add(tag)
    
    sorted_tags = sorted(list(unique_tags))
    
    # Dropdown Menu in Sidebar
    st.sidebar.header("Filter Settings")
    selected_tag = st.sidebar.selectbox("Select Product Tag", sorted_tags if sorted_tags else ["No Tags Found"])

    filtered_rows = []

    for edge in all_products:
        node = edge['node']
        tags = node.get('tags', [])
        
        if selected_tag in tags:
            for wh_prod in node.get('warehouse_products', []):
                for loc_edge in wh_prod.get('locations', {}).get('edges', []):
                    loc_name = loc_edge['node']['location']['name']
                    qty = loc_edge['node']['quantity']
                    
                    # Match location keyword to rate card
                    daily_rate = 0.0
                    for key, rate in STORAGE_RATES.items():
                        if key.lower() in loc_name.lower():
                            daily_rate = rate
                            break
                    
                    filtered_rows.append({
                        "SKU": node['sku'],
                        "Product Name": node['name'],
                        "Location": loc_name,
                        "Quantity": qty,
                        "Daily Rate": daily_rate,
                        "Est. Monthly (30 Day)": round(daily_rate * 30, 2)
                    })

    if filtered_rows:
        df = pd.DataFrame(filtered_rows)
        
        # Summary Metrics
        total_monthly = df["Est. Monthly (30 Day)"].sum()
        c1, c2 = st.columns(2)
        c1.metric(f"Total Monthly Storage: {selected_tag}", f"${total_monthly:,.2f}")
        c2.metric("Target Unit Rate", "$0.65/cuft Avg")

        # Table
        st.dataframe(df, use_container_width=True)
        
        # CSV Export
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(f"Download {selected_tag} Report", csv, f"{selected_tag}_storage.csv", "text/csv")
    else:
        st.info("Select a tag from the sidebar to view storage costs.")

else:
    st.error("Unable to connect to ShipHero API. Please check your token in Streamlit Secrets.")
