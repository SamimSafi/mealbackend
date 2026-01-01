# PowerShell script to configure ngrok authtoken

$AUTHTOKEN = "4NUsoYfBtHFvg2mbAXh5U_4XN8S6cYhG5qtNS89h9Mc"

Write-Host "=========================================="
Write-Host "Configuring ngrok Authtoken"
Write-Host "=========================================="
Write-Host ""

# Method 1: Set environment variable for current session
Write-Host "[1] Setting environment variable for current session..."
$env:NGROK_AUTHTOKEN = $AUTHTOKEN
Write-Host "    NGROK_AUTHTOKEN set for current PowerShell session"
Write-Host ""

# Method 2: Configure ngrok directly (recommended)
Write-Host "[2] Configuring ngrok config file (recommended)..."
try {
    ngrok config add-authtoken $AUTHTOKEN
    Write-Host "    ✅ ngrok authtoken configured successfully!"
} catch {
    Write-Host "    ⚠️  Could not configure ngrok (may need to install ngrok first)"
    Write-Host "    Error: $_"
}
Write-Host ""

# Method 3: Set permanent environment variable (User level)
Write-Host "[3] Setting permanent environment variable (User level)..."
try {
    [System.Environment]::SetEnvironmentVariable("NGROK_AUTHTOKEN", $AUTHTOKEN, "User")
    Write-Host "    ✅ Permanent environment variable set (User level)"
    Write-Host "    Note: Restart PowerShell for it to take effect"
} catch {
    Write-Host "    ⚠️  Could not set permanent environment variable"
    Write-Host "    Error: $_"
}
Write-Host ""

Write-Host "=========================================="
Write-Host "✅ Configuration Complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Verify: ngrok config check"
Write-Host "  2. Start ngrok: ngrok http 8000"
Write-Host ""

