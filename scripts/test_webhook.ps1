# PowerShell script to test webhook endpoint

$WEBHOOK_URL = "https://f0c3f65cab43.ngrok-free.app/api/webhooks/kobo"
$FORM_ID = "arsYddWQmG4Hn2D8XMEdJw"

Write-Host "=========================================="
Write-Host "Testing Webhook Endpoint"
Write-Host "=========================================="
Write-Host ""
Write-Host "Webhook URL: $WEBHOOK_URL"
Write-Host "Form ID: $FORM_ID"
Write-Host ""

$body = @{
    event_type = "submission.created"
    form_id = $FORM_ID
    submission_id = "test-123"
    data = @{
        form_id = $FORM_ID
    }
} | ConvertTo-Json

Write-Host "Sending test webhook request..."
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri $WEBHOOK_URL `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -UseBasicParsing
    
    Write-Host "[SUCCESS] Status Code: $($response.StatusCode)"
    Write-Host ""
    Write-Host "Response:"
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
    Write-Host ""
    Write-Host "Webhook is working correctly!"
} catch {
    Write-Host "[ERROR] Webhook test failed"
    Write-Host "Status Code: $($_.Exception.Response.StatusCode.value__)"
    Write-Host "Error: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response: $responseBody"
    }
}

Write-Host ""
Write-Host "=========================================="

