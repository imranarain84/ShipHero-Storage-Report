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
    .header-box { text-align: center; width: 100%; margin-bottom: 5px; }
    .main-title-text { color: white; font-size: 42px; font-weight: bold; margin: 0; }
    .sidebar-branding { text-align: center; padding-bottom: 20px; border-bottom: 1px solid #30363d; margin-bottom: 20px; }
    div.stButton > button { width: 100%; background-color: #161b22; color: white; border: 1px solid #30363d; }
    .vp-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #555e67; text-align: center; padding: 15px 0px; font-size: 13px; border-top: 1px solid #30363d; z-index: 999999; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. HEADER ---
st.markdown("<div class='header-box'><h1 class='main-title-text'>Warehouse Storage Cost Report</h1></div>", unsafe_allow_html=True)
col_l, col_m, col_r = st.columns([1.5, 1, 1.5])
with col_m:
    st.image("snow-logo.png", width=250, use_container_width=True)
st.markdown("<hr style='border: 1px solid #30363d; margin-top: 10px; margin-bottom: 30px;'>", unsafe_allow_html=True)

# --- 3. API & CONFIG ---
token = st.secrets.get("SHIPHERO_TOKEN_SNOW")
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"
HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
CSV_FILE = "updated_tags.csv" 
W_PRIMARY, W_NORTH = "V2FyZWhvdXNlOjczNjY2", "V2FyZWhvdXNlOjExNjI4OA=="

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
        return sorted(df['tag'].dropna().unique().tolist()), df.groupby('tag')['sku'].apply(list).to_dict()
    except: return None, None

@st.cache_data
def get_loc_map():
    try:
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'].str.strip(), df['Type'].str.strip()))
    except: return {}

# --- 4. IMPROVED ROBUST ENGINE ---
def fetch_inventory_robust(sku_list):
    final_results = []
    progress_bar = st.progress(0)
    total = len(sku_list)
    
    batch_size = 8 # Reduced slightly for better stability
    for i in range(0, total, batch_size):
        batch = sku_list[i : i + batch_size]
        progress_bar.progress(min(i / total, 1.0))
        
        fragments = " ".join([f's{idx}: product(sku: "{s.strip()}") {{ data {{ sku name warehouse_products {{ warehouse_id locations(first: 50) {{ edges {{ node {{ quantity location {{ name }} }} }} }} }} }} }}' for idx, s in enumerate(batch)])
        
        try:
            r = requests.post(SHIPHERO_API_URL, json={'query': f"query {{ {fragments} }}"}, headers=HEADERS, timeout=60)
            data = r.json().get('data', {})
            
            if not data: # If API returns empty, wait and retry once
                time.sleep(5)
                r = requests.post(SHIPHERO_API_URL, json={'query': f"query {{ {fragments} }}"}, headers=HEADERS, timeout=60)
                data = r.json().get('data', {})

            for key in data:
                if data[key] and data[key].get('data'):
                    final_results.append(data[key]['data'])
            
            time.sleep(0.4) # Respectful throttle
        except: continue
            
    progress_bar.empty()
    return final_results

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown('<div class="sidebar-branding">', unsafe_allow_html=True)
    st.image("VP Logo Horizontal Transparent White Lettering.png", width=220)
    st.markdown('</div>', unsafe_allow_html=True)
    available_tags, tag_map = load_csv_data()
    selected_tags = st.multiselect("Select Tag", options=available_tags if available_tags else [])
    date_range = st.date_input("Date Range", value=(date.today().replace(day=1), date.today()), format="MM/DD/YYYY")
    generate_btn = st.button("Generate Report")

# --- 6. LOGIC ---
if generate_btn and selected_tags:
    num_days = (date_range[1] - date_range[0]).days + 1 if isinstance(date_range, tuple) and len(date_range) == 2 else 1
    sku_pool = list(set([sku for t in selected_tags for sku in tag_map.get(t, [])]))
    
    st.write(f"🔄 Processing {len(sku_pool)} SKUs from CSV...")
    products = fetch_inventory_robust(sku_pool)
    loc_type_map = get_loc_map()
    report = []
    
    for p in products:
        found_wh = False
        for wh in p.get('warehouse_products', []):
            if wh['warehouse_id'] in [W_PRIMARY, W_NORTH]:
                for edge in wh.get('locations', {}).get('edges', []):
                    found_wh = True
                    n = edge['node']
                    l_type = loc_type_map.get(n['location']['name'], "Unknown")
                    report.append({
                        "Product": p['name'], "SKU": p['sku'], "Location": n['location']['name'],
                        "Type": l_type, "Qty": n['quantity'], "Period Cost": round(STORAGE_TYPES.get(l_type, 0.0) * num_days, 2)
                    })
        if not found_wh:
            report.append({"Product": p['name'], "SKU": p['sku'], "Location": "No Bin Found", "Type": "N/A", "Qty": 0, "Period Cost": 0.0})

    if report:
        df = pd.DataFrame(report)
        st.success(f"Verified {len(df['SKU'].unique())} SKUs.")
        st.metric("Total Period Cost", f"${df['Period Cost'].sum():,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), "report.csv")
    else:
        st.error("❌ No matching inventory found in ShipHero.")

st.markdown(f'<div class="vp-footer">v8.0 | Vertical Passage Operations</div>', unsafe_allow_html=True)
