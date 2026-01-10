"""Test all API endpoints and collect responses."""
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
TOKEN = None

def login() -> str:
    """Login and get JWT token."""
    global TOKEN
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if response.status_code == 200:
            TOKEN = response.json()["access_token"]
            print("[SUCCESS] Login successful")
            return TOKEN
        else:
            print(f"[FAILED] Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"[ERROR] Login error: {e}")
        return None

def get_headers() -> Dict[str, str]:
    """Get headers with authentication."""
    if not TOKEN:
        login()
    return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

def test_endpoint(method: str, endpoint: str, data: Any = None, description: str = "") -> Dict[str, Any]:
    """Test an API endpoint."""
    url = f"{BASE_URL}{endpoint}"
    headers = get_headers()
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=data if isinstance(data, dict) else None)
        elif method.upper() == "POST":
            headers["Content-Type"] = "application/json"
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == "PUT":
            headers["Content-Type"] = "application/json"
            response = requests.put(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        result = {
            "method": method,
            "endpoint": endpoint,
            "description": description,
            "status_code": response.status_code,
            "success": 200 <= response.status_code < 300,
        }
        
        try:
            result["response"] = response.json()
            # Truncate large responses for readability
            if isinstance(result["response"], list) and len(result["response"]) > 5:
                result["response"] = result["response"][:5] + [f"... ({len(result['response']) - 5} more items)"]
            elif isinstance(result["response"], dict):
                # Limit response size
                result["response"] = {k: v for i, (k, v) in enumerate(result["response"].items()) if i < 10}
        except:
            result["response"] = response.text[:500] if response.text else "No content"
        
        return result
    except Exception as e:
        return {
            "method": method,
            "endpoint": endpoint,
            "description": description,
            "status_code": 0,
            "success": False,
            "error": str(e)
        }

def main():
    """Test all API endpoints."""
    print("=" * 80)
    print("API TESTING SUITE")
    print("=" * 80)
    print()
    
    # Login first
    if not login():
        print("Cannot proceed without authentication")
        return
    
    results = []
    
    # Authentication endpoints
    print("\n" + "=" * 80)
    print("AUTHENTICATION ENDPOINTS")
    print("=" * 80)
    
    results.append(test_endpoint("GET", "/api/auth/me", description="Get current user"))
    
    # Forms endpoints
    print("\n" + "=" * 80)
    print("FORMS ENDPOINTS")
    print("=" * 80)
    
    results.append(test_endpoint("GET", "/api/forms", description="List all forms"))
    
    # Get first form ID if available
    forms_response = test_endpoint("GET", "/api/forms")
    form_id = None
    if forms_response.get("success") and forms_response.get("response"):
        if isinstance(forms_response["response"], list) and len(forms_response["response"]) > 0:
            form_id = forms_response["response"][0].get("id")
        elif isinstance(forms_response["response"], dict) and "id" in forms_response["response"]:
            form_id = forms_response["response"]["id"]
    
    if form_id:
        results.append(test_endpoint("GET", f"/api/forms/{form_id}", description=f"Get form {form_id} details"))
        results.append(test_endpoint("GET", f"/api/forms/{form_id}/schema", description=f"Get form {form_id} schema"))
        results.append(test_endpoint("GET", f"/api/forms/{form_id}/filter-fields", description=f"Get form {form_id} filter fields"))
        results.append(test_endpoint("GET", f"/api/forms/{form_id}/debug-schema?field_name=info/province", description=f"Debug form {form_id} schema"))
        results.append(test_endpoint("GET", f"/api/forms/{form_id}/indicators", description=f"Get form {form_id} indicators"))
    
    # Submissions endpoints
    print("\n" + "=" * 80)
    print("SUBMISSIONS ENDPOINTS")
    print("=" * 80)
    
    results.append(test_endpoint("GET", "/api/submissions", description="List all submissions"))
    if form_id:
        results.append(test_endpoint("GET", "/api/submissions", data={"form_id": form_id}, description=f"List submissions for form {form_id}"))
        results.append(test_endpoint("GET", f"/form/{form_id}/submissions", description=f"Get form {form_id} submissions (public)"))
    
    # Chart Data endpoints
    print("\n" + "=" * 80)
    print("CHART DATA ENDPOINTS")
    print("=" * 80)
    
    if form_id:
        # Test chart-data endpoint
        chart_data = {
            "chart_type": "donut",
            "dimension": "info/province",
            "filters": {
                "info/province": []
            }
        }
        results.append(test_endpoint("POST", f"/api/forms/{form_id}/chart-data", data=chart_data, description=f"Get donut chart for form {form_id}"))
        
        # Test bar chart endpoint
        bar_chart_data = {
            "form_id": form_id,
            "filters": {
                "info/province": []
            }
        }
        results.append(test_endpoint("POST", "/api/charts/bar_chart", data=bar_chart_data, description="Get bar chart with labels"))
        
        # Test box plot endpoint
        box_plot_data = {
            "form_id": form_id,
            "column": "hh_size",
            "filters": {}
        }
        results.append(test_endpoint("POST", "/api/charts/box_plot", data=box_plot_data, description="Get box plot statistics"))
    
    # Indicators endpoints
    print("\n" + "=" * 80)
    print("INDICATORS ENDPOINTS")
    print("=" * 80)
    
    results.append(test_endpoint("GET", "/api/indicators", description="List all indicators"))
    if form_id:
        results.append(test_endpoint("GET", "/api/indicators", data={"form_id": form_id}, description=f"List indicators for form {form_id}"))
        results.append(test_endpoint("GET", f"/form/{form_id}/indicators", description=f"Get form {form_id} indicators (public)"))
    
    # Dashboard endpoints
    print("\n" + "=" * 80)
    print("DASHBOARD ENDPOINTS")
    print("=" * 80)
    
    results.append(test_endpoint("GET", "/api/dashboard/summary", description="Get dashboard summary"))
    results.append(test_endpoint("GET", "/api/dashboard/indicators", description="Get indicator dashboard"))
    results.append(test_endpoint("GET", "/api/dashboard/accountability", description="Get accountability dashboard"))
    
    # Data loading endpoint
    print("\n" + "=" * 80)
    print("DATA LOADING ENDPOINTS")
    print("=" * 80)
    
    results.append(test_endpoint("GET", "/api/data/load", data={"date": "2024-01-01"}, description="Load data by date"))
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    total = len(results)
    successful = sum(1 for r in results if r.get("success"))
    failed = total - successful
    
    print(f"\nTotal endpoints tested: {total}")
    print(f"[SUCCESS] Successful: {successful}")
    print(f"[FAILED] Failed: {failed}")
    print()
    
    # Print detailed results
    print("=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    
    for i, result in enumerate(results, 1):
        status_icon = "[OK]" if result.get("success") else "[FAIL]"
        print(f"\n{i}. {status_icon} {result.get('method', 'N/A')} {result.get('endpoint', 'N/A')}")
        print(f"   Description: {result.get('description', 'N/A')}")
        print(f"   Status Code: {result.get('status_code', 'N/A')}")
        
        if result.get("error"):
            print(f"   Error: {result.get('error')}")
        elif result.get("response"):
            response = result["response"]
            if isinstance(response, dict):
                # Show key information
                if "form_id" in response:
                    print(f"   Form ID: {response.get('form_id')}")
                if "total" in response:
                    print(f"   Total: {response.get('total')}")
                if "data" in response:
                    data = response.get("data", [])
                    print(f"   Data items: {len(data) if isinstance(data, list) else 'N/A'}")
                if "items" in response:
                    items = response.get("items", [])
                    print(f"   Items: {len(items) if isinstance(items, list) else 'N/A'}")
                if "submission_count" in response:
                    print(f"   Submission count: {response.get('submission_count')}")
            
            # Show truncated response
            response_str = json.dumps(response, indent=2)
            if len(response_str) > 500:
                response_str = response_str[:500] + "\n... (truncated)"
            print(f"   Response: {response_str}")
    
    # Save results to file
    output_file = "api_test_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n[INFO] Full results saved to: {output_file}")

if __name__ == "__main__":
    main()

