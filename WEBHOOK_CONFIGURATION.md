# Webhook Configuration Guide - Current Setup & Production Migration

## 📌 **Important: KoboToolbox Uses REST Services**

In KoboToolbox, webhooks are configured through the **REST Services** feature, not a separate "Webhooks" menu. REST Services allow you to link your Kobo form to an external URL (your webhook endpoint), sending data in JSON format in real-time when forms are submitted.

**Key Points:**
- ✅ Configure in **Settings → REST Services** (not "Webhooks")
- ✅ Sends JSON data to your endpoint when submissions are created/updated
- ✅ Can be secured with API keys or tokens
- ✅ Manage all REST service calls in Kobo's settings

---

## 🔧 **Current Setup (Local Development with ngrok)**

### **Your Current Webhook URL:**
```
https://f0c3f65cab43.ngrok-free.app/api/webhooks/kobo
```

---


---

## 📋 **Step-by-Step: Configure REST Services in KoboToolbox**

### **Method 1: Via KoboToolbox Web Interface (REST Services)**

Complete step-by-step guide to configure REST Services in KoboToolbox:

#### **Step 1: Log in to KoboToolbox**
1. Go to: https://kf.kobotoolbox.org
2. Log in with your credentials

#### **Step 2: Navigate to Your Form**
1. From the dashboard, click on your form: **"MEAL System Master Form"**
   - Or go directly to: https://kf.kobotoolbox.org/#/forms/arsYddWQmG4Hn2D8XMEdJw
2. You should see your form details page

#### **Step 3: Access REST Services Settings**
1. Click on the **"Settings"** tab (usually at the top or side menu)
   - Look for a gear icon ⚙️ or "Settings" button
2. In the Settings page, scroll down or look for **"REST Services"** section
   - It may be labeled as:
     - **"REST Services"**
     - **"REST API"**
     - **"External Services"**
     - **"Integrations"** → then **"REST Services"**
3. Click on **"REST Services"** to open the REST Services configuration page

#### **Step 4: Add/Create REST Service**
1. Click the **"Add REST Service"** or **"Create REST Service"** or **"New REST Service"** button
2. A form/dialog will appear to configure the REST service

#### **Step 5: Configure REST Service Details**
Fill in the REST Service configuration form with these exact values:

1. **Name**:
   - Enter: `MEAL System - Local Dev`
   - This is a label for your reference

2. **Endpoint URL**:
   - The field has a fixed `https://` prefix
   - Enter only: `f0c3f65cab43.ngrok-free.app/api/webhooks/kobo`
   - Full URL will be: `https://f0c3f65cab43.ngrok-free.app/api/webhooks/kobo`
   - This is where Kobo will send the JSON data when forms are submitted

3. **Enabled**:
   - ✅ **Check this box** to activate the REST service
   - The service won't work if this is unchecked

4. **Receive emails notifications** (Optional):
   - Check this if you want email notifications when the REST service is triggered
   - For local testing, you can leave this unchecked

5. **Type**:
   - Select: **`JSON`** (radio button)
   - This ensures data is sent in JSON format that your API expects
   - Do NOT select XML

6. **Security** (Optional):
   - Click the dropdown and select a security option if needed
   - For local testing, you can leave this as "Select..." (no security)
   - Options may include: API Key, Token, Basic Auth, etc.

7. **Select fields subset** (Optional):
   - Leave empty to send all fields
   - Or enter specific field names if you only want to send certain fields
   - For full data sync, leave this empty

8. **Custom HTTP Headers** (Optional):
   - If you need to add authentication headers, click **"+ Add header"**
   - For example:
     - Name: `Authorization`
     - Value: `Bearer YOUR_TOKEN`
   - For local testing without authentication, you can skip this

9. **Add custom wrapper around JSON submission** (Optional):
   - Leave empty for standard JSON format
   - Only use if you need a custom wrapper (advanced use case)
   - The `%SUBMISSION%` placeholder will be replaced by the JSON data

#### **Step 6: Save the REST Service**
1. Click the blue **"Create"** button at the bottom right of the modal
2. The modal will close and the REST service should now appear in your REST Services list
3. Status should show as **"Enabled"** (if the Enabled checkbox was checked)

