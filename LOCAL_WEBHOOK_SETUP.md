# Local Development: Real-Time Kobo Webhooks Setup

This guide shows you how to receive real-time webhooks from KoboToolbox while running your app locally.

---

## 🚀 **Quick Setup (3 Steps)**

### **Step 1: Start Your Application**

```bash
cd mealbackend
uvicorn main:app --host 0.0.0.0 --port 8000
```

Your app should be running at `http://localhost:8000`

---

### **Step 2: Set Up ngrok Tunnel**

#### **Option A: Using ngrok (Recommended)**

1. **Download ngrok**: https://ngrok.com/download
   - Or install via package manager:
     ```bash
     # Windows (chocolatey)
     choco install ngrok
     
     # macOS (homebrew)
     brew install ngrok
     
     # Linux
     wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip
     ```

2. **Sign up for free ngrok account** (optional but recommended):
   - Go to https://dashboard.ngrok.com/signup
   - Get your authtoken

3. **Configure ngrok**:
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN
   ```

4. **Start ngrok tunnel**:
   ```bash
   ngrok http 8000
   ```

5. **Copy your ngrok URL**:
   ```
   Forwarding  https://abc123.ngrok.io -> http://localhost:8000
   ```
   Your webhook URL will be: `https://abc123.ngrok.io/api/webhooks/kobo`

#### **Option B: Using Cloudflare Tunnel (Free, No Signup)**

1. **Install cloudflared**:
   ```bash
   # Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
   ```

2. **Start tunnel**:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```

3. **Copy the URL** shown (e.g., `https://abc123.trycloudflare.com`)

#### **Option C: Using localtunnel (No Signup Required)**

1. **Install localtunnel**:
   ```bash
   npm install -g localtunnel
   ```

2. **Start tunnel**:
   ```bash
   lt --port 8000
   ```

3. **Copy the URL** shown (e.g., `https://abc123.loca.lt`)

---

### **Step 3: Configure Webhook in KoboToolbox**

1. **Go to your Kobo form** → **Settings** → **Webhooks**
2. **Click "Add Webhook"**
3. **Enter details**:
   - **Name**: `MEAL System Local Dev`
   - **URL**: `https://your-ngrok-url.ngrok.io/api/webhooks/kobo`
     - Replace `your-ngrok-url` with your actual ngrok URL
   - **Method**: `POST`
   - **Events**: 
     - ✅ `submission.created`
     - ✅ `submission.updated`
   - **Active**: ✅ Yes
4. **Click "Save"**

---

## ✅ **Test the Setup**

### **Test 1: Verify Webhook Endpoint**

Test your webhook endpoint directly:

```bash
curl -X POST https://your-ngrok-url.ngrok.io/api/webhooks/kobo \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "submission.created",
    "form_id": "arsYddWQmG4Hn2D8XMEdJw",
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

### **Test 2: Create Test Submission**

1. **Submit a test form** in KoboToolbox
2. **Check your application logs** - you should see:
   ```
   Webhook received: submission.created
   Syncing form: arsYddWQmG4Hn2D8XMEdJw
   Records added: 1
   ```
3. **Check your database** - new submission should appear
4. **Check your dashboard** - data should update automatically

---

## 🔧 **Complete Setup Script**

Create a file `start_local_with_webhook.sh` (or `.bat` for Windows):

### **Linux/macOS Script**

```bash
#!/bin/bash

# Start your FastAPI app in background
echo "Starting FastAPI application..."
cd mealbackend
uvicorn main:app --host 0.0.0.0 --port 8000 &
APP_PID=$!

# Wait for app to start
sleep 3

# Start ngrok tunnel
echo "Starting ngrok tunnel..."
ngrok http 8000 &
NGROK_PID=$!

# Wait for ngrok to start
sleep 5

# Get ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*\.ngrok\.io' | head -1)

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo "Application: http://localhost:8000"
echo "Webhook URL: ${NGROK_URL}/api/webhooks/kobo"
echo ""
echo "Configure this URL in KoboToolbox:"
echo "  Settings → Webhooks → Add Webhook"
echo ""
echo "Press Ctrl+C to stop both services"
echo "=========================================="

# Wait for user interrupt
wait
```

### **Windows Script (start_local_with_webhook.bat)**

```batch
@echo off
echo Starting FastAPI application...
start "FastAPI" cmd /k "cd mealbackend && uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 3

echo Starting ngrok tunnel...
start "ngrok" cmd /k "ngrok http 8000"

