import streamlit as st
import pandas as pd
import requests
from datetime import date

# --- 1. CONFIGURATION & BRANDING ---
st.set_page_config(
    page_title="VP Storage Report", 
    page_icon="VP Warehouse Icon TP.png", 
    layout="wide"
)

# Professional CSS for compact layout and custom footer
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem; 
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
    /* Custom Footer Styling */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #0e1117;
        color: #555;
        text-align: center;
        padding: 10px;
        font-size: 12px;
        border-top: 1px solid #333;
        z-index: 999;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# Centered Logo
st.markdown('<div class="logo-container">', unsafe_allow_html=True)
st.image("VP Logo Horizontal Transparent White Lettering.png", width=250)
st.markdown('</div>', unsafe_allow_html=True)

# --- 2. MULTI-ACCOUNT SELECTION ---
st.sidebar.header("Account Settings")
account_choice = st.sidebar.selectbox(
    "Select ShipHero Account",
    ["Snow Commerce", "Universal Parks"]
)

# Map choice to Secret Key
token_key = "SHIPHERO_TOKEN_SNOW" if account_choice == "Snow Commerce" else "SHIPHERO_TOKEN_UNIVERSAL"
token = st.secrets.get(token_key)

if not token:
    st.error(f"❌ Critical Error: `{token_key}` not found in Streamlit Secrets.")
    st.stop()

SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"

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

# --- 4. DATA FETCHING WITH PAGINATION & DEBUGGING ---
@st.cache_data
def get_location_lookup():
    try:
        df = pd.read_csv("ShipHero - Location Names and Info.csv")
        return dict(zip(df['Location'], df['Type']))
    except: return {}

location_map = get_location_lookup()

@st.cache_data(ttl=300)
def fetch_shiphero_data(api_token, account_name):
    all_products = []
    has_next_page = True
    cursor = None
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    while has_next_page:
        cursor_arg = f', after: "{cursor}"' if cursor else ""
        query = f"""
        query {{
          products {{
            data(first: 100{cursor_arg}) {{
              pageInfo {{
                hasNextPage
                endCursor
              }}
              edges {{
                node {{
                  sku
                  name
                  tags
                  warehouse_products {{
                    locations(first: 25) {{
                      edges {{
                        node {{
                          quantity
                          location {{ name }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        try:
            r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=headers, timeout=20)
            
            # DEBUG: Catch HTTP errors (401 Unauthorized, etc)
            if r.status_code != 200:
                return {"debug_error": f"HTTP {r.status_code}: {r.text}"}
            
            res = r.json()
            
            # DEBUG: Catch ShipHero internal errors
            if 'errors' in res:
                return res
            
            page_data = res.get('data', {}).get('products', {}).get('data', {})
            edges = page_data.get('edges', [])
            all_products.extend(edges)
            
            has_next_page = page_data.get('pageInfo', {}).get('hasNextPage', False)
            cursor = page_data.get('pageInfo', {}).get('endCursor')
            
        except Exception as e:
            return {"debug_error": str(e)}
            
    return {"all_edges": all_products}

# --- 5. UI & PROCESSING ---
st.sidebar.markdown("---")
st.sidebar.header("Report Filters")

today = date.today()
date_range = st.sidebar.date_input(
    "Select Date Range (MM/DD/YYYY)", 
    value=(today.replace(day=1), today), 
    format="MM/DD/YYYY"
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    num_days = (end_date - start_date).days + 1
else:
    num_days = 1

with st.spinner(f'Fetching all catalog data for {account_choice}...'):
    data_response = fetch_shiphero_data(token, account_choice)

# --- DEBUG MODE ERROR HANDLING ---
if "debug_error" in data_response:
    st.error(f"⚠️ Connection Failed for {account_choice}")
    st.info(f"**Technical Details:** {data_response['debug_error']}")
    st.stop()

if 'errors' in data_response:
    st.error(f"⚠️ ShipHero API Error for {account_choice}")
    st.json(data_response['errors'])
    st.stop()

# --- DATA PROCESSING ---
product_edges = data_response.get("all_edges", [])

if not product_edges:
    st.warning(f"Connected to {account_choice}, but no products were found.")
    st.stop()

# Extract all tags from the entire catalog
available_tags = sorted(list({t for e in product_edges for t in e['node'].get('tags', []) if t}))
selected_tags = st.sidebar.multiselect(
    "Select Product Tags", 
    options=available_tags,
    help="Leave empty to show all items"
)

report_list = []
for edge in product_edges:
    node = edge.get('node', {})
    node_tags = node.get('tags', [])
    
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
                    "Product Name": node.get('name', 'Unknown'),
                    "SKU": node.get('sku'),
                    "Location": l_name,
                    "Storage Type": l_type,
                    "Inv Qty": inv_qty,
                    "Daily Rate": daily_fee,
                    "Period Cost": round(total_period_cost, 2)
                }
                
                if len(selected_tags) > 1:
                    tags_present = [t for t in node_tags if t in selected_tags]
                    row["Matching Tags"] = ", ".join(tags_present)
                
                report_list.append(row)

if report_list:
    df = pd.DataFrame(report_list)
    st.title(f"📦 Storage Report: {account_choice}")
    
    c1, c2 = st.columns(2)
    c1.metric("Total Period Cost", f"${df['Period Cost'].sum():,.2f}")
    c2.metric("Days Counted", f"{num_days} Days")

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

    # Main Table
    st.dataframe(
        df, use_container_width=True, hide_index=True,
        column_config={
            "Daily Rate": st.column_config.NumberColumn(format="$%.4f"), 
            "Period Cost": st.column_config.NumberColumn(format="$%.2f")
        }
    )
    st.download_button(f"Download CSV", df.to_csv(index=False), f"{account_choice}_report.csv", "text/csv")
else:
    st.info(f"No active inventory matches your criteria for {account_choice}.")

# --- 6. FOOTER WITH REVISION ---
st.markdown(f"""
    <div class="footer">
        Vertical Passage Warehouse Operations | Revision: March 17, 2026
    </div>
    """, unsafe_allow_html=True)
