
import requests
import json

BASE_URL = "http://localhost:8000"

def test_filters():
    # Login to get token
    login_data = {"username": "admin", "password": "password123"}
    resp = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get forms to find a valid form_id
    forms_resp = requests.get(f"{BASE_URL}/api/forms/", headers=headers)
    forms = forms_resp.json()
    if not forms:
        print("No forms found")
        return
    
    form_id = forms[0]["id"]
    print(f"Testing filters for Form ID: {form_id}")

    # Get filters
    filters_resp = requests.get(f"{BASE_URL}/api/analysis/filters?form_id={form_id}", headers=headers)
    filters = filters_resp.json()

    print("\n--- DROPDOWN OPTIONS ---")
    print(f"Scatter/Histogram (Numeric): {[f['label'] for f in filters['numeric_fields']]}")
    print(f"Line Chart (Dates): {[f['label'] for f in filters['date_fields']]}")
    print(f"Bar/Pie (Categorical): {[f['label'] for f in filters['categorical_fields']]}")

if __name__ == "__main__":
    try:
        test_filters()
    except Exception as e:
        print(f"Error: {e}")
