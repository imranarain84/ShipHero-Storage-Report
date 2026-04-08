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
    .block-container { padding-top: 1rem !important; padding-bottom: 10rem; }
    .main-title { text-align: center; width: 100%; color: white; font-size: 42px; font-weight: bold; margin-top: 5px; }
    .sidebar-logo-container { text-align: center; padding: 10px 0px 20px 0px; border-bottom: 1px solid #30363d; margin-bottom: 20px; }
    div.stButton > button { width: 100%; background-color: #161b22; color: white; border: 1px solid #30363d; }
    .vp-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #555e67; text-align: center; padding: 15px 0px; font-size: 13px; border-top: 1px solid #30363d; z-index: 999999; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. HEADER ---
st.image("snow-logo.png", width=250)
st.markdown("<h1 class='main-title'>Warehouse Storage Cost Report</h1>", unsafe_allow_html=True)
st.markdown("<hr style='border: 1px solid #30363d; margin-top: 5px; margin-bottom: 30px;'>", unsafe_allow_html=True)

# --- 3. API & CONFIG ---
token = st.secrets.get("SHIPHERO_TOKEN_SNOW")
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"
HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
CSV_FILE = "updated_tags.csv" 

W_PRIMARY = "V2FyZWhvdXNlOjczNjY2"
W_NORTH = "V2FyZWhvdXNlOjExNjI4OA=="

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

@st.cache_data
def load_csv_data():
    if not os.path.exists(CSV_FILE): return None, None
    try:
        df = pd.read_csv(CSV_FILE, dtype={'sku': str})
        df.columns = df.columns.str.strip().str.lower()
        df['sku'] = df['sku'].str.strip(); df['tag'] = df['tag'].str.strip()
        unique_tags = sorted(df['tag'].dropna().unique().tolist())
        tag_to_skus = df.groupby('tag')['sku'].apply(list).to_dict()
        return unique_tags, tag_to_skus
    except: return None, None

@st.cache_data
def get_loc_map():
    try:
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'].str.strip(), df['Type'].str.strip()))
    except: return {}

# --- 4. DATA ENGINE (With Debugging) ---
def fetch_inventory_debug(sku_list, selected_tags, debug_on=False):
    final_results = []
    debug_log = []
    normalized_selections = [str(t).lower().strip() for t in selected_tags]
    
    progress_text = st.empty()
    progress_bar = st.progress(0)
    total_skus = len(sku_list)
    
    batch_size = 10
    for i in range(0, total_skus, batch_size):
        batch = sku_list[i : i + batch_size]
        progress_text.markdown(f"**Loading... {int((i/total_skus)*100)}%**")
        progress_bar.progress(i / total_skus)
        
        queries = ""
        for idx, sku in enumerate(batch):
            queries += f'sku_{idx}: product(sku: "{sku.strip()}") {{ data {{ sku name tags warehouse_products {{ warehouse_id on_hand locations(first: 50) {{ edges {{ node {{ quantity location {{ name }} }} }} }} }} }} }} '

        full_query = f"query {{ {queries} }}"
        try:
            r = requests.post(SHIPHERO_API_URL, json={'query': full_query}, headers=HEADERS, timeout=60)
            res = r.json()
            
            data_map = res.get('data', {})
            if not data_map and debug_on:
                debug_log.append({"batch": batch, "error": res.get("errors")})
            
            for alias_key in data_map:
                prod_node = data_map[alias_key].get('data') if data_map[alias_key] else None
                if prod_node:
                    final_results.append(prod_node)
                elif debug_on:
                    debug_log.append({"sku_failed": alias_key, "reason": "Not found in ShipHero"})
            
            time.sleep(0.3)
        except Exception as e:
            if debug_on: debug_log.append({"error": str(e)})
            continue
            
    progress_text.empty(); progress_bar.empty()
    return final_results, debug_log

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown('<div class="sidebar-logo-container">', unsafe_allow_html=True)
    st.image("VP Logo Horizontal Transparent White Lettering.png", width=220)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("Report Filters")
    available_tags, tag_map = load_csv_data()
    selected_tags = st.multiselect("Select Product Tag", options=available_tags if available_tags else [])
    date_range = st.date_input("Select Date Range", value=(date.today().replace(day=1), date.today()), format="MM/DD/YYYY")
    
    st.markdown("---")
    debug_mode = st.checkbox("🚀 Enable Debug Mode")
    generate_btn = st.button("Generate Report")

# --- 6. MAIN LOGIC ---
if not selected_tags:
    st.info("👈 Select a tag in the sidebar to begin.")
else:
    if generate_btn:
        num_days = (date_range[1] - date_range[0]).days + 1 if isinstance(date_range, tuple) and len(date_range) == 2 else 1
        sku_pool = []
        for tag in selected_tags: sku_pool.extend(tag_map.get(tag, []))
        sku_pool = list(set(sku_pool))
        
        if debug_mode:
            st.warning(f"DEBUG: CSV contains {len(sku_pool)} SKUs for this tag selection.")

        verified_products, logs = fetch_inventory_debug(sku_pool, selected_tags, debug_mode)
        
        if debug_mode and logs:
            with st.expander("🛠️ API Debug Logs"):
                st.write(logs)

        loc_type_map = get_loc_map()
        report_list = []
        for node in verified_products:
            for wh_prod in node.get('warehouse_products', []):
                if wh_prod['warehouse_id'] in [W_PRIMARY, W_NORTH]:
                    for loc_edge in wh_prod.get('locations', {}).get('edges', []):
                        l_node = loc_edge['node']
                        qty = l_node.get('quantity', 0)
                        l_name = str(l_node.get('location', {}).get('name', 'Unknown')).strip()
                        l_type = loc_type_map.get(l_name, "Unknown")
                        rate = STORAGE_TYPES.get(l_type, 0.0)
                        cost = (rate * num_days) if qty > 0 else 0.0
                        report_list.append({
                            "Product Name": node.get('name'), "SKU": node.get('sku'), "Location": l_name,
                            "Storage Type": l_type, "Inv Qty": qty, "Daily Rate": rate, "Period Cost": round(cost, 2)
                        })

        if report_list:
            df = pd.DataFrame(report_list)
            st.success(f"Verified {len(df['SKU'].unique())} unique SKUs found with inventory.")
            c1, c2 = st.columns(2)
            c1.metric("Total Period Cost", f"${df['Period Cost'].sum():,.2f}")
            c2.metric("Days Counted", f"{num_days} Days")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("Download CSV", df.to_csv(index=False), "report.csv")
        else:
            st.error("❌ No matching inventory found in ShipHero.")

st.markdown(f'<div class="vp-footer">v7.5 | Vertical Passage Operations</div>', unsafe_allow_html=True)
