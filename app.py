import streamlit as st
import pandas as pd
import requests
import time
from datetime import date

# --- 1. CONFIGURATION & BRANDING ---
st.set_page_config(page_title="VP Storage Report", page_icon="VP Warehouse Icon TP.png", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 6rem; }
    [data-testid="stHeader"] { background-color: #0e1117; height: 0px; }
    .logo-container { display: flex; justify-content: center; background-color: #0e1117; padding: 10px 0px; }
    h1 { margin-top: -15px !important; text-align: center; }
    .custom-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #161b22; color: #8b949e; 
                     text-align: center; padding: 15px 0; font-size: 12px; border-top: 1px solid #30363d; z-index: 9999; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="logo-container">', unsafe_allow_html=True)
st.image("VP Logo Horizontal Transparent White Lettering.png", width=250)
st.markdown('</div>', unsafe_allow_html=True)

# --- 2. API & FILE CONFIGURATION ---
token = st.secrets.get("SHIPHERO_TOKEN_SNOW")
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"
HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
CSV_FILE = "sku_tags.csv"

# --- 3. STORAGE RATE CARD ---
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

# --- 4. CSV & DATA UTILITIES ---
@st.cache_data
def load_csv_data():
    try:
        df = pd.read_csv(CSV_FILE)
        df.columns = df.columns.str.strip().str.lower()
        # Get unique list of tags for the dropdown
        unique_tags = sorted(df['tag'].unique().tolist())
        # Create mapping of Tag -> List of SKUs
        tag_to_skus = df.groupby('tag')['sku'].apply(list).to_dict()
        return unique_tags, tag_to_skus
    except Exception as e:
        st.error(f"Error loading {CSV_FILE}: {e}")
        return [], {}

@st.cache_data
def get_loc_map():
    try:
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'], df['Type']))
    except: return {}

# --- 5. TARGETED FETCH (BY SKU BATCHES) ---
def fetch_inventory_for_skus(sku_list):
    all_results = []
    # Fetching in batches of 50 SKUs per request for speed/safety
    for i in range(0, len(sku_list), 50):
        batch = sku_list[i:i+50]
        # Format list for GraphQL: ["SKU1", "SKU2"]
        formatted_skus = json.dumps(batch)
        
        query = f"""
        query {{
          products(skus: {formatted_skus}) {{
            data(first: 50) {{
              edges {{
                node {{
                  sku name tags
                  warehouse_products {{
                    locations(first: 10) {{
                      edges {{ node {{ quantity location {{ name }} }} }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        try:
            r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS)
            res = r.json()
            
            if 'errors' in res and "credits" in res['errors'][0].get('message', ''):
                time.sleep(6)
                # Simple retry for this batch
                r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS)
                res = r.json()
                
            edges = res.get('data', {}).get('products', {}).get('data', {}).get('edges', [])
            all_results.extend(edges)
            time.sleep(0.5)
        except:
            continue
    return all_results

# --- 6. UI FLOW ---
st.sidebar.header("1. Filter Settings")
available_tags, tag_map = load_csv_data()

selected_tag = st.sidebar.selectbox("Select Client Tag", options=[""] + available_tags)

st.sidebar.markdown("---")
st.sidebar.header("2. Date Range")
today = date.today()
date_range = st.sidebar.date_input("Select Range", value=(today.replace(day=1), today), format="MM/DD/YYYY")

generate_btn = st.sidebar.button("🚀 Generate Report")

if not selected_tag:
    st.title("📦 Storage Cost Reporter")
    st.info("👈 Select a tag from your CSV in the sidebar to begin.")
    st.stop()

if generate_btn:
    # Calculation for days
    if isinstance(date_range, tuple) and len(date_range) == 2:
        num_days = (date_range[1] - date_range[0]).days + 1
    else:
        num_days = 1

    skus_to_fetch = tag_map.get(selected_tag, [])
    
    with st.spinner(f"Fetching data for {len(skus_to_fetch)} SKUs..."):
        import json # Needed for sku formatting
        raw_edges = fetch_inventory_for_skus(skus_to_fetch)
        
    # Process results
    loc_type_map = get_loc_map()
    report_list = []

    for edge in raw_edges:
        node = edge['node']
        for wh_prod in node.get('warehouse_products', []):
            for loc_edge in wh_prod.get('locations', {}).get('edges', []):
                l_node = loc_edge['node']
                qty, l_name = l_node.get('quantity', 0), l_node.get('location', {}).get('name', 'Unknown')
                l_type = loc_type_map.get(l_name, "Unknown")
                rate = STORAGE_TYPES.get(l_type, 0.0)
                cost = (rate * num_days) if qty > 0 else 0.0
                
                report_list.append({
                    "Product Name": node.get('name'), "SKU": node.get('sku'), "Location": l_name,
                    "Storage Type": l_type, "Inv Qty": qty, "Daily Rate": rate, "Period Cost": round(cost, 2)
                })

    if report_list:
        df = pd.DataFrame(report_list)
        st.title(f"📦 {selected_tag} Storage Report")
        
        c1, c2 = st.columns(2)
        c1.metric("Total Period Cost", f"${df['Period Cost'].sum():,.2f}")
        c2.metric("Days Counted", f"{num_days} Days")
        
        # Sidebar breakdown
        summary = df.groupby("Storage Type").agg(Qty=('Location', 'count'), Cost=('Period Cost', 'sum')).reset_index()
        st.sidebar.subheader("Cost Breakdown")
        st.sidebar.dataframe(summary, hide_index=True, column_config={"Cost": st.column_config.NumberColumn(format="$%.2f")})

        st.dataframe(df, use_container_width=True, hide_index=True, column_config={
            "Daily Rate": st.column_config.NumberColumn(format="$%.4f"),
            "Period Cost": st.column_config.NumberColumn(format="$%.2f")
        })
        st.download_button("Download CSV", df.to_csv(index=False), f"{selected_tag}_report.csv", "text/csv")
    else:
        st.warning("No inventory records found for those SKUs in ShipHero.")

# --- 7. FOOTER ---
st.markdown(f"""
    <div class="custom-footer">
        Vertical Passage Warehouse Operations | Iteration: 4.0 (CSV-Targeted) | Revision: {date.today().strftime('%B %d, %Y')}
    </div>
    """, unsafe_allow_html=True)
