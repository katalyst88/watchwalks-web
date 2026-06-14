# Polls GitHub Pages until the TLS cert is issued, then turns on Enforce HTTPS.
$log = "C:\Users\jwden\WatchApps\watchwalks-web\https_enable.log"
$env:GIT_TERMINAL_PROMPT = "0"; $env:GCM_INTERACTIVE = "never"
$tok = ((("protocol=https`nhost=github.com`n`n" | git credential fill 2>$null) -split "`n") | Where-Object { $_ -like "password=*" }) -replace "password=",""
$hdr = @{ Authorization = "token $tok"; "User-Agent" = "ww"; Accept = "application/vnd.github+json" }
$api = "https://api.github.com/repos/katalyst88/watchwalks-web/pages"
Set-Content $log "$(Get-Date -Format 'HH:mm:ss') waiting for HTTPS cert..."
for ($i = 0; $i -lt 24; $i++) {
    Start-Sleep -Seconds 300
    try {
        $p = Invoke-RestMethod -Uri $api -Headers $hdr
        $state = $p.https_certificate.state
        "$(Get-Date -Format 'HH:mm:ss') cert=$state enforced=$($p.https_enforced)" | Add-Content $log
        if ($p.https_enforced) { "already enforced" | Add-Content $log; exit 0 }
        if ($state -eq "approved") {
            Invoke-RestMethod -Method Put -Uri $api -Headers $hdr -Body (@{ https_enforced = $true } | ConvertTo-Json) | Out-Null
            "$(Get-Date -Format 'HH:mm:ss') ENFORCE HTTPS ENABLED" | Add-Content $log
            exit 0
        }
    } catch { "$(Get-Date -Format 'HH:mm:ss') err $($_.Exception.Message)" | Add-Content $log }
}
"$(Get-Date -Format 'HH:mm:ss') timeout - cert not ready within 2h" | Add-Content $log
exit 2
