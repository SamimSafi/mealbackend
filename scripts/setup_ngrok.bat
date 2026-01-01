@echo off
REM Batch script to configure ngrok authtoken (Windows)

set AUTHTOKEN=4NUsoYfBtHFvg2mbAXh5U_4XN8S6cYhG5qtNS89h9Mc

echo ==========================================
echo Configuring ngrok Authtoken
echo ==========================================
echo.

REM Method 1: Set environment variable for current session
echo [1] Setting environment variable for current session...
set NGROK_AUTHTOKEN=%AUTHTOKEN%
echo    NGROK_AUTHTOKEN set for current Command Prompt session
echo.

REM Method 2: Configure ngrok directly (recommended)
echo [2] Configuring ngrok config file (recommended)...
ngrok config add-authtoken %AUTHTOKEN%
if %ERRORLEVEL% EQU 0 (
    echo    [SUCCESS] ngrok authtoken configured successfully!
) else (
    echo    [WARNING] Could not configure ngrok (may need to install ngrok first)
)
echo.

REM Method 3: Set permanent environment variable (User level)
echo [3] Setting permanent environment variable (User level)...
setx NGROK_AUTHTOKEN "%AUTHTOKEN%"
if %ERRORLEVEL% EQU 0 (
    echo    [SUCCESS] Permanent environment variable set (User level)
    echo    Note: Restart Command Prompt for it to take effect
) else (
    echo    [WARNING] Could not set permanent environment variable
)
echo.

echo ==========================================
echo Configuration Complete!
echo ==========================================
echo.
echo Next steps:
echo   1. Verify: ngrok config check
echo   2. Start ngrok: ngrok http 8000
echo.
pause

