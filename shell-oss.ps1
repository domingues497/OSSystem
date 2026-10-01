# Shell rapido para projeto OSSystem - garante Git no PATH
$GitCmd  = "C:\Program Files\Git\cmd"
$GitBin  = "C:\Program Files\Git\bin"
$parts   = $env:PATH -split ';'
if ($parts -notcontains $GitCmd) { $env:PATH = "$GitCmd;$GitBin;$env:PATH" }

Set-Alias -Name g -Value git -Option AllScope -Scope Global -Force
Set-Location "c:\Projetos\OSSystem"

Write-Host ""
Write-Host "=== OSSystem Shell ===" -ForegroundColor Cyan
Write-Host "Pasta...: $(Get-Location)"
Write-Host "Git.....: $(git --version)"
Write-Host "Usuario.: $(& git config --local user.name) <$(& git config --local user.email)>"
Write-Host "Dica....: use 'g st' (git status), 'g add .', 'g commit -m msg'"
Write-Host ""
