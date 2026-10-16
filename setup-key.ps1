$ErrorActionPreference = 'Stop'
$secureKey = Read-Host 'Paste your private OpenAQ API key (input will not be displayed)' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $configDir = Join-Path $env:LOCALAPPDATA 'AirScope'
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    Set-Content -Path (Join-Path $configDir 'openaq.env') -Value "OPENAQ_API_KEY=$key" -NoNewline
    Write-Host 'Saved in your local Windows AppData folder (outside OneDrive). Keep it private.'
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}
