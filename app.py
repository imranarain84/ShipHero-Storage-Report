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
    .block-container { padding-top: 1rem; padding-bottom: 10rem; }
    [data-testid="stHeader"] { background-color: #0e1117; height: 0px; }
    .report-title-container { flex-grow: 2; text-align: center; }
    div.stButton > button { display: block; margin: 0 auto; width: 100%; background-color: #161b22; color: white; border: 1px solid #30363d; }
    .vp-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #555e67; text-align: center; padding: 15px 0px; font-size: 13px; border-top: 1px solid #30363d; z-index: 999999; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .sidebar-logo-container { display: flex; justify-content: center; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API & DATA CONFIGURATION ---
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
        df['sku'] = df['sku'].str.strip()
        df['tag'] = df['tag'].str.strip()
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

# --- 3. STABLE BATCH FETCH ENGINE ---
def fetch_inventory_stable(sku_list, selected_tags):
    final_results = []
    normalized_selections = [str(t).lower().strip() for t in selected_tags]
    
    progress_text = st.empty()
    progress_bar = st.progress(0)
    total_skus = len(sku_list)
    
    # Process 5 at a time to balance speed and ShipHero stability
    batch_size = 5
    for i in range(0, total_skus, batch_size):
        batch = sku_list[i : i + batch_size]
        current_percent = int((i / total_skus) * 100)
        progress_text.markdown(f"**Loading... {current_percent}%**")
        progress_bar.progress(i / total_skus)
        
        # Build individual fragments for the batch
        fragments = ""
        for idx, sku in enumerate(batch):
            fragments += f'sku_{idx}: product(sku: "{sku.strip()}") {{ data {{ sku name tags warehouse_products {{ warehouse_id locations(first: 50) {{ edges {{ node {{ quantity location {{ name }} }} }} }} }} }} }} '

        query = f"query {{ {fragments} }}"
        
        try:
            r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS, timeout=60)
            res = r.json()
            
            # Handle credit limits
            if 'errors' in res and "credits" in res['errors'][0].get('message', '').lower():
                time.sleep(15)
                r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS)
                res = r.json()
            
            data = res.get('data', {})
            for key in data:
                product_data = data[key].get('data')
                if product_data:
                    ship_tags = [str(t).lower().strip() for t in product_data.get('tags', [])]
                    if any(sel in ship_tags for sel in normalized_selections):
                        final_results.append(product_data)
            
            time.sleep(0.4)
        except Exception as e:
            continue
            
    progress_text.empty()
    progress_bar.empty()
    return final_results

# --- 4. HEADER LAYOUT ---
available_tags, tag_map = load_csv_data()
h_col1, h_col2, h_col3 = st.columns([1, 2, 1])
with h_col1: st.image("snow-logo.png", width=220)
with h_col2: st.markdown("<h1 style='text-align: center; color: white; padding-top: 10px;'>Warehouse Storage Cost Report</h1>", unsafe_allow_html=True)
with h_col3: st.write("")
st.markdown("---")

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown('<div class="sidebar-logo-container">', unsafe_allow_html=True)
    st.image("VP Logo Horizontal Transparent White Lettering.png", width=220)
    st.markdown('</div>', unsafe_allow_html=True)
    st.header("Report Filters")
    selected_tags = st.multiselect("Select Product Tag", options=available_tags if available_tags else [])
    date_range = st.date_input("Date Range", value=(date.today().replace(day=1), date.today()))
    generate_btn = st.button("Generate Report")

# --- 6. PROCESSING ---
if not selected_tags:
    st.info("👈 Select a tag in the sidebar to begin.")
else:
    if generate_btn:
        num_days = (date_range[1] - date_range[0]).days + 1 if isinstance(date_range, tuple) and len(date_range) == 2 else 1
        sku_pool = []
        for tag in selected_tags: sku_pool.extend(tag_map.get(tag, []))
        sku_pool = list(set(sku_pool))
        
        verified_products = fetch_inventory_stable(sku_pool, selected_tags)
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
            st.success(f"Verified {len(df['SKU'].unique())} unique SKUs.")
            c1, c2 = st.columns(2)
            c1.metric("Total Period Cost", f"${df['Period Cost'].sum():,.2f}")
            c2.metric("Days Counted", f"{num_days} Days")
            st.sidebar.subheader("Cost Breakdown")
            summary = df.groupby("Storage Type").agg(Qty=('Location', 'count'), Cost=('Period Cost', 'sum')).reset_index()
            st.sidebar.dataframe(summary, hide_index=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("Download CSV", df.to_csv(index=False), "report.csv")
        else:
            st.error("❌ No matching inventory found.")

st.markdown(f'<div class="vp-footer">v6.7 | Vertical Passage Operations</div>', unsafe_allow_html=True)