timeout /t 5

echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo Application: http://localhost:8000
echo.
echo Check ngrok web interface: http://localhost:4040
echo Copy the HTTPS URL and add /api/webhooks/kobo
echo.
echo Configure this URL in KoboToolbox:
echo   Settings -^> Webhooks -^> Add Webhook
echo ==========================================
pause
```

---

## 📊 **Monitor Webhook Activity**

### **View ngrok Requests**

ngrok provides a web interface to monitor requests:
- Open: `http://localhost:4040`
- You'll see all incoming requests in real-time
- Check webhook payloads and responses

### **View Application Logs**

Watch your application logs:
```bash
# In your terminal where uvicorn is running
# You'll see webhook requests like:
INFO: POST /api/webhooks/kobo
INFO: Webhook received: submission.created
INFO: Syncing form: arsYddWQmG4Hn2D8XMEdJw
```

### **Check Database**

```bash
# Using SQLite
sqlite3 mealbackend/app.db "SELECT COUNT(*) FROM submissions;"

# Or check via API
curl http://localhost:8000/api/submissions
```

---

## ⚠️ **Important Notes**

### **1. ngrok URL Changes**
- **Free ngrok**: URL changes every time you restart ngrok
- **Solution**: 
  - Use ngrok's paid plan for static URLs
  - Or update webhook URL in Kobo each time
  - Or use a script to auto-update (see below)

### **2. Keep Both Running**
- Keep both your app AND ngrok running
- If either stops, webhooks won't work
- Use the script above to manage both

### **3. Firewall/Antivirus**
- Some firewalls may block ngrok
- Allow ngrok in your firewall settings
- Check Windows Defender or antivirus

### **4. Network Requirements**
- Your computer must be connected to internet
- Port 8000 should be available
- No VPN conflicts

---

## 🔄 **Alternative: Polling Instead of Webhooks**

If webhooks are too complex, you can use polling:

### **Create a Polling Script**

```python
# scripts/poll_kobo.py
import time
import requests
from database import SessionLocal
from etl import ETLPipeline

def poll_kobo_forms():
    """Poll Kobo for new submissions every 30 seconds."""
    db = SessionLocal()
    etl = ETLPipeline(db)
    
    # Get all forms
    from models import Form
    forms = db.query(Form).filter(Form.is_active == True).all()
    
    while True:
        try:
            for form in forms:
                print(f"Polling form: {form.title}")
                sync_log = etl.sync_form(form.kobo_form_id, sync_type="incremental")
                if sync_log.records_added > 0:
                    print(f"  Added {sync_log.records_added} new submissions")
        except Exception as e:
            print(f"Error polling: {e}")
        
        time.sleep(30)  # Poll every 30 seconds

if __name__ == "__main__":
    poll_kobo_forms()
```

**Run it:**
```bash
python scripts/poll_kobo.py
```

**Note**: Polling uses more API calls and isn't truly "real-time", but it works without webhooks.

---

## 🎯 **Recommended Setup for Local Development**

1. **Use ngrok** (easiest, most reliable)
2. **Keep ngrok web interface open** (`http://localhost:4040`) to monitor
3. **Use the startup script** to manage both services
4. **Test with a real submission** to verify it works

---

## 🐛 **Troubleshooting**

### **Issue: ngrok not connecting**
- Check internet connection
- Verify ngrok is installed correctly
- Try restarting ngrok

### **Issue: Webhook not received**
- Verify ngrok URL is correct in Kobo
- Check ngrok web interface (`http://localhost:4040`) for requests
- Verify your app is running on port 8000
- Check application logs for errors

### **Issue: 404 Not Found**
- Verify URL: `https://your-ngrok-url.ngrok.io/api/webhooks/kobo`
- Check endpoint path is correct
- Test with curl first

### **Issue: 500 Internal Server Error**
- Check application logs
- Verify database connection
- Check Kobo API credentials in `.env`

---

## 📝 **Quick Reference**

**Start App:**
```bash
cd mealbackend
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Start ngrok:**
```bash
ngrok http 8000
```

**Webhook URL Format:**
```
https://YOUR_NGROK_URL.ngrok.io/api/webhooks/kobo
```

**Test Webhook:**
```bash
curl -X POST https://YOUR_NGROK_URL.ngrok.io/api/webhooks/kobo \
  -H "Content-Type: application/json" \
  -d '{"event_type": "submission.created", "form_id": "YOUR_FORM_ID"}'
```

---

**Last Updated**: 2025-12-23

