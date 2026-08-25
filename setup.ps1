# ==============================================================
# SQUADRA (Orchestratore LLM) — Launcher Setup Wizard
# ==============================================================
Write-Host "Avvio Wizard di configurazione Squadra..." -ForegroundColor Cyan

$pythonCmd = "python"
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
}

Invoke-Expression "$pythonCmd setup_wizard.py $args"
