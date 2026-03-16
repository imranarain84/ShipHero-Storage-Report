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

# --- 2. STORAGE RATE CARD (From Billing Profile) ---
# Extracted from your provided PDF data
STORAGE_RATES = {
    "Standard Bin": 0.0442,      # [cite: 10, 15]
    "Blue Bin Small": 0.0488,    # [cite: 39]
    "Blue Bin Medium": 0.1462,   # [cite: 34]
    "Blue Bin Large": 0.2925,    # [cite: 29]
    "Gray Bin Small": 0.1846,    # [cite: 44]
    "Gray Bin Medium": 0.2275,   # [cite: 49]
    "Gray Bin Large": 0.325,     # [cite: 54]
    "Pallet": 2.093,             # [cite: 5]
    "Pallet Tall": 2.7274,       # [cite: 59]
    "Pallet Large": 2.652,       # [cite: 64]
    "Pallet Medium Large": 1.7914, # [cite: 69]
    "Pallet Medium Small": 1.443,  # [cite: 74]
    "Pallet Small Large": 0.9581,  # [cite: 79]
    "Pallet Small": 0.5902,      # [cite: 84]
    "Half Pallet": 1.0472,       # [cite: 20]
    "Tractor Trailer Load Floor": 52.00, # [cite: 24]
    "Wall - Back": 12.116,       # [cite: 89]
    "Wall - Front": 4.4096,      # [cite: 99]
    "Pallite 16": 0.0537,        # [cite: 112]
    "Pallite 48": 0.0357,        # [cite: 112]
    "DT - Pallet": 2.2074        # [cite: 104, 109]
}

# --- 3. API DATA FETCHING ---
@st.cache_data(ttl=300)
def fetch_shiphero_data():
    # This query uses the most basic structure to avoid 400 Bad Request errors
    query = """
    query {
      products(first: 100) {
        data {
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
        
        # If the API returns a 400, let's see why
        if response.status_code != 200:
            st.error(f"ShipHero API returned a {response.status_code} error.")
            st.code(response.text) # This will show the exact reason for the 400 error
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
    # Safely drilling down into the JSON
    product_data = data_response.get('data', {}).get('products', {}).get('data', {})
    product_edges = product_data.get('edges', [])
    
    if not product_edges:
        st.warning("No product data found in this account.")
        st.stop()

    # Create a unique list of tags from all returned products
    available_tags = set()
    for edge in product_edges:
        tags = edge.get('node', {}).get('tags', [])
        if tags:
            for t in tags:
                available_tags.add(t)
    
    sorted_tags = sorted(list(available_tags))

    # Sidebar Filter
    st.sidebar.header("Report Filters")
    selected_tag = st.sidebar.selectbox("Select a Product Tag", ["Show All"] + sorted_tags)

    report_list = []
    for edge in product_edges:
        node = edge.get('node', {})
        node_tags = node.get('tags', [])
        
        # Filter Logic
        if selected_tag == "Show All" or selected_tag in node_tags:
            for wh_prod in node.get('warehouse_products', []):
                loc_edges = wh_prod.get('locations', {}).get('edges', [])
                for loc_edge in loc_edges:
                    l_node = loc_edge.get('node', {})
                    l_name = l_node.get('location', {}).get('name', 'Unknown')
                    l_qty = l_node.get('quantity', 0)
                    
                    # Rate Matching Logic
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
        
        # Display Totals
        total_storage = df["Monthly Est."].sum()
        st.metric(f"Total Monthly Storage Cost ({selected_tag})", f"${total_storage:,.2f}")
        
        # Detailed Table
        st.dataframe(df, use_container_width=True)
        
        # Export Option
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Report as CSV", csv_data, "storage_report.csv", "text/csv")
    else:
        st.info(f"No active inventory found for items with the tag: {selected_tag}")

elif data_response and 'errors' in data_response:
    st.error("The GraphQL query was rejected by ShipHero:")
    st.json(data_response['errors'])
