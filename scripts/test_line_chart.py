
import requests
import json

BASE_URL = "http://localhost:8000"

def test_line_chart():
    # Login
    login_data = {"username": "testadmin", "password": "testpassword123"}
    resp = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get first form
    forms = requests.get(f"{BASE_URL}/api/forms/", headers=headers).json()
    if not forms:
        print("No forms found")
        return
    
    form_id = forms[0]["id"]
    
    # Get filters to find a date field
    filters = requests.get(f"{BASE_URL}/api/analysis/filters?form_id={form_id}", headers=headers).json()
    
    date_fields = filters.get("date_fields", [])
    if not date_fields:
        # Fallback to common Kobo metadata if no explicit date fields in schema
        time_dim = "_submission_time"
    else:
        time_dim = date_fields[0]["name"]

    print(f"Testing Line Chart for Form {form_id} using time_dimension: {time_dim}")

    # Request Line Chart
    payload = {
        "chart_type": "line",
        "dimension": "status", # Just a placeholder
        "time_dimension": time_dim,
        "filters": {}
    }
    
    chart_resp = requests.post(f"{BASE_URL}/api/forms/{form_id}/chart-data", headers=headers, json=payload)
    
    print("\n--- LINE CHART RESPONSE (JSON) ---")
    print(json.dumps(chart_resp.json(), indent=2))

if __name__ == "__main__":
    try:
        test_line_chart()
    except Exception as e:
        print(f"Error: {e}")
