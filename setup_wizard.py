#!/usr/bin/env python3
"""Setup Wizard Interattivo per Squadra (Orchestratore LLM).

Guida l'utente nell'installazione, rilevamento delle risorse a disposizione
(senza vincoli su GPU o agenti specifici) e configurazione iniziale di .env
e progetti locali.

Funziona in modalità:
- Interattiva (default): fa domande chiare e guidate
- Automatica (--auto): rileva le risorse e genera una configurazione funzionante con default
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    reconf_out = getattr(sys.stdout, "reconfigure", None)
    if callable(reconf_out):
        try:
            reconf_out(encoding="utf-8", errors="replace")
        except Exception:
            pass
    reconf_err = getattr(sys.stderr, "reconfigure", None)
    if callable(reconf_err):
        try:
            reconf_err(encoding="utf-8", errors="replace")
        except Exception:
            pass

RADICE = Path(__file__).resolve().parent
DIR_DATI_LOCALI = RADICE / "dati_locali"
DIR_CONFIG = RADICE / "config"
DIR_TEMPLATES_HOOK = DIR_CONFIG / "templates_hook"
FILE_ENV = RADICE / ".env"
FILE_PROGETTI = DIR_DATI_LOCALI / "progetti.json"


# ANSI Colors per console
class Colori:
    RESET = "\033[0m"
    GRASSETTO = "\033[1m"
    VERDE = "\033[92m"
    CIANO = "\033[96m"
    GIALLO = "\033[93m"
    ROSSO = "\033[91m"
    MAGENTA = "\033[95m"
    GRIGIO = "\033[90m"


def stampa_banner() -> None:
    print(f"""
{Colori.CIANO}{Colori.GRASSETTO}===============================================================
       🚀 SQUADRA — Orchestratore Multi-Agente LLM
              WIZARD DI CONFIGURAZIONE GUIDATA
==============================================================={Colori.RESET}
Questo wizard configurerà l'ambiente in base alle risorse presenti sul tuo PC.
{Colori.GRIGIO}Funziona sia con GPU che senza, e con qualsiasi combinazione di agenti.{Colori.RESET}
""")


def chiedi_conferma(domanda: str, default: bool = True) -> bool:
    suggerimento = "[S/n]" if default else "[s/N]"
    try:
        risposta = input(f"{Colori.GRASSETTO}? {domanda} {suggerimento}:{Colori.RESET} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nOperazione annullata.")
        sys.exit(0)
    if not risposta:
        return default
    return risposta in ("s", "si", "sì", "y", "yes", "true", "1")


def chiedi_testo(domanda: str, default: str = "") -> str:
    suggerimento = f" [{default}]" if default else ""
    try:
        risposta = input(f"{Colori.GRASSETTO}? {domanda}{suggerimento}:{Colori.RESET} ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nOperazione annullata.")
        sys.exit(0)
    return risposta if risposta else default


def rileva_eseguibile(nome: str) -> str | None:
    """Rileva se un comando o wrapper Windows e' presente sul PATH."""
    return shutil.which(nome)


def diagnostica_ambiente() -> dict[str, Any]:
    """Scansiona l'ambiente locale in modo non bloccante."""
    info: dict[str, Any] = {}

    # Python
    info["python_versione"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    info["python_ok"] = sys.version_info >= (3, 10)

    # Git
    git_path = rileva_eseguibile("git")
    info["git_presente"] = git_path is not None
    info["git_path"] = git_path

    # CLI Assistenti
    info["claude_presente"] = rileva_eseguibile("claude") is not None
    info["codex_presente"] = rileva_eseguibile("codex") is not None

    agy_path = rileva_eseguibile("agy")
    if not agy_path:
        agy_win = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"
        if agy_win.exists():
            agy_path = str(agy_win)
    info["gemini_presente"] = agy_path is not None

    # LLM Locale (Llama)
    porta_llama = int(os.environ.get("PORTA_LLAMA", "8090"))
    info["llama_attivo"] = False
    try:
        with urllib.request.urlopen(f"http://localhost:{porta_llama}/health", timeout=1.5):
            info["llama_attivo"] = True
    except Exception:
        info["llama_attivo"] = False

    return info


def installa_dipendenze(dev: bool = False) -> bool:
    """Esegue pip install per requirements.txt (e dev se richiesto)."""
    file_req = RADICE / "requirements.txt"
    if not file_req.exists():
        print(f"{Colori.GIALLO}Attenzione: {file_req} non trovato.{Colori.RESET}")
        return False

    cmd = [sys.executable, "-m", "pip", "install", "-r", str(file_req)]
    print(f"\n{Colori.CIANO}→ Installazione dipendenze base (pip)...{Colori.RESET}")
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0:
        print(f"{Colori.ROSSO}Errore durante l'installazione di requirements.txt{Colori.RESET}")
        return False

    if dev:
        file_dev = RADICE / "requirements-dev.txt"
        if file_dev.exists():
            print(f"{Colori.CIANO}→ Installazione dipendenze di sviluppo/quality-gate...{Colori.RESET}")
            res_dev = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(file_dev)], check=False)
            if res_dev.returncode != 0:
                print(f"{Colori.GIALLO}Avviso: installazione dev terminata con codice {res_dev.returncode}{Colori.RESET}")

    print(f"{Colori.VERDE}✓ Dipendenze installate con successo.{Colori.RESET}")
    return True


