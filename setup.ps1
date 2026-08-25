# ==============================================================
# SQUADRA (Orchestratore LLM) — Launcher Setup Wizard
# ==============================================================
Write-Host "Avvio Wizard di configurazione Squadra..." -ForegroundColor Cyan

$pythonCmd = "python"
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
}

if ($pythonCmd -eq "py -3") {
    & py -3 setup_wizard.py @args
} else {
    & python setup_wizard.py @args
}
