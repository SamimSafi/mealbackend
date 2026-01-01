# KoboToolbox Webhook Configuration Guide

This guide explains how to configure webhooks in KoboToolbox to enable real-time updates in your application.

---

## 📋 **Prerequisites**

1. Your application must be accessible via HTTPS (Kobo requires HTTPS for webhooks)
2. Your application must be running and accessible from the internet
3. You need admin access to your KoboToolbox account

---

## 🔧 **Step-by-Step Configuration**

### **Step 1: Get Your Webhook URL**

Your webhook endpoint is:
```
https://your-domain.com/api/webhooks/kobo
```

**For local development/testing**, you can use a tunnel service like:
- **ngrok**: `https://your-ngrok-url.ngrok.io/api/webhooks/kobo`
- **localtunnel**: `https://your-tunnel-url.loca.lt/api/webhooks/kobo`
- **Cloudflare Tunnel**: `https://your-tunnel-url.trycloudflare.com/api/webhooks/kobo`

**Example URLs:**
- Production: `https://mealsystem.example.com/api/webhooks/kobo`
- Development (ngrok): `https://abc123.ngrok.io/api/webhooks/kobo`

---

### **Step 2: Configure Webhook in KoboToolbox**

#### **Option A: Via KoboToolbox Web Interface**

1. **Log in** to your KoboToolbox account
2. **Navigate to your form** (the form you want to sync)
3. **Go to Settings** → **Webhooks** (or **Integrations** → **Webhooks`)
4. **Click "Add Webhook"** or **"Create Webhook"**
5. **Fill in the webhook details:**
   - **Name**: `MEAL System Sync` (or any descriptive name)
   - **URL**: `https://your-domain.com/api/webhooks/kobo`
   - **Method**: `POST`
   - **Events**: Select the following:
     - ✅ `submission.created` - When a new submission is created
     - ✅ `submission.updated` - When a submission is updated
   - **Active**: ✅ Check this box
6. **Click "Save"** or **"Create"**

#### **Option B: Via KoboToolbox API**

You can also configure webhooks programmatically using the Kobo API:

```python
import requests

KOBO_TOKEN = "your_kobo_api_token"
ASSET_ID = "your_form_asset_id"  # e.g., "arsYddWQmG4Hn2D8XMEdJw"
WEBHOOK_URL = "https://your-domain.com/api/webhooks/kobo"

headers = {
    "Authorization": f"Token {KOBO_TOKEN}",
    "Content-Type": "application/json"
}

webhook_data = {
    "name": "MEAL System Sync",
    "url": WEBHOOK_URL,
    "active": True,
    "events": ["submission.created", "submission.updated"]
}

response = requests.post(
    f"https://kf.kobotoolbox.org/api/v2/assets/{ASSET_ID}/hooks/",
    headers=headers,
    json=webhook_data
)

print(response.json())
```

---

### **Step 3: Test the Webhook**

#### **Test 1: Manual Test**

Create a test submission in your Kobo form and check:
1. Your application logs for webhook requests
2. Your database for new submissions
3. Your dashboard for updated data

#### **Test 2: Using cURL**

Test the webhook endpoint directly:

```bash
curl -X POST https://your-domain.com/api/webhooks/kobo \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "submission.created",
    "form_id": "arsYddWQmG4Hn2D8XMEdJw",
    "submission_id": "123456",
    "data": {
      "form_id": "arsYddWQmG4Hn2D8XMEdJw"
    }
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "sync_log_id": 1,
  "records_added": 1
}
```

---

## 📡 **Webhook Payload Structure**

Your application expects the following payload format:

```json
{
  "event_type": "submission.created",  // or "submission.updated"
  "form_id": "arsYddWQmG4Hn2D8XMEdJw",  // Kobo form asset ID
  "submission_id": "123456",             // Optional: submission ID
  "data": {                              // Optional: additional data
    "form_id": "arsYddWQmG4Hn2D8XMEdJw"
  }
}
```

**Note**: The webhook endpoint will automatically:
1. Extract the `form_id` from the payload
2. Trigger an incremental sync for that form
3. Process and store the new/updated submission
4. Update indicators

---

## 🔒 **Security Considerations**

### **1. HTTPS Required**
- KoboToolbox requires HTTPS for webhook URLs
- Use a valid SSL certificate
- For local development, use ngrok or similar tunnel service

### **2. Webhook Secret (Optional)**
You can add webhook secret verification in your `.env`:

```env
WEBHOOK_SECRET=your-secret-key-here
```

Then verify it in your webhook endpoint (you may need to add this to the code).

### **3. IP Whitelisting (Optional)**
If you know Kobo's IP ranges, you can whitelist them in your firewall/load balancer.

---

## 🐛 **Troubleshooting**

### **Issue 1: Webhook Not Receiving Requests**

**Check:**
1. ✅ Webhook URL is accessible (test with curl)
2. ✅ Webhook is active in Kobo settings
3. ✅ Correct events are selected
4. ✅ URL uses HTTPS (not HTTP)
5. ✅ Check Kobo webhook logs (if available)

**Solution:**
- Verify the webhook URL is correct
- Check your server logs for incoming requests
- Test the endpoint manually with curl

### **Issue 2: Webhook Returns 500 Error**

**Check:**
1. ✅ Application logs for error details
2. ✅ Database connection is working
3. ✅ Kobo API credentials are valid
4. ✅ Form exists in your database

**Solution:**
- Check application logs: `tail -f logs/app.log`
- Verify database connection
- Test Kobo API credentials

### **Issue 3: Webhook Receives Requests But No Data**

**Check:**
1. ✅ `form_id` is present in payload
- ✅ Form exists in your database
- ✅ ETL pipeline is working

**Solution:**
- Check webhook payload structure
- Verify form is synced in your database
- Check ETL logs

---

## 📊 **Monitoring Webhooks**

### **Check Webhook Status in Kobo**

1. Go to your form → Settings → Webhooks
2. Check webhook status (Active/Inactive)
3. View webhook delivery logs (if available)

### **Monitor in Your Application**

Check your application logs for webhook activity:

```bash
# View recent webhook requests
grep "webhook" logs/app.log | tail -20

# Check for errors
grep "Webhook processing error" logs/app.log
```

### **Database Monitoring**

Check sync logs:
```sql
SELECT * FROM sync_logs 
WHERE sync_type = 'incremental' 
ORDER BY started_at DESC 
LIMIT 10;
```

---

## 🚀 **Production Setup**

### **1. Use a Production Domain**
- Set up a proper domain with SSL certificate
- Use a reverse proxy (nginx/Apache) if needed
- Configure firewall rules

### **2. Set Up Monitoring**
- Monitor webhook endpoint health
- Set up alerts for failed webhooks
- Track webhook delivery success rate

### **3. Rate Limiting**
- Consider rate limiting to prevent abuse
- Monitor webhook frequency
- Handle burst traffic appropriately

---

## 📝 **Example: Using ngrok for Local Development**

### **Step 1: Install ngrok**
```bash
# Download from https://ngrok.com/download
# Or use package manager
brew install ngrok  # macOS
choco install ngrok  # Windows
```

### **Step 2: Start Your Application**
```bash
cd mealbackend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### **Step 3: Start ngrok Tunnel**
```bash
ngrok http 8000
```

### **Step 4: Get Your ngrok URL**
ngrok will display:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

### **Step 5: Configure Webhook in Kobo**
Use the ngrok URL:
```
https://abc123.ngrok.io/api/webhooks/kobo
```

**Note**: Free ngrok URLs change on restart. For stable testing, use ngrok's paid plan or set up a permanent domain.

---

## ✅ **Verification Checklist**

- [ ] Webhook URL is accessible via HTTPS
- [ ] Webhook is configured in Kobo with correct events
- [ ] Webhook is active in Kobo settings
- [ ] Test submission triggers webhook
- [ ] Application receives webhook requests
- [ ] Submissions are synced to database
- [ ] Dashboard updates with new data
- [ ] Webhook errors are logged and monitored

---

## 🔗 **Useful Links**

- [KoboToolbox API Documentation](https://support.kobotoolbox.org/api.html)
- [KoboToolbox Webhooks Documentation](https://support.kobotoolbox.org/webhooks.html)
- [ngrok Documentation](https://ngrok.com/docs)

---

## 📞 **Support**

If you encounter issues:
1. Check application logs
2. Verify webhook configuration in Kobo
3. Test webhook endpoint manually
4. Check database for synced submissions

---

**Last Updated**: 2025-12-23