def genera_file_env(config: dict[str, Any], percorso_env: Path | None = None) -> None:
    """Scrive il file .env con le configurazioni fornite."""
    dest = percorso_env or FILE_ENV
    righe = [
        "# ==============================================================",
        "# SQUADRA (Orchestratore LLM) — Configurazione Ambiente Locale",
        "# Generato automaticamente dal Setup Wizard",
        "# ==============================================================",
        "",
        f"ORCHESTRATORE_HOST={config.get('host', '127.0.0.1')}",
        f"ORCHESTRATORE_PORTA={config.get('porta', 8095)}",
        "",
        "# Agenti abilitati per la cooperazione (separati da virgola)",
        f"AGENTI_ABILITATI={','.join(config.get('agenti_abilitati', ['claude', 'gemini', 'codex']))}",
        "",
        "# Modello LLM Locale gratuito (llama-server)",
        f"LLM_LOCALE_ABILITATO={'true' if config.get('llm_locale_abilitato', True) else 'false'}",
        f"PORTA_LLAMA={config.get('porta_llama', 8090)}",
        f"SCRIPT_AVVIO_LLAMA={config.get('script_avvio_llama', '')}",
        f"MODELLO_LEGGERO_GGUF={config.get('modello_gguf', '')}",
        "",
        "# Il Postino automatico si configura per-progetto dal menu 'profilo operativo'",
        "# in dashboard (standard/brainstorming/super/smodata), non da variabili .env.",
        "# POSTINO_ATTIVO_DEFAULT / POSTINO_HEADLESS_DEFAULT erano legacy e ignorati",
        "# dal runtime: non li scriviamo piu' (rilievo review v4).",
        "",
    ]
    dest.write_text("\n".join(righe), encoding="utf-8")


def inizializza_progetti(radice_orchestratore: Path = RADICE, percorso_progetti: Path | None = None) -> None:
    """Crea o aggiorna dati_locali/progetti.json registrando l'orchestratore."""
    dest = percorso_progetti or FILE_PROGETTI
    dest.parent.mkdir(parents=True, exist_ok=True)
    lista_progetti = []

    if dest.exists():
        try:
            raw = json.loads(dest.read_text(encoding="utf-8")).get("progetti", [])
            if isinstance(raw, list):
                lista_progetti = raw
            elif isinstance(raw, dict):
                lista_progetti = [
                    {"id": k, **v} if isinstance(v, dict) else {"id": k, "nome": k, "percorso": str(v)}
                    for k, v in raw.items()
                ]
        except Exception:
            lista_progetti = []

    if not any(p.get("id") == "orchestratore" for p in lista_progetti if isinstance(p, dict)):
        lista_progetti.insert(0, {
            "id": "orchestratore",
            "nome": "Orchestratore Centrale",
            "percorso": str(radice_orchestratore),
        })

    dest.write_text(json.dumps({"versione_schema": 1, "progetti": lista_progetti}, ensure_ascii=False, indent=2), encoding="utf-8")


