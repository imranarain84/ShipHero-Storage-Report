import streamlit as st
import pandas as pd
import requests

# 1. Access the API Key from Streamlit Cloud Settings
SHIPHERO_API_URL = "https://public-api.shiphero.com/graphql"

if "SHIPHERO_TOKEN" not in st.secrets:
    st.error("❌ 'SHIPHERO_TOKEN' not found in Streamlit Secrets. Please check your dashboard settings.")
    st.stop()

token = st.secrets["SHIPHERO_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

st.title("🛠️ Debug Mode: ShipHero API")

# 2. ShipHero API Call with Debugging Enabled
def fetch_debug_data():
    # Simplest possible query to test connection
    query = """
    query {
      products(tags: ["backmarket"]) {
        data(first: 10) {
          edges {
            node {
              sku
              tags
              warehouse_products {
                locations(first: 5) {
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
        r = requests.post(SHIPHERO_API_URL, json={'query': query}, headers=HEADERS)
        
        # DISPLAY RAW RESPONSE FOR DEBUGGING
        st.subheader("Raw API Response")
        if r.status_code != 200:
            st.error(f"HTTP Error: {r.status_code}")
            st.write(r.text)
        else:
            response_json = r.json()
            st.json(response_json) # This shows you the actual JSON or the Error list
            return response_json
            
    except Exception as e:
        st.error(f"Python Exception: {e}")
        return None

# 3. Execution
raw_data = fetch_debug_data()

if raw_data and 'data' in raw_data:
    products = raw_data['data']['products']['data']['edges']
    if not products:
        st.warning("⚠️ Connection successful, but NO products were found with the tag 'backmarket'.")
        st.info("Check if the tag is spelled exactly like that in ShipHero (it is case-sensitive).")
    else:
        st.success(f"✅ Success! Found {len(products)} products.")
