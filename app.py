import streamlit as st
import pandas as pd
import requests

# --- 1. CONFIGURATION, SECRETS & BRANDING ---
st.set_page_config(
    page_title="VP Storage Report", 
    page_icon="VP Warehouse Icon TP.png", 
    layout="wide"
)

# Custom CSS to handle the white logo on the dark header
st.markdown("""
    <style>
    [data-testid="stHeader"] {
        background-color: #0e1117;
    }
    .logo-container {
        display: flex;
        justify-content: center;
        background-color: #0e1117;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# Centered Logo Display using your uploaded branding
st.markdown('<div class="logo-container">', unsafe_allow_html=True)
st.image("VP Logo Horizontal Transparent White Lettering.png", width=400)
st.markdown('</div>', unsafe_allow_html=True)

SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"

# Ensure API Token exists in Streamlit Cloud Secrets
if "SHIPHERO_TOKEN" not in st.secrets:
    st.error("❌ 'SHIPHERO_TOKEN' not found in Streamlit Secrets.")
    st.stop()

token = st.secrets["SHIPHERO_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# --- 2. STORAGE RATE CARD ---
# Data derived from Billing Profile: Flat Rate Shipping Cost by Weight [cite: 5-20, 55-84, 94, 104]
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

# --- 3. LOAD LOCATION DATA ---
@st.cache_data
def get_location_lookup():
    try:
        # Loading your merged CSV file from GitHub
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'], df['Type']))
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return {}

location_map = get_location_lookup()

# --- 4. API DATA FETCHING ---
@st.cache_data(ttl=300)
def fetch_shiphero_data():
    # GraphQL query structured for ShipHero API [cite: 1]
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
        if r.status_code == 200:
            return r.json()
        else:
            return None
    except:
        return None

# --- 5. PROCESSING & UI ---
st.title("📦 Warehouse Storage Report")

data_response = fetch_shiphero_data()

if data_response and 'data' in data_response:
    product_connection = data_response.get('data', {}).get('products', {}).get('data', {})
    product_edges = product_connection.get('edges', [])
    
    if not product_edges:
        st.warning("No products found in the account.")
        st.stop()

    # Dynamic dropdown for all account tags
    available_tags = sorted(list({t for e in product_edges for t in e['node'].get('tags', []) if t}))
    selected_tag = st.sidebar.selectbox("Filter by Product Tag", ["Show All"] + available_tags)

    report_list = []
    for edge in product_edges:
        node = edge.get('node', {})
        node_tags = node.get('tags', [])
        
        # Filtering logic for specific tags like "backmarket"
        if selected_tag == "Show All" or selected_tag in node_tags:
            for wh_prod in node.get('warehouse_products', []):
                loc_edges = wh_prod.get('locations', {}).get('edges', [])
                for loc_edge in loc_edges:
                    l_node = loc_edge.get('node', {})
                    l_name = l_node.get('location', {}).get('name', 'Unknown')
                    l_qty = l_node.get('quantity', 0)
                    
                    # Cross-reference ShipHero location name with CSV Type and Rate Card
                    l_type = location_map.get(l_name, "Unknown")
                    daily_fee = STORAGE_TYPES.get(l_type, 0.0)

                    report_list.append({
                        "SKU": node.get('sku'),
                        "Location": l_name,
                        "Storage Type": l_type,
                        "Quantity": l_qty,
                        "Daily Rate": daily_fee,
                        "Monthly Est.": round(daily_fee * 30, 2)
                    })

    if report_list:
        df = pd.DataFrame(report_list)
        total_monthly = df["Monthly Est."].sum()
        
        col1, col2 = st.columns(2)
        col1.metric(f"Total Monthly Storage ({selected_tag})", f"${total_monthly:,.2f}")
        col2.metric("Target Metric (Per Ryan)", "$0.65/cuft Avg")

        st.dataframe(df, use_container_width=True)
        st.download_button("Download CSV Report", df.to_csv(index=False), "storage_report.csv", "text/csv")
    else:
        st.info(f"No active inventory for items tagged: {selected_tag}")
else:
    st.error("API Connection Error. Please verify your SHIPHERO_TOKEN and Network.")
