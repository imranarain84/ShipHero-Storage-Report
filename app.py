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

# Professional CSS for a compact, centered layout
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

# Date Picker (MM/DD/YYYY)
today = date.today()
date_range = st.sidebar.date_input(
    "Select Date Range (MM/DD/YYYY)",
    value=(today.replace(day=1), today),
    max_value=today,
    format="MM/DD/YYYY"
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    num_days = (end_date - start_date).days + 1
else:
    num_days = 1

data_response = fetch_shiphero_data()

if data_response and 'data' in data_response:
    product_edges = data_response.get('data', {}).get('products', {}).get('data', {}).get('edges', [])
    
    # --- MULTI-SELECT TAGS ---
    available_tags = sorted(list({t for e in product_edges for t in e['node'].get('tags', []) if t}))
    selected_tags = st.sidebar.multiselect(
        "Select Product Tags", 
        options=available_tags, 
        default=[],
        help="If empty, all items will be shown."
    )

    report_list = []
    for edge in product_edges:
        node = edge.get('node', {})
        node_tags = node.get('tags', [])
        
        # Match if no tags are selected (Show All) OR if product has one of the selected tags
        if not selected_tags or any(tag in node_tags for tag in selected_tags):
            for wh_prod in node.get('warehouse_products', []):
                for loc_edge in wh_prod.get('locations', {}).get('edges', []):
                    l_node = loc_edge.get('node', {})
                    l_name = l_node.get('location', {}).get('name', 'Unknown')
                    inv_qty = l_node.get('quantity', 0)
                    
                    l_type = location_map.get(l_name, "Unknown")
                    daily_fee = STORAGE_TYPES.get(l_type, 0.0)

                    # 0 Qty = 0 Cost logic
                    total_period_cost = (daily_fee * num_days) if inv_qty > 0 else 0.0

                    row = {
                        "SKU": node.get('sku'),
                        "Location": l_name,
                        "Storage Type": l_type,
                        "Inv Qty": inv_qty,
                        "Daily Rate": daily_fee,
                        "Period Cost": round(total_period_cost, 2)
                    }
                    
                    # Add 'Matching Tags' column ONLY if 2 or more tags are selected
                    if len(selected_tags) > 1:
                        # Only show the tags that caused the match
                        tags_present = [t for t in node_tags if t in selected_tags]
                        row["Matching Tags"] = ", ".join(tags_present)
                    
                    report_list.append(row)

    if report_list:
        df = pd.DataFrame(report_list)
        total_period_sum = df["Period Cost"].sum()
        
        # Sidebar Cost Breakdown
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

        # Main Dashboard
        st.title("📦 Warehouse Storage Report")
        c1, c2 = st.columns(2)
        c1.metric("Total Period Cost", f"${total_period_sum:,.2f}")
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
        st.info("No active inventory found for the selected criteria.")
else:
    st.error("API Connection Error. Verify your SHIPHERO_TOKEN.")
