@echo off
REM Script to start FastAPI app with ngrok tunnel for webhook testing (Windows)

echo ==========================================
echo Starting MEAL System with Webhook Support
echo ==========================================
echo.

REM Check if ngrok is installed
where ngrok >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ngrok is not installed!
    echo Please install ngrok: https://ngrok.com/download
    echo Or use: choco install ngrok
    pause
    exit /b 1
)

REM Check if port 8000 is available
netstat -an | findstr ":8000" >nul
if %ERRORLEVEL% EQU 0 (
    echo [WARNING] Port 8000 is already in use
    echo Please stop the service using port 8000 first
    pause
    exit /b 1
)

REM Start FastAPI app
echo [INFO] Starting FastAPI application on port 8000...
start "MEAL FastAPI" cmd /k "cd /d %~dp0.. && uvicorn main:app --host 0.0.0.0 --port 8000"

REM Wait for app to start
echo [INFO] Waiting for application to start...
timeout /t 3 /nobreak >nul

REM Start ngrok tunnel
echo [INFO] Starting ngrok tunnel...
start "ngrok" cmd /k "ngrok http 8000"

REM Wait for ngrok to start
echo [INFO] Waiting for ngrok to start...
timeout /t 5 /nobreak >nul

echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo Application: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo ngrok Web Interface: http://localhost:4040
echo.
echo [IMPORTANT] Get your webhook URL:
echo   1. Open: http://localhost:4040
echo   2. Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
echo   3. Add /api/webhooks/kobo to the end
echo.
echo Configure in KoboToolbox:
echo   1. Go to your form -^> Settings -^> Webhooks
echo   2. Add Webhook
echo   3. URL: https://YOUR_NGROK_URL.ngrok.io/api/webhooks/kobo
echo   4. Events: submission.created, submission.updated
echo   5. Save
echo.
echo ==========================================
echo.
echo Press any key to exit (services will keep running)...
pause >nul

