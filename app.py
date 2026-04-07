import streamlit as st
import pandas as pd
import requests
import time
from datetime import date

# --- 1. CONFIGURATION & BRANDING ---
st.set_page_config(
    page_title="VP Storage Report", 
    page_icon="VP Warehouse Icon TP.png", 
    layout="wide"
)

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    [data-testid="stHeader"] { background-color: #0e1117; height: 0px; }
    .logo-container { display: flex; justify-content: center; background-color: #0e1117; padding: 10px 0px; }
    h1 { margin-top: -15px !important; text-align: center; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #555; text-align: center; padding: 10px; font-size: 12px; border-top: 1px solid #333; z-index: 999; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="logo-container">', unsafe_allow_html=True)
st.image("VP Logo Horizontal Transparent White Lettering.png", width=250)
st.markdown('</div>', unsafe_allow_html=True)

# --- 2. API CONFIGURATION ---
token = st.secrets.get("SHIPHERO_TOKEN_SNOW")
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"
HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

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

# --- 4. IMPROVED TAG FETCHING WITH PROGRESS ---
def fetch_all_tags():
    all_tags = set()
    cursor = None
    has_next = True
    
    # UI Progress components
    progress_text = st.sidebar.empty()
    progress_bar = st.sidebar.progress(0)
    
    page_count = 0
    while has_next:
        page_count += 1
        progress_text.text(f"Scanning Catalog (Page {page_count})...")
        progress_bar.progress(min(page_count * 5, 100)) # Simple visual increment
        
        cursor_arg = f', after: "{cursor}"' if cursor else ""
        query = f"query {{ products {{ data(first: 500{cursor_arg}) {{ pageInfo {{ hasNextPage endCursor }} edges {{ node {{ tags }} }} }} }} }}"
        
        try:
            r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS, timeout=20)
            res = r.json()
            
            if 'errors' in res:
                st.sidebar.error(f"API Error: {res['errors'][0]['message']}")
                break
                
            data = res.get('data', {}).get('products', {}).get('data', {})
            edges = data.get('edges', [])
            
            if not edges: break
            
            for edge in edges:
                for tag in edge['node'].get('tags', []):
                    if tag: all_tags.add(tag)
            
            has_next = data.get('pageInfo', {}).get('hasNextPage', False)
            cursor = data.get('pageInfo', {}).get('endCursor')
            
        except Exception as e:
            st.sidebar.error(f"Connection Failed: {e}")
            break
            
    progress_text.empty()
    progress_bar.empty()
    return sorted(list(all_tags))

# --- 5. TARGETED DATA FETCHING ---
@st.cache_data(ttl=300)
def fetch_report_data(selected_tags):
    report_data = []
    for tag in selected_tags:
        cursor = None
        has_next = True
        while has_next:
            cursor_arg = f', after: "{cursor}"' if cursor else ""
            query = f"""
            query {{
              products(tag: "{tag}") {{
                data(first: 100{cursor_arg}) {{
                  pageInfo {{ hasNextPage endCursor }}
                  edges {{
                    node {{
                      sku name tags
                      warehouse_products {{
                        locations(first: 20) {{
                          edges {{ node {{ quantity location {{ name }} }} }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            """
            r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS, timeout=20)
            res = r.json()
            
            if 'errors' in res and "credits" in res['errors'][0].get('message', ''):
                time.sleep(5)
                continue
                
            page = res.get('data', {}).get('products', {}).get('data', {})
            report_data.extend(page.get('edges', []))
            has_next = page.get('pageInfo', {}).get('hasNextPage', False)
            cursor = page.get('pageInfo', {}).get('endCursor')
            
    return report_data

# --- 6. UI FLOW ---
st.sidebar.header("1. Data Initialization")

# We call the tag fetcher. It now manages its own progress bar in the sidebar.
tags_list = fetch_all_tags()

if not tags_list:
    st.sidebar.warning("No tags found. Check API Token.")
    selected_tags = []
else:
    selected_tags = st.sidebar.multiselect("Select Product Tags", options=tags_list)

st.sidebar.markdown("---")
st.sidebar.header("2. Date Range")
today = date.today()
date_range = st.sidebar.date_input("Select Range", value=(today.replace(day=1), today), format="MM/DD/YYYY")

if not selected_tags:
    st.title("📦 Storage Report")
    st.info("👈 Please select one or more tags in the sidebar to start.")
    st.stop()

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    num_days = (end_date - start_date).days + 1
else:
    num_days = 1

# Heavy fetch happens here
with st.spinner(f"Pulling location data for: {', '.join(selected_tags)}..."):
    raw_edges = fetch_report_data(selected_tags)

# --- 7. PROCESSING & DISPLAY ---
@st.cache_data
def get_location_map():
    try:
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'], df['Type']))
    except: return {}

loc_type_map = get_location_map()
report_list = []

for edge in raw_edges:
    node = edge['node']
    for wh_prod in node.get('warehouse_products', []):
        for loc_edge in wh_prod.get('locations', {}).get('edges', []):
            l_node = loc_edge['node']
            qty = l_node.get('quantity', 0)
            l_name = l_node.get('location', {}).get('name', 'Unknown')
            l_type = loc_type_map.get(l_name, "Unknown")
            daily_rate = STORAGE_TYPES.get(l_type, 0.0)
            
            cost = (daily_rate * num_days) if qty > 0 else 0.0
            
            report_list.append({
                "Product Name": node.get('name'),
                "SKU": node.get('sku'),
                "Location": l_name,
                "Storage Type": l_type,
                "Inv Qty": qty,
                "Daily Rate": daily_rate,
                "Period Cost": round(cost, 2)
            })

if report_list:
    df = pd.DataFrame(report_list)
    st.title("📦 Snow Commerce Storage Report")
    
    c1, c2 = st.columns(2)
    c1.metric("Total Period Cost", f"${df['Period Cost'].sum():,.2f}")
    c2.metric("Days Counted", f"{num_days} Days")

    st.sidebar.subheader("Cost Breakdown")
    summary = df.groupby("Storage Type").agg(Qty=('Location', 'count'), Cost=('Period Cost', 'sum')).reset_index()
    st.sidebar.dataframe(summary, hide_index=True, column_config={"Cost": st.column_config.NumberColumn(format="$%.2f")})

    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        "Daily Rate": st.column_config.NumberColumn(format="$%.4f"),
        "Period Cost": st.column_config.NumberColumn(format="$%.2f")
    })
    st.download_button("Download CSV", df.to_csv(index=False), "report.csv", "text/csv")
else:
    st.warning("No inventory found for the selected tags.")

st.markdown(f'<div class="footer">Vertical Passage Warehouse Operations | Revision: March 17, 2026</div>', unsafe_allow_html=True)
