#!/bin/bash

# Script to start FastAPI app with ngrok tunnel for webhook testing

echo "=========================================="
echo "Starting MEAL System with Webhook Support"
echo "=========================================="
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok is not installed!"
    echo "Please install ngrok: https://ngrok.com/download"
    echo "Or use: brew install ngrok (macOS) or choco install ngrok (Windows)"
    exit 1
fi

# Check if port 8000 is available
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port 8000 is already in use"
    echo "Please stop the service using port 8000 first"
    exit 1
fi

# Start FastAPI app in background
echo "🚀 Starting FastAPI application on port 8000..."
cd "$(dirname "$0")/.."
uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/meal_app.log 2>&1 &
APP_PID=$!

# Wait for app to start
echo "⏳ Waiting for application to start..."
sleep 3

# Check if app started successfully
if ! ps -p $APP_PID > /dev/null; then
    echo "❌ Failed to start application"
    cat /tmp/meal_app.log
    exit 1
fi

echo "✅ Application started (PID: $APP_PID)"
echo ""

# Start ngrok tunnel
echo "🌐 Starting ngrok tunnel..."
ngrok http 8000 > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
echo "⏳ Waiting for ngrok to start..."
sleep 5

# Get ngrok URL
echo "📡 Getting ngrok URL..."
sleep 2
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o 'https://[^"]*\.ngrok\.io' | head -1)

if [ -z "$NGROK_URL" ]; then
    echo "⚠️  Could not get ngrok URL automatically"
    echo "Please check ngrok web interface: http://localhost:4040"
    NGROK_URL="https://YOUR_NGROK_URL.ngrok.io"
else
    echo "✅ ngrok tunnel active"
fi

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📍 Application: http://localhost:8000"
echo "📍 API Docs: http://localhost:8000/docs"
echo "📍 ngrok Web Interface: http://localhost:4040"
echo ""
echo "🔗 Webhook URL:"
echo "   ${NGROK_URL}/api/webhooks/kobo"
echo ""
echo "📋 Configure in KoboToolbox:"
echo "   1. Go to your form → Settings → Webhooks"
echo "   2. Add Webhook"
echo "   3. URL: ${NGROK_URL}/api/webhooks/kobo"
echo "   4. Events: submission.created, submission.updated"
echo "   5. Save"
echo ""
echo "🧪 Test webhook:"
echo "   curl -X POST ${NGROK_URL}/api/webhooks/kobo \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"event_type\":\"submission.created\",\"form_id\":\"YOUR_FORM_ID\"}'"
echo ""
echo "📊 Monitor:"
echo "   - App logs: tail -f /tmp/meal_app.log"
echo "   - ngrok requests: http://localhost:4040"
echo ""
echo "⏹️  Press Ctrl+C to stop both services"
echo "=========================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $APP_PID 2>/dev/null
    kill $NGROK_PID 2>/dev/null
    echo "✅ Stopped"
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Wait for user interrupt
wait

