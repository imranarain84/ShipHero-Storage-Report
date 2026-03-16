import streamlit as st
import pandas as pd
import requests

# --- 1. CONFIGURATION & SECRETS ---
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"

if "SHIPHERO_TOKEN" not in st.secrets:
    st.error("❌ 'SHIPHERO_TOKEN' not found in Streamlit Secrets.")
    st.stop()

token = st.secrets["SHIPHERO_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# --- 2. STORAGE RATE CARD (Refined Keywords) ---
# We use shorter keywords to increase the chance of a match
STORAGE_RATES = {
    "standard bin": 0.0442,
    "blue bin small": 0.0488,
    "blue bin medium": 0.1462,
    "blue bin large": 0.2925,
    "gray bin small": 0.1846,
    "gray bin medium": 0.2275,
    "gray bin large": 0.325,
    "pallet tall": 2.7274,
    "pallet large": 2.652,
    "pallet medium large": 1.7914,
    "pallet medium small": 1.443,
    "pallet small large": 0.9581,
    "pallet small": 0.5902,
    "pallet": 2.093,             # Generic 'pallet' must come after specific sizes
    "half pallet": 1.0472,
    "tractor trailer": 52.00,
    "wall - back": 12.116,
    "wall - front": 4.4096,
    "pallite 16": 0.0537,
    "pallite 48": 0.0357,
    "dt-pallet": 2.2074
}

# --- 3. API DATA FETCHING ---
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
        response = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS)
        if response.status_code != 200:
            return None
        return response.json()
    except:
        return None

# --- 4. APP INTERFACE ---
st.set_page_config(page_title="Storage Cost Report", layout="wide")
st.title("📦 Storage Cost Report")

data_response = fetch_shiphero_data()

if data_response and 'data' in data_response:
    product_root = data_response.get('data', {}).get('products', {})
    product_edges = product_root.get('data', {}).get('edges', []) if product_root else []
    
    if not product_edges:
        st.warning("No products found in the ShipHero account.")
        st.stop()

    # Tag & Location Audit
    available_tags = set()
    all_location_names = set()
    
    for edge in product_edges:
        node = edge.get('node', {})
        for t in node.get('tags', []):
            if t: available_tags.add(t)
        for wh_prod in node.get('warehouse_products', []):
            for loc_edge in wh_prod.get('locations', {}).get('edges', []):
                all_location_names.add(loc_edge['node']['location']['name'])
    
    # Sidebar
    st.sidebar.header("Filters")
    selected_tag = st.sidebar.selectbox("Select Product Tag", ["Show All"] + sorted(list(available_tags)))

    report_list = []
    unmatched_locations = set()

    for edge in product_edges:
        node = edge.get('node', {})
        node_tags = node.get('tags', [])
        
        if selected_tag == "Show All" or selected_tag in node_tags:
            for wh_prod in node.get('warehouse_products', []):
                for loc_edge in wh_prod.get('locations', {}).get('edges', []):
                    l_name = loc_edge['node']['location']['name']
                    l_qty = loc_edge['node']['quantity']
                    
                    # Match Logic
                    daily_fee = 0.0
                    matched = False
                    for key, fee in STORAGE_RATES.items():
                        if key.lower() in l_name.lower():
                            daily_fee = fee
                            matched = True
                            break
                    
                    if not matched:
                        unmatched_locations.add(l_name)

                    report_list.append({
                        "SKU": node.get('sku'),
                        "Location": l_name,
                        "Quantity": l_qty,
                        "Daily Rate": daily_fee,
                        "Monthly Est.": round(daily_fee * 30, 2)
                    })

    if report_list:
        df = pd.DataFrame(report_list)
        total_monthly = df["Monthly Est."].sum()
        
        # Display Totals
        col1, col2 = st.columns(2)
        col1.metric("Total Monthly Cost", f"${total_monthly:,.2f}")
        col2.metric("Items Found", len(df))
        
        st.write(f"### Results for Tag: `{selected_tag}`")
        st.dataframe(df, use_container_width=True)

        # DEBUG SECTION: If total is 0, help the user see why
        if total_monthly == 0 and not df.empty:
            st.error("⚠️ The total cost is $0.00 because your ShipHero location names don't match our 'Rate Keywords'.")
            with st.expander("🔍 See Unmatched Location Names"):
                st.write("The app found these locations, but doesn't know what to charge for them. Please tell us which ones are Bins or Pallets:")
                st.write(list(unmatched_locations))
        
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv_data, "storage_report.csv", "text/csv")
    else:
        st.info(f"No active inventory found for items tagged: {selected_tag}")

else:
    st.error("No data received from API. Please check your token.")
