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

# --- 2. STORAGE RATE CARD ---
# Extracted from Billing Profiles
STORAGE_RATES = {
    "Standard Bin": 0.0442,
    "Blue Bin Small": 0.0488,
    "Blue Bin Medium": 0.1462,
    "Blue Bin Large": 0.2925,
    "Gray Bin Small": 0.1846,
    "Gray Bin Medium": 0.2275,
    "Gray Bin Large": 0.325,
    "Pallet": 2.093,
    "Pallet Tall": 2.7274,
    "Pallet Large": 2.652,
    "Pallet Medium Large": 1.7914,
    "Pallet Medium Small": 1.443,
    "Pallet Small Large": 0.9581,
    "Pallet Small": 0.5902,
    "Half Pallet": 1.0472,
    "Tractor Trailer Load Floor": 52.00,
    "Wall - Back": 12.116,
    "Wall - Front": 4.4096,
    "Pallite 16": 0.0537,
    "Pallite 48": 0.0357,
    "DT - Pallet": 2.2074
}

# --- 3. API DATA FETCHING ---
@st.cache_data(ttl=300)
def fetch_shiphero_data():
    # Adjusted query: 'first' is moved inside 'data' where the schema expects it
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
                locations(first: 20) {
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
            st.error(f"ShipHero API Error {response.status_code}")
            st.code(response.text)
            return None
            
        return response.json()
    except Exception as e:
        st.error(f"Connection failed: {e}")
        return None

# --- 4. APP INTERFACE ---
st.set_page_config(page_title="Storage Report", layout="wide")
st.title("📦 Storage Cost Report")

data_response = fetch_shiphero_data()

if data_response and 'data' in data_response:
    product_root = data_response.get('data', {}).get('products', {})
    product_edges = product_root.get('data', {}).get('edges', []) if product_root else []
    
    if not product_edges:
        st.warning("No products found or connection returned empty results.")
        st.stop()

    # Collect unique tags
    available_tags = set()
    for edge in product_edges:
        tags = edge.get('node', {}).get('tags', [])
        for t in tags:
            if t: available_tags.add(t)
    
    sorted_tags = sorted(list(available_tags))

    # Sidebar
    st.sidebar.header("Navigation")
    selected_tag = st.sidebar.selectbox("Filter by Product Tag", ["Show All"] + sorted_tags)

    report_list = []
    for edge in product_edges:
        node = edge.get('node', {})
        node_tags = node.get('tags', [])
        
        if selected_tag == "Show All" or selected_tag in node_tags:
            for wh_prod in node.get('warehouse_products', []):
                loc_edges = wh_prod.get('locations', {}).get('edges', [])
                for loc_edge in loc_edges:
                    l_node = loc_edge.get('node', {})
                    l_name = l_node.get('location', {}).get('name', 'Unknown')
                    l_qty = l_node.get('quantity', 0)
                    
                    # Rate Mapping
                    daily_fee = 0.0
                    for key, fee in STORAGE_RATES.items():
                        if key.lower() in l_name.lower():
                            daily_fee = fee
                            break
                    
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
        
        st.metric(f"Total Monthly Storage ({selected_tag})", f"${total_monthly:,.2f}")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv_data, "storage_report.csv", "text/csv")
    else:
        st.info(f"No inventory records for items tagged: {selected_tag}")

elif data_response and 'errors' in data_response:
    st.error("GraphQL Errors Detected:")
    st.json(data_response['errors'])