def inizializza_config_agenti(
    agenti_selezionati: list[str],
    radice_progetto: Path = RADICE,
    sovrascrivi: bool = False,
    dir_templates: Path | None = None,
) -> dict[str, list[Path]]:
    """Inizializza le configurazioni locali di hook per gli agenti a partire dai template generici.

    Non sovrascrive i file esistenti a meno che sovrascrivi=True.
    Ritorna un dizionario con gli agenti e i percorsi dei file configurati/creati.
    """
    risultati: dict[str, list[Path]] = {}
    cartella_tmpl = dir_templates or DIR_TEMPLATES_HOOK

    mappa: dict[str, list[tuple[str, Path]]] = {
        "claude": [
            ("claude_settings.esempio.json", Path(".claude") / "settings.json"),
        ],
        "codex": [
            ("codex_hooks.esempio.json", Path(".codex") / "hooks.json"),
        ],
        "gemini": [
            ("gemini_hooks.esempio.json", Path(".agents") / "hooks.json"),
            ("gemini_settings.esempio.json", Path(".gemini") / "settings.json"),
        ],
    }

    for agente in agenti_selezionati:
        ag_norm = agente.lower().strip()
        if ag_norm not in mappa:
            continue
        risultati[ag_norm] = []
        for nome_template, path_relativo in mappa[ag_norm]:
            file_dest = radice_progetto / path_relativo
            file_tmpl = cartella_tmpl / nome_template

            if file_dest.exists() and not sovrascrivi:
                risultati[ag_norm].append(file_dest)
                continue

            file_dest.parent.mkdir(parents=True, exist_ok=True)
            if file_tmpl.exists():
                # I template invocano bacheca.py / hook_gemini.py: se lasciati
                # relativi si risolvono rispetto alla CWD dell'agente (che per
                # Antigravity e' .agents/, non la root) e l'hook fallisce muto se
                # l'agente lavora su un altro progetto (rilievo review v4 N7).
                # Sostituiamo il placeholder col percorso assoluto (POSIX-style:
                # niente escaping JSON, funziona anche su Windows).
                contenuto = file_tmpl.read_text(encoding="utf-8").replace(
                    "__RADICE_ORCHESTRATORE__", RADICE.as_posix()
                )
                file_dest.write_text(contenuto, encoding="utf-8")
            risultati[ag_norm].append(file_dest)

    return risultati


def installa_hook_git() -> bool:
    """Installa l'hook git pre-commit per il quality gate se disponibile."""
    script_hook = RADICE / "utility" / "installa_hook.py"
    if script_hook.exists():
        res = subprocess.run([sys.executable, str(script_hook)], capture_output=True, text=True, check=False)
        return res.returncode == 0
    return False


def stampa_diagnostica(diag: dict[str, Any]) -> None:
    print(f"{Colori.GRASSETTO}[1/6] Diagnostica Ambiente & Strumenti{Colori.RESET}")
    py_ok = "✓" if diag["python_ok"] else f"{Colori.ROSSO}✗ (richiesto >= 3.10){Colori.RESET}"
    git_ok = f"{Colori.VERDE}✓ Presente{Colori.RESET}" if diag["git_presente"] else f"{Colori.ROSSO}✗ Non trovato nel PATH{Colori.RESET}"
    print(f"  • Python: {Colori.VERDE}{diag['python_versione']}{Colori.RESET} {py_ok}")
    print(f"  • Git: {git_ok}")

    print("\n  Assistenti AI rilevati sul sistema:")
    agenti_check = (
        ("Claude Code (claude)", "claude_presente"),
        ("OpenAI Codex (codex)", "codex_presente"),
        ("Google Gemini (agy)", "gemini_presente"),
    )
    for ag, key in agenti_check:
        status = f"{Colori.VERDE}✓ Rilevato{Colori.RESET}" if diag[key] else f"{Colori.GRIGIO}Non installato (opzionale){Colori.RESET}"
        print(f"  • {ag}: {status}")

    print("\n  Modello Locale (Llama-server / GPU):")
    if diag["llama_attivo"]:
        llama_status = f"{Colori.VERDE}✓ Attivo in ascolto{Colori.RESET}"
    else:
        llama_status = f"{Colori.GRIGIO}Non attivo (opzionale, supporta modalità senza GPU){Colori.RESET}"
    print(f"  • Llama-server (porta 8090): {llama_status}")


