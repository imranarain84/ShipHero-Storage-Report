import streamlit as st
import pandas as pd
import requests

# --- 1. CONFIGURATION, SECRETS & BRANDING ---
st.set_page_config(
    page_title="VP Storage Report", 
    page_icon="VP Warehouse Icon TP.png", 
    layout="wide"
)

# Custom CSS for the dark header and centered white logo
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
    /* Hide the index column for tables in the sidebar */
    [data-testid="stSidebar"] table thead tr th:first-child, 
    [data-testid="stSidebar"] table tbody tr th:first-child {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

# Centered Logo Display
st.markdown('<div class="logo-container">', unsafe_allow_html=True)
st.image("VP Logo Horizontal Transparent White Lettering.png", width=400)
st.markdown('</div>', unsafe_allow_html=True)

SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"

if "SHIPHERO_TOKEN" not in st.secrets:
    st.error("❌ 'SHIPHERO_TOKEN' not found in Streamlit Secrets.")
    st.stop()

token = st.secrets["SHIPHERO_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# --- 2. STORAGE RATE CARD ---
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
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'], df['Type']))
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
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

    # Dropdown in Sidebar
    available_tags = sorted(list({t for e in product_edges for t in e['node'].get('tags', []) if t}))
    selected_tag = st.sidebar.selectbox("Filter by Product Tag", ["Show All"] + available_tags)

    report_list = []
    for edge in product_edges:
        node = edge.get('node', {})
        node_tags = node.get('tags', [])
        
        if selected_tag == "Show All" or selected_tag in node_tags:
            for wh_prod in node.get('warehouse_products', []):
                loc_edges = wh_prod.get('locations', {}).get('edges', [])
                for loc_edge in loc_edges:
                    l_node = loc_edge.get('node', {})
                    l_name = l_node.get('location', {}).get('name', 'Unknown')
                    inv_qty = l_node.get('quantity', 0)
                    
                    l_type = location_map.get(l_name, "Unknown")
                    daily_fee = STORAGE_TYPES.get(l_type, 0.0)

                    report_list.append({
                        "SKU": node.get('sku'),
                        "Location": l_name,
                        "Storage Type": l_type,
                        "Inv Qty": inv_qty,
                        "Daily Rate": daily_fee,
                        "Monthly Est.": round(daily_fee * 30, 2)
                    })

    if report_list:
        df = pd.DataFrame(report_list)
        total_monthly = df["Monthly Est."].sum()
        
        # --- Sidebar Summary Table ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("Cost Breakdown")
        
        # Aggregate data: Count unique locations and sum costs
        summary_df = df.groupby("Storage Type").agg(
            Quantity=('Location', 'count'),
            Total_Cost=('Monthly Est.', 'sum')
        ).reset_index()
        
        # Reorder columns: Quantity, Storage Type, Total Cost
        summary_df = summary_df[['Quantity', 'Storage Type', 'Total_Cost']]
        
        # Format for display
        summary_df['Total_Cost'] = summary_df['Total_Cost'].map('${:,.2f}'.format)
        
        # We use st.write with CSS to hide the index, or st.table
        st.sidebar.table(summary_df)

        # --- Main Dashboard ---
        col1, col2 = st.columns(2)
        col1.metric(f"Total Monthly Cost ({selected_tag})", f"${total_monthly:,.2f}")
        col2.metric("Target Metric", "$0.65/cuft Avg")

        # Table Display (Main Area)
        # To keep row numbers hidden in the main dataframe, we use st.dataframe(hide_index=True)
        main_display_df = df.copy()
        main_display_df["Monthly Est."] = main_display_df["Monthly Est."].map('${:,.2f}'.format)
        main_display_df["Daily Rate"] = main_display_df["Daily Rate"].map('${:,.4f}'.format)
        
        st.dataframe(main_display_df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV Report", df.to_csv(index=False), "storage_report.csv", "text/csv")
    else:
        st.info(f"No active inventory for items tagged: {selected_tag}")
else:
    st.error("API Connection Error. Verify your SHIPHERO_TOKEN.")
