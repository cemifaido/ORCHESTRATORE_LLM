<#
Avvia la dashboard dell'Orchestratore LLM per l'uso quotidiano.
Se e' gia' in ascolto sulla porta, non ne avvia una seconda copia: apre solo il browser.
Uso: doppio click, o da PowerShell: .\avvia_dashboard.ps1
#>

$ErrorActionPreference = "Stop"
$radice = $PSScriptRoot
$porta = 8095
$cartellaLog = Join-Path $radice "dati_locali"
$log = Join-Path $cartellaLog "dashboard.log"
$logErrori = Join-Path $cartellaLog "dashboard.err.log"

$attiva = Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue

if ($attiva) {
    $pid_attivo = ($attiva | Select-Object -First 1 -ExpandProperty OwningProcess)
    Write-Host "Dashboard gia' attiva sulla porta $porta (PID $pid_attivo). Apro solo il browser."
} else {
    Write-Host "Avvio la dashboard sulla porta $porta..."
    New-Item -ItemType Directory -Force -Path $cartellaLog | Out-Null
    Start-Process -FilePath "python" -ArgumentList "interfaccia.py" -WorkingDirectory $radice `
        -RedirectStandardOutput $log -RedirectStandardError $logErrori -WindowStyle Hidden

    $tentativi = 0
    while (-not (Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue) -and $tentativi -lt 20) {
        Start-Sleep -Milliseconds 500
        $tentativi++
    }

    if (-not (Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue)) {
        Write-Warning "La dashboard non risulta in ascolto dopo 10s. Controlla $logErrori"
        exit 1
    }
    Write-Host "Dashboard pronta."
}

Start-Process "http://127.0.0.1:$porta"