def configura_modalita_auto(diag: dict[str, Any], salta_pip: bool) -> dict[str, Any]:
    print(f"\n{Colori.CIANO}→ Modalità automatica: applicazione default ottimali...{Colori.RESET}")
    agenti = []
    if diag["claude_presente"]:
        agenti.append("claude")
    if diag["gemini_presente"]:
        agenti.append("gemini")
    if diag["codex_presente"]:
        agenti.append("codex")
    if not agenti:
        agenti = ["claude", "gemini", "codex"]

    config = {
        "agenti_abilitati": agenti,
        "llm_locale_abilitato": diag["llama_attivo"],
        "host": "127.0.0.1",
        "porta": 8095,
        "porta_llama": 8090,
        "script_avvio_llama": "",
        "modello_gguf": "",
        "postino_attivo": True,
        "postino_headless": False,
    }

    if not salta_pip:
        installa_dipendenze(dev=False)
    genera_file_env(config)
    inizializza_progetti()
    inizializza_config_agenti(config["agenti_abilitati"])
    installa_hook_git()
    return config


def configura_modalita_interattiva(diag: dict[str, Any], salta_pip: bool) -> dict[str, Any]:
    config: dict[str, Any] = {}

    # PASSO 2: Selezione Assistenti
    print(f"\n{Colori.GRASSETTO}[2/6] Configurazione Squadra & Assistenti{Colori.RESET}")
    agenti_selezionati = []
    if chiedi_conferma("Abilitare Claude Code nella squadra?", default=diag["claude_presente"]):
        agenti_selezionati.append("claude")
    if chiedi_conferma("Abilitare Gemini (Antigravity) nella squadra?", default=diag["gemini_presente"]):
        agenti_selezionati.append("gemini")
    if chiedi_conferma("Abilitare OpenAI Codex nella squadra?", default=diag["codex_presente"]):
        agenti_selezionati.append("codex")

    if not agenti_selezionati:
        print(f"{Colori.GIALLO}Nessun agente esterno selezionato: userai la modalità manuale/dashboard.{Colori.RESET}")
        agenti_selezionati = ["umano"]
    else:
        if chiedi_conferma("Inizializzare automaticamente le configurazioni locali di hook per gli agenti scelti?", default=True):
            inizializza_config_agenti(agenti_selezionati)

    config["agenti_abilitati"] = agenti_selezionati

    # PASSO 3: Modello Locale & GPU
    print(f"\n{Colori.GRASSETTO}[3/6] Modello AI Locale (Triage & Sintesi a costo zero){Colori.RESET}")
    print(f"{Colori.GRIGIO}Nota: Se il tuo PC non ha una scheda video dedicata, puoi rispondere 'No': userà controlli deterministici veloci.{Colori.RESET}")
    usa_llama = chiedi_conferma("Disponi di GPU e desideri abilitare il modello locale gratuito (llama-server)?", default=diag["llama_attivo"])
    config["llm_locale_abilitato"] = usa_llama

    if usa_llama:
        config["porta_llama"] = int(chiedi_testo("Porta del server llama locale", default="8090"))
        config["script_avvio_llama"] = chiedi_testo("Percorso script avvio llama (opzionale se già avviato)", default="")
        config["modello_gguf"] = chiedi_testo("Percorso file modello .gguf leggero (opzionale)", default="")
    else:
        config["porta_llama"] = 8090
        config["script_avvio_llama"] = ""
        config["modello_gguf"] = ""

    # PASSO 4: Dipendenze Python
    print(f"\n{Colori.GRASSETTO}[4/6] Installazione Dipendenze Python{Colori.RESET}")
    if not salta_pip and chiedi_conferma("Installare/aggiornare i pacchetti Python richiesti (FastAPI, pytest, ecc.)?", default=True):
        installa_dev = chiedi_conferma("Installare anche i pacchetti di sviluppo/quality-gate (ruff, mypy, xenon)?", default=True)
        installa_dipendenze(dev=installa_dev)

    # PASSO 5: Dashboard e Postino
    print(f"\n{Colori.GRASSETTO}[5/6] Parametri Dashboard e Postino{Colori.RESET}")
    config["host"] = "127.0.0.1"
    config["porta"] = int(chiedi_testo("Porta Web Dashboard", default="8095"))
    config["postino_attivo"] = chiedi_conferma("Attivare il Postino di sincronizzazione bacheca?", default=True)
    config["postino_headless"] = chiedi_conferma("Abilitare il Dispatch Headless in background (avanzato, spento di default)?", default=False)

    genera_file_env(config)
    inizializza_progetti()

    # Progetti addizionali
    if chiedi_conferma("Desideri registrare subito un altro progetto locale nella dashboard?", default=False):
        _aggiungi_progetto_opzionale()

    # PASSO 6: Hook Git
    print(f"\n{Colori.GRASSETTO}[6/6] Quality Gate & Hook Git{Colori.RESET}")
    if chiedi_conferma("Installare l'hook Git pre-commit per verificare automaticamente lint/tipi prima di ogni commit?", default=True):
        if installa_hook_git():
            print(f"{Colori.VERDE}✓ Hook pre-commit installato con successo.{Colori.RESET}")
        else:
            print(f"{Colori.GIALLO}Avviso: impossibile installare l'hook pre-commit (.git non trovato o permessi insufficienti).{Colori.RESET}")

    return config


