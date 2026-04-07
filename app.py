import streamlit as st
import pandas as pd
import requests
import time
import json
import os
from datetime import date

# --- 1. CONFIGURATION & BRANDING ---
st.set_page_config(page_title="VP Storage Report", page_icon="VP Warehouse Icon TP.png", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 8rem; }
    [data-testid="stHeader"] { background-color: #0e1117; height: 0px; }
    .logo-container { display: flex; justify-content: center; background-color: #0e1117; padding: 10px 0px; }
    .report-header { text-align: center; margin-bottom: 0px; color: white; font-size: 42px; font-weight: bold; }
    .client-logo-container { display: flex; justify-content: center; padding-top: 10px; padding-bottom: 20px; }
    div.stButton > button { display: block; margin: 0 auto; width: 100%; background-color: #161b22; color: white; border: 1px solid #30363d; }
    .vp-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #555e67; text-align: center; padding: 20px 0px; font-size: 13px; z-index: 999999; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="logo-container">', unsafe_allow_html=True)
st.image("VP Logo Horizontal Transparent White Lettering.png", width=250)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<h1 class='report-header'>Warehouse Storage Cost Report</h1>", unsafe_allow_html=True)
st.markdown('<div class="client-logo-container">', unsafe_allow_html=True)
st.image("snow-logo.png", width=240) 
st.markdown('</div>', unsafe_allow_html=True)

# --- 2. API & FILE CONFIGURATION ---
token = st.secrets.get("SHIPHERO_TOKEN_SNOW")
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"
HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
CSV_FILE = "updated_tags.csv" 

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

# --- 4. DATA UTILITIES ---
@st.cache_data
def load_csv_data():
    if not os.path.exists(CSV_FILE): return None, None
    try:
        df = pd.read_csv(CSV_FILE)
        df.columns = df.columns.str.strip().str.lower()
        unique_tags = sorted(df['tag'].dropna().unique().tolist())
        tag_to_skus = df.groupby('tag')['sku'].apply(list).to_dict()
        return unique_tags, tag_to_skus
    except: return None, None

@st.cache_data
def get_loc_map():
    try:
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'], df['Type']))
    except: return {}

# --- 5. UPDATED FETCH ENGINE (Iteration 4.8) ---
def fetch_and_filter_inventory(sku_list, selected_tags):
    verified_results = []
    search_tags = [t.lower().strip() for t in selected_tags]
    
    for i in range(0, len(sku_list), 40):
        batch = sku_list[i:i+40]
        formatted_skus = json.dumps([str(s).strip() for s in batch])
        query = f"query {{ products(skus: {formatted_skus}) {{ data(first: 50) {{ edges {{ node {{ sku name tags warehouse_products {{ locations(first: 15) {{ edges {{ node {{ quantity location {{ name }} }} }} }} }} }} }} }} }} }}"
        
        try:
            r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS, timeout=30)
            res = r.json()
            if 'errors' in res and "credits" in res['errors'][0].get('message', '').lower():
                time.sleep(8); r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS); res = r.json()
            
            edges = res.get('data', {}).get('products', {}).get('data', {}).get('edges', [])
            
            for edge in edges:
                # Get the actual tags from ShipHero for this product
                live_tags = [t.lower().strip() for t in edge['node'].get('tags', [])]
                
                # Check if the product's tags CONTAINS any of the selected tags
                if any(tag in live_tags for tag in search_tags):
                    verified_results.append(edge)
            
            time.sleep(0.4)
        except: continue
    return verified_results

# --- 6. UI SIDEBAR ---
available_tags, tag_map = load_csv_data()

if available_tags is None:
    st.sidebar.warning(f"⚠️ {CSV_FILE} not found!")
    st.stop()

selected_tags = st.sidebar.multiselect(
    "Select Product Tag (Select all that apply)", 
    options=available_tags,
    help="The report will include any SKU from your CSV that contains these tags in ShipHero."
)

today = date.today()
date_range = st.sidebar.date_input("Select Date Range", value=(today.replace(day=1), today), format="MM/DD/YYYY")

st.sidebar.markdown("<br>", unsafe_allow_html=True)
generate_btn = st.sidebar.button("Generate Report")

# --- 7. MAIN CONTENT ---
if not selected_tags:
    st.info("👈 Please select one or more product tags in the sidebar and click 'Generate Report'.")
else:
    if generate_btn:
        num_days = (date_range[1] - date_range[0]).days + 1 if isinstance(date_range, tuple) and len(date_range) == 2 else 1
        
        # Get SKUs from CSV that are associated with selected tags
        sku_pool = []
        for tag in selected_tags: sku_pool.extend(tag_map.get(tag, []))
        sku_pool = list(set(sku_pool))
        
        with st.spinner(f"Scanning {len(sku_pool)} SKUs for matching tags..."):
            raw_edges = fetch_and_filter_inventory(sku_pool, selected_tags)
            
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
            c1, c2 = st.columns(2)
            c1.metric("Total Period Cost", f"${df['Period Cost'].sum():,.2f}")
            c2.metric("Days Counted", f"{num_days} Days")
            
            st.sidebar.subheader("Cost Breakdown")
            summary = df.groupby("Storage Type").agg(Qty=('Location', 'count'), Cost=('Period Cost', 'sum')).reset_index()
            st.sidebar.dataframe(summary, hide_index=True, column_config={"Cost": st.column_config.NumberColumn(format="$%.2f")})

            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("Download CSV Report", df.to_csv(index=False), "report.csv")
        else:
            st.error("No inventory found. Ensure the SKUs in your CSV are correctly tagged in ShipHero.")
            if len(sku_pool) > 0:
                st.sidebar.info(f"Analyzed {len(sku_pool)} SKUs from CSV, but none contained the tag(s): {', '.join(selected_tags)}")

# --- 8. FOOTER ---
st.markdown(f"""
    <div class="vp-footer">
        v4.8 | Vertical Passage Operations
    </div>
    """, unsafe_allow_html=True)
