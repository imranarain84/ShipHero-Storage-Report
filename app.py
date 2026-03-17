import streamlit as st
import pandas as pd
import requests
from datetime import date

# --- 1. CONFIGURATION, SECRETS & BRANDING ---
st.set_page_config(
    page_title="VP Storage Report", 
    page_icon="VP Warehouse Icon TP.png", 
    layout="wide"
)

# Custom CSS for a compact, professional dark-mode branding
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    [data-testid="stHeader"] {
        background-color: #0e1117;
        height: 0px;
    }
    .logo-container {
        display: flex;
        justify-content: center;
        background-color: #0e1117;
        padding: 10px 0px; 
    }
    h1 {
        margin-top: -15px !important;
        text-align: center;
    }
    /* Clean up standalone app look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# Centered Logo
st.markdown('<div class="logo-container">', unsafe_allow_html=True)
st.image("VP Logo Horizontal Transparent White Lettering.png", width=250)
st.markdown('</div>', unsafe_allow_html=True)

SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"
token = st.secrets.get("SHIPHERO_TOKEN")
HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# --- 2. STORAGE RATE CARD ---
STORAGE_TYPES = {
    "Standard Bin": 0.0442, "Bin": 0.0442, "Blue Bin Small": 0.0488, 
    "Blue Bin Medium": 0.1462, "Blue Bin Large": 0.2925, "Gray Bin Small": 0.1846,
    "Gray Bin Medium": 0.2275, "Gray Bin Large": 0.325, "Pallet": 2.093,
    "Pallet Tall": 2.7274, "Pallet TALL": 2.7274, "Pallet Large": 2.652,
    "Pallet Medium Large": 1.7914, "Pallet Medium Small": 1.443,
    "Pallet Small Large": 0.9581, "Pallet Small": 0.5902, "Half Pallet": 1.0472,
    "Tractor Trailer Load Floor Storage": 52.00, "Wall - Back": 12.116,
    "Wall - Front": 4.4096, "Pallite_16": 0.0537, "Pallite - 48": 0.0357,
    "Pallite_48": 0.0357, "Palite_48": 0.0357, "Jumbo Receiving Pallet": 3.90,
    "HD": 2.275, "DT - Pallet": 2.2074
}

# --- 3. LOAD DATA ---
@st.cache_data
def get_location_lookup():
    try:
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'], df['Type']))
    except:
        return {}

location_map = get_location_lookup()

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

# --- 4. UI FILTERS ---
st.sidebar.header("Report Filters")

# UPDATED: Date Range Picker with Month/Day/Year display format
today = date.today()
date_range = st.sidebar.date_input(
    "Select Date Range (MM/DD/YYYY)",
    value=(today.replace(day=1), today),
    max_value=today,
    format="MM/DD/YYYY" 
)

# Calculate days for cost calculation
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    num_days = (end_date - start_date).days + 1
else:
    num_days = 1

data_response = fetch_shiphero_data()

if data_response and 'data' in data_response:
    product_edges = data_response.get('data', {}).get('products', {}).get('data', {}).get('edges', [])
    
    available_tags = sorted(list({t for e in product_edges for t in e['node'].get('tags', []) if t}))
    selected_tag = st.sidebar.selectbox("Select Product Tag", ["Show All"] + available_tags)

    report_list = []
    for edge in product_edges:
        node = edge.get('node', {})
        if selected_tag == "Show All" or selected_tag in node.get('tags', []):
            for wh_prod in node.get('warehouse_products', []):
                for loc_edge in wh_prod.get('locations', {}).get('edges', []):
                    l_node = loc_edge.get('node', {})
                    l_name = l_node.get('location', {}).get('name', 'Unknown')
                    inv_qty = l_node.get('quantity', 0)
                    
                    l_type = location_map.get(l_name, "Unknown")
                    daily_fee = STORAGE_TYPES.get(l_type, 0.0)

                    # LOGIC FIX: 0 Quantity = 0 Cost
                    total_period_cost = (daily_fee * num_days) if inv_qty > 0 else 0.0

                    report_list.append({
                        "SKU": node.get('sku'),
                        "Location": l_name,
                        "Storage Type": l_type,
                        "Inv Qty": inv_qty,
                        "Daily Rate": daily_fee,
                        "Period Cost": round(total_period_cost, 2)
                    })

    if report_list:
        df = pd.DataFrame(report_list)
        total_period_sum = df["Period Cost"].sum()
        
        # --- Sidebar Cost Breakdown ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("Cost Breakdown")
        summary_df = df.groupby("Storage Type").agg(
            Quantity=('Location', 'count'),
            Total_Cost=('Period Cost', 'sum')
        ).reset_index()
        
        st.sidebar.dataframe(
            summary_df[['Quantity', 'Storage Type', 'Total_Cost']], 
            use_container_width=True, hide_index=True,
            column_config={"Total_Cost": st.column_config.NumberColumn("Total Cost", format="$%.2f")}
        )

        # --- Main Dashboard ---
        st.title("📦 Warehouse Storage Report")
        c1, c2 = st.columns(2)
        c1.metric(f"Total Cost ({selected_tag})", f"${total_period_sum:,.2f}")
        c2.metric("Days Counted", f"{num_days} Days")

        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={
                "Daily Rate": st.column_config.NumberColumn("Daily Rate", format="$%.4f"),
                "Period Cost": st.column_config.NumberColumn(f"Cost ({num_days} Days)", format="$%.2f")
            }
        )
        st.download_button("Download CSV Report", df.to_csv(index=False), "storage_report.csv", "text/csv")
    else:
        st.info(f"No active inventory for items tagged: {selected_tag}")
else:
    st.error("API Connection Error. Verify your SHIPHERO_TOKEN.")