def _aggiungi_progetto_opzionale() -> None:
    nome_p = chiedi_testo("Nome del progetto (es. Mia App)")
    path_p = chiedi_testo("Percorso assoluto cartella progetto")
    if nome_p and path_p and Path(path_p).exists():
        try:
            dati_proj = json.loads(FILE_PROGETTI.read_text(encoding="utf-8"))
            progetti = dati_proj.get("progetti", [])
            id_p = nome_p.lower().replace(" ", "_")
            if isinstance(progetti, list):
                progetti.append({"id": id_p, "nome": nome_p, "percorso": path_p})
            elif isinstance(progetti, dict):
                progetti[id_p] = {"nome": nome_p, "percorso": path_p}
            FILE_PROGETTI.write_text(json.dumps(dati_proj, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{Colori.VERDE}✓ Progetto '{nome_p}' aggiunto a {FILE_PROGETTI}.{Colori.RESET}")
        except Exception as ex:
            print(f"{Colori.ROSSO}Errore nel salvataggio del progetto: {ex}{Colori.RESET}")


def stampa_riepilogo_finale(config: dict[str, Any]) -> None:
    gpu_desc = (
        f"Attivo (Llama porta {config.get('porta_llama', 8090)})"
        if config.get("llm_locale_abilitato")
        else "Disabilitato (Modalità Deterministica Senza GPU)"
    )
    postino_desc = f"{'Attivo' if config.get('postino_attivo') else 'Disattivato'} (Headless: {'Sì' if config.get('postino_headless') else 'No'})"

    hook_elenco = []
    for ag in config.get("agenti_abilitati", []):
        if ag == "claude":
            hook_elenco.append("Claude (.claude/settings.json)")
        elif ag == "codex":
            hook_elenco.append("Codex (.codex/hooks.json)")
        elif ag == "gemini":
            hook_elenco.append("Gemini (.agents/hooks.json)")
    hook_desc = ", ".join(hook_elenco) if hook_elenco else "Nessuno"

    print(f"""
{Colori.VERDE}{Colori.GRASSETTO}===============================================================
               ✨ SETUP COMPLETATO CON SUCCESSO!
==============================================================={Colori.RESET}
Riepilogo configurazione salvata in {Colori.CIANO}.env{Colori.RESET}:
  • Dashboard:             http://{config.get('host', '127.0.0.1')}:{config.get('porta', 8095)}
  • Squadra Abilitata:     {', '.join(config.get('agenti_abilitati', []))}
  • LLM Locale (GPU):      {gpu_desc}
  • Postino Automatico:    {postino_desc}
  • Hook Agenti:           {hook_desc}

{Colori.GRASSETTO}Per avviare la Dashboard Web ora:{Colori.RESET}
  {Colori.CIANO}.\\avvia_dashboard.ps1{Colori.RESET}
""")


def esegui_wizard(auto: bool = False, salta_pip: bool = False) -> int:
    stampa_banner()
    diag = diagnostica_ambiente()
    stampa_diagnostica(diag)

    if auto:
        config = configura_modalita_auto(diag, salta_pip)
    else:
        config = configura_modalita_interattiva(diag, salta_pip)

    stampa_riepilogo_finale(config)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Wizard di configurazione per Squadra (Orchestratore LLM)")
    parser.add_argument("--auto", action="store_true", help="Configurazione automatica non-interattiva")
    parser.add_argument("--salta-pip", action="store_true", help="Salta l'installazione dei pacchetti pip")
    args = parser.parse_args()
    return esegui_wizard(auto=args.auto, salta_pip=args.salta_pip)


if __name__ == "__main__":
    raise SystemExit(main())