#### **Step 7: Verify REST Service**
1. The REST service should appear in the list with:
   - Name: `MEAL System - Local Dev`
   - URL: Your ngrok URL
   - Status: Active/Enabled
2. You can test it by submitting a test form in KoboToolbox
3. Check ngrok web interface (http://127.0.0.1:4040) to see the request

---

### **Visual Guide - REST Service Modal Fields**

Based on the actual KoboToolbox interface, here's what the "New REST Service" modal looks like:

```
┌─────────────────────────────────────────┐
│ New REST Service                    [X] │
├─────────────────────────────────────────┤
│ Name:                                    │
│ [Service Name                    ]      │
│                                         │
│ Endpoint URL:                            │
│ [https://][f0c3f65cab43.ngrok-free...] │
│                                         │
│ ☑ Enabled                                │
│ ☑ Receive emails notifications          │
│                                         │
│ Type:                                    │
│ ⦿ JSON  ○ XML                            │
│                                         │
│ Security:                                │
│ [Select...                    ▼]        │
│                                         │
│ Select fields subset:                   │
│ [Add field(s)                   ]      │
│                                         │
│ Custom HTTP Headers:                    │
│ [Name] [Value] [🗑]                     │
│ [+ Add header]                          │
│                                         │
│ Add custom wrapper around JSON          │
│ submission (%SUBMISSION% will be        │
│ replaced by JSON):                       │
│ [Add Custom Wrapper             ]      │
│                                         │
│                              [Create]   │
└─────────────────────────────────────────┘
```

**Key Points:**
- The **Endpoint URL** field has a fixed `https://` prefix - you only enter the domain and path
- **Type** uses radio buttons (JSON/XML), not a dropdown
- **Enabled** checkbox must be checked for the service to work
- Click **"Create"** button at the bottom to save

---

### **Alternative: If REST Services is Not Visible**

If you don't see "REST Services" in Settings:

1. **Check Project Level**: REST Services might be at the project level, not form level
   - Go to your project → Settings → REST Services

2. **Check Permissions**: You may need admin/owner permissions
   - Contact your Kobo account administrator

3. **Check Kobo Version**: Some older versions may have different locations
   - Look for "External Services" or "API Integrations"

4. **Use API Method**: If web interface doesn't work, use the API method below

---

### **Method 2: Via KoboToolbox API (REST Services)**

If you prefer to configure via API or if the web interface doesn't work:

```python
import requests

KOBO_TOKEN = "your_kobo_api_token"  # Get from Kobo account settings
ASSET_ID = "arsYddWQmG4Hn2D8XMEdJw"  # Your form asset ID
REST_SERVICE_URL = "https://f0c3f65cab43.ngrok-free.app/api/webhooks/kobo"

headers = {
    "Authorization": f"Token {KOBO_TOKEN}",
    "Content-Type": "application/json"
}

# REST Service configuration
rest_service_data = {
    "name": "MEAL System - Local Dev",
    "service_url": REST_SERVICE_URL,
    "service_method": "POST",
    "active": True,
    "data_format": "json"
}

# Try REST Services API endpoint
try:
    response = requests.post(
        f"https://kf.kobotoolbox.org/api/v2/assets/{ASSET_ID}/rest_services/",
        headers=headers,
        json=rest_service_data
    )
    response.raise_for_status()
    print("✅ REST Service created successfully!")
    print(response.json())
except requests.exceptions.HTTPError as e:
    print(f"❌ Error: {e}")
    print(f"Response: {response.text}")
    print("\nTrying alternative endpoint...")
    
    # Alternative: Some Kobo versions use different endpoints
    try:
        response = requests.post(
            f"https://kf.kobotoolbox.org/api/v2/assets/{ASSET_ID}/hooks/",
            headers=headers,
            json={
                "url": REST_SERVICE_URL,
                "active": True,
                "name": "MEAL System - Local Dev"
            }
        )
        print("✅ REST Service created via alternative endpoint!")
        print(response.json())
    except Exception as e2:
        print(f"❌ Alternative also failed: {e2}")
```

**To get your Kobo API Token:**
1. Go to Kobo account settings
2. Navigate to API Tokens or API Keys
3. Create a new token
4. Copy the token and use it in the script above

---

## ✅ **Test the Webhook**

### **Test 1: Manual Test via cURL**

```powershell
Invoke-WebRequest -Uri "https://f0c3f65cab43.ngrok-free.app/api/webhooks/kobo" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"event_type":"submission.created","form_id":"arsYddWQmG4Hn2D8XMEdJw","data":{"form_id":"arsYddWQmG4Hn2D8XMEdJw"}}'
```

**Expected Response:**
```json
{
  "status": "success",
  "sync_log_id": 1,
  "records_added": 1
}
```

### **Test 2: Real Submission Test**

1. **Submit a test form** in KoboToolbox
2. **Check ngrok web interface**: http://127.0.0.1:4040
   - You should see the webhook request
3. **Check your app logs**:
   - Should see: `INFO: POST /api/webhooks/kobo`
   - Should see: `Webhook received: submission.created`
4. **Check your database**:
   - New submission should appear
   - Query: `GET http://localhost:8000/api/submissions`

---

## 🚀 **Migration to Production Domain**

When you're ready to deploy to production, follow these steps:

### **Step 1: Deploy Your Application**

Deploy your FastAPI app to your production server with:
- Domain: `https://mealsystem.example.com` (your actual domain)
- SSL certificate (HTTPS required)
- Port 8000 (or configure reverse proxy)

### **Step 2: Update Webhook URL in Kobo**

#### **Option A: Via Web Interface (REST Services)**

1. Go to your form → **Settings** → **REST Services**
2. Find your existing REST service (webhook)
3. Click **"Edit"** or **"Update"** or **"Configure"**
4. Change **Service URL** from:
   ```
   https://f0c3f65cab43.ngrok-free.app/api/webhooks/kobo
   ```
   To:
   ```
   https://mealsystem.example.com/api/webhooks/kobo
   ```
5. **Save** or **"Update"**

#### **Option B: Via API (Update Existing REST Service)**

```python
import requests

KOBO_TOKEN = "your_kobo_api_token"
ASSET_ID = "arsYddWQmG4Hn2D8XMEdJw"
REST_SERVICE_ID = "your_rest_service_id"  # Get from listing REST services
NEW_WEBHOOK_URL = "https://mealsystem.example.com/api/webhooks/kobo"

headers = {
    "Authorization": f"Token {KOBO_TOKEN}",
    "Content-Type": "application/json"
}

# Get existing REST service
response = requests.get(
    f"https://kf.kobotoolbox.org/api/v2/assets/{ASSET_ID}/rest_services/{REST_SERVICE_ID}/",
    headers=headers
)
rest_service_data = response.json()

# Update Service URL
rest_service_data["service_url"] = NEW_WEBHOOK_URL

# Update REST service
response = requests.patch(
    f"https://kf.kobotoolbox.org/api/v2/assets/{ASSET_ID}/rest_services/{REST_SERVICE_ID}/",
    headers=headers,
    json=rest_service_data
)

print(response.json())
```

#### **Option C: Create New REST Service (Keep Both)**

You can also create a new REST service for production and keep the local one for testing:

1. Go to **Settings** → **REST Services**
2. Click **"Add REST Service"** or **"Create REST Service"**
3. Add a new REST service with production URL
4. Keep the ngrok REST service active for local development
5. Both will work simultaneously - Kobo will send data to all active REST services

---

## 📝 **Webhook URL Reference**

### **Current (Local Development)**
```
https://f0c3f65cab43.ngrok-free.app/api/webhooks/kobo
```
- **Use for**: Local development and testing
- **Note**: URL changes when you restart ngrok (free plan)

### **Production (When Deployed)**
```
https://mealsystem.example.com/api/webhooks/kobo
```
- **Use for**: Production environment
- **Note**: Replace `mealsystem.example.com` with your actual domain

---

## 🔄 **Managing Multiple Environments**

You can have multiple REST Services for different environments:

1. **Local Dev**: `https://ngrok-url.ngrok.io/api/webhooks/kobo`
2. **Staging**: `https://staging.mealsystem.com/api/webhooks/kobo`
3. **Production**: `https://mealsystem.example.com/api/webhooks/kobo`

Kobo will send data to all active REST Services, so you can test in multiple environments simultaneously.

---

## ⚙️ **Environment-Specific Configuration**

### **Create Environment Variables**

In your `.env` file:

```env
# Local Development
WEBHOOK_BASE_URL=https://f0c3f65cab43.ngrok-free.app

# Production (update when deploying)
# WEBHOOK_BASE_URL=https://mealsystem.example.com
```

### **Update Webhook URL Script**

Create a script to update webhook URL based on environment:

```python
# scripts/update_webhook_url.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

KOBO_TOKEN = os.getenv("KOBO_API_TOKEN")
ASSET_ID = os.getenv("KOBO_FORM_ID", "arsYddWQmG4Hn2D8XMEdJw")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")

if not WEBHOOK_BASE_URL:
    print("Error: WEBHOOK_BASE_URL not set in .env")
    exit(1)

WEBHOOK_URL = f"{WEBHOOK_BASE_URL}/api/webhooks/kobo"

headers = {
    "Authorization": f"Token {KOBO_TOKEN}",
    "Content-Type": "application/json"
}

# List existing webhooks
response = requests.get(
    f"https://kf.kobotoolbox.org/api/v2/assets/{ASSET_ID}/hooks/",
    headers=headers
)

webhooks = response.json()
print(f"Found {len(webhooks)} webhooks")

# Update or create webhook
# ... (implementation)
```

---

## ✅ **Verification Checklist**

### **Current Setup (Local)**
- [ ] ngrok is running and accessible
- [ ] FastAPI app is running on port 8000
- [ ] REST Service configured in Kobo with ngrok URL (Settings → REST Services)
- [ ] REST Service shows as "Active" or "Enabled" in Kobo
- [ ] HTTP Method is set to `POST`
- [ ] "On form submission" trigger is enabled
- [ ] Test submission triggers REST service
- [ ] Data appears in your database

### **Production Setup (When Ready)**
- [ ] Application deployed to production domain
- [ ] SSL certificate installed (HTTPS working)
- [ ] REST Service URL updated in Kobo (Settings → REST Services → Edit)
- [ ] Test REST service from production
- [ ] Monitor REST service delivery
- [ ] Set up error alerts
- [ ] Disable or remove ngrok REST service

---

## 🐛 **Troubleshooting**

### **REST Service Not Receiving Requests**

1. **Check ngrok is running**: http://127.0.0.1:4040
2. **Check REST service is active/enabled** in Kobo settings → REST Services
3. **Verify Service URL is correct** (no typos, includes `/api/webhooks/kobo`)
4. **Check HTTP Method** is set to `POST`
5. **Verify "On form submission"** is enabled/checked
6. **Check ngrok web interface** for incoming requests (http://127.0.0.1:4040)
7. **Verify FastAPI app is running** on port 8000
8. **Check if authentication is required** - if you set API key/token, make sure it matches

### **Webhook Returns Error**

1. **Check application logs** for error details
2. **Verify database connection**
3. **Check Kobo API credentials** in `.env`
4. **Test endpoint manually** with curl

### **Switching to Production**

1. **Test production URL** before updating REST service
2. **Keep ngrok REST service** for local testing (or disable it)
3. **Monitor both** during transition
4. **Update REST Service URL** in Kobo (Settings → REST Services → Edit)
5. **Test with real submission** to verify production webhook works
6. **Disable ngrok REST service** once production is confirmed working

---

## 📊 **Monitoring**

### **Local Development**
- **ngrok Web Interface**: http://127.0.0.1:4040
- **Application Logs**: Terminal where uvicorn runs
- **Database**: Check via API or SQLite

### **Production**
- **Application Logs**: Server logs
- **Webhook Delivery**: Kobo webhook logs (if available)
- **Database**: Monitor submission count
- **Error Tracking**: Set up alerts

---

## 🔐 **Security Notes**

1. **HTTPS Required**: Kobo requires HTTPS (ngrok provides this)
2. **Webhook Secret**: Consider adding secret verification (future enhancement)
3. **Rate Limiting**: Monitor webhook frequency
4. **IP Whitelisting**: Optional - whitelist Kobo IPs if known

---

**Last Updated**: 2025-12-23  
**Current Webhook URL**: `https://f0c3f65cab43.ngrok-free.app/api/webhooks/kobo`

