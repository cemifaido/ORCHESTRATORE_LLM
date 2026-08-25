#!/usr/bin/env python3
"""Verifica versioni installate vs disponibili delle CLI headless del postino
(claude, codex, agy) e, se serve, accende il modello locale leggero per un
riassunto delle note di rilascio. Read-only sulle CLI: non le aggiorna mai da
solo (nessuna chiamata a `claude update`/`codex update`/`agy update` qui
dentro) - l'aggiornamento resta un atto separato, deliberato, dopo verdetto
umano (vedi docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import bacheca
from adattatori import litellm

RADICE = Path(__file__).resolve().parent

PORTA_LLAMA_PREDEFINITA = 8090
# Modello leggero (solo testo) per compiti di riassunto: il default del progetto
# (Qwen VL 7B, con visione) e' pensato per altri usi - inutilmente pesante qui.
# Percorsi/parametri presi da start_llama_only.bat, blocco ":model_3b_q4".
SCRIPT_AVVIO_LLAMA = Path(r"D:\Share\py\altro-progetto\0.6_app\start_llama_only.ps1")
MODELLO_LEGGERO_GGUF = Path(
    r"C:\Users\paolo_pavesi\ollama-models\qwen2.5-3b-instruct\qwen2.5-3b-instruct-q4_k_m.gguf"
)

COMANDI_VERSIONE = {
    "claude": ["claude", "--version"],
    "codex": ["codex", "--version"],
    "gemini": ["agy", "--version"],
}
PACCHETTI_NPM = {"claude": "@anthropic-ai/claude-code", "codex": "@openai/codex"}
MANIFEST_AGY_URL = (
    "https://antigravity-cli-auto-updater-974169037036.us-central1.run.app"
    "/manifests/windows_amd64.json"
)

_RE_VERSIONE = re.compile(r"\d+\.\d+\.\d+")


def llama_attivo(porta: int = PORTA_LLAMA_PREDEFINITA, timeout: float = 5.0) -> bool:
    """True se llama-server risponde su /health, qualunque modello abbia caricato -
    non tocca nulla se e' gia' su, come richiesto (usa quello acceso)."""
    try:
        with urllib.request.urlopen(f"http://localhost:{porta}/health", timeout=timeout):
            return True
    except (urllib.error.URLError, OSError):
        return False


def avvia_llama_leggero(
    *,
    script: Path = SCRIPT_AVVIO_LLAMA,
    modello: Path = MODELLO_LEGGERO_GGUF,
    porta: int = PORTA_LLAMA_PREDEFINITA,
    timeout_avvio_secondi: float = 120.0,
    avvia_processo=subprocess.Popen,
) -> bool:
    """Avvia llama-server col modello leggero (Qwen 2.5 3B, solo testo) in
    background e attende che risponda su /health. Non fa nulla se e' gia'
    attivo (chiamare prima llama_attivo() per quello - qui si avvia sempre,
    per restare una funzione a singola responsabilita' e testabile)."""
    if not script.exists():
        raise FileNotFoundError(f"script di avvio llama non trovato: {script}")
    if not modello.exists():
        raise FileNotFoundError(f"modello gguf non trovato: {modello}")
    avvia_processo(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
            "-LlamaModel", str(modello), "-LlamaMmproj", "", "-LlamaGpuLayers", "999",
            "-LlamaParallel", "1", "-LlamaPort", str(porta),
        ],
        cwd=str(script.parent),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    scadenza = time.monotonic() + timeout_avvio_secondi
    while time.monotonic() < scadenza:
        if llama_attivo(porta=porta, timeout=3.0):
            return True
        time.sleep(3.0)
    return False


def assicura_llama_attivo(*, porta: int = PORTA_LLAMA_PREDEFINITA, **kwargs: Any) -> bool:
    """Se llama-server e' gia' acceso, lo lascia stare (qualunque modello abbia
    caricato). Se e' spento, lo accende col modello leggero. Ritorna lo stato
    finale (True = pronto all'uso)."""
    if llama_attivo(porta=porta):
        return True
    return avvia_llama_leggero(porta=porta, **kwargs)


def _estrai_versione(testo: str) -> str | None:
    """Estrae il primo pattern N.N.N da un output CLI eterogeneo:
    'codex-cli 0.149.1' / '2.1.204 (Claude Code)' / '1.1.0'."""
    trovata = _RE_VERSIONE.search(testo)
    return trovata.group(0) if trovata else None


def _risolvi_eseguibile(nome: str) -> str | None:
    """subprocess.run con shell=False non passa da PATHEXT su Windows: un nome
    nudo come 'codex'/'npm' non risolve mai il wrapper .cmd anche se e' sul
    PATH (stesso bug reale gia' corretto in postino.py il 2026-08-25)."""
    return shutil.which(nome)


def versione_installata(agente: str, *, esegui=subprocess.run) -> str | None:
    comando = COMANDI_VERSIONE.get(agente)
    if comando is None:
        return None
    eseguibile = _risolvi_eseguibile(comando[0])
    if eseguibile is None:
        return None
    try:
        risultato = esegui([eseguibile, *comando[1:]], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return _estrai_versione(risultato.stdout + risultato.stderr)


def _versione_npm(pacchetto: str, *, richiedi=subprocess.run) -> str | None:
    eseguibile = _risolvi_eseguibile("npm")
    if eseguibile is None:
        return None
    try:
        risultato = richiedi(
            [eseguibile, "view", pacchetto, "version"], capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if risultato.returncode != 0:
        return None
    return _estrai_versione(risultato.stdout)


def _versione_manifest_agy(*, apri_url=urllib.request.urlopen) -> str | None:
    try:
        with apri_url(MANIFEST_AGY_URL, timeout=15) as risposta:
            dati = json.loads(risposta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return None
    versione = dati.get("version")
    return _estrai_versione(versione) if isinstance(versione, str) else None


def versione_disponibile(agente: str, *, esegui_npm=subprocess.run, apri_url=urllib.request.urlopen) -> str | None:
    if agente in PACCHETTI_NPM:
        return _versione_npm(PACCHETTI_NPM[agente], richiedi=esegui_npm)
    if agente == "gemini":
        return _versione_manifest_agy(apri_url=apri_url)
    return None


def confronta_versioni(a: str, b: str) -> int:
    """-1 se a<b, 0 se uguali, 1 se a>b. Confronto numerico per componente
    (non lessicografico: '0.9.0' < '0.10.0', un confronto di stringhe sbaglierebbe)."""
    tupla_a = tuple(int(x) for x in a.split("."))
    tupla_b = tuple(int(x) for x in b.split("."))
    if tupla_a < tupla_b:
        return -1
    if tupla_a > tupla_b:
        return 1
    return 0


def verifica_tutti(
    agenti: tuple[str, ...] = ("claude", "codex", "gemini"), **kwargs: Any
) -> dict[str, dict[str, Any]]:
    """Per ogni agente: versione installata, ultima disponibile, e se c'e'
    un aggiornamento. Read-only: nessuna CLI viene aggiornata qui."""
    risultato: dict[str, dict[str, Any]] = {}
    for agente in agenti:
        installata = versione_installata(agente)
        disponibile = versione_disponibile(agente, **kwargs)
        aggiornamento = (
            installata is not None and disponibile is not None
            and confronta_versioni(installata, disponibile) < 0
        )
        risultato[agente] = {
            "installata": installata,
            "disponibile": disponibile,
            "aggiornamento_disponibile": aggiornamento,
        }
    return risultato


URL_RELEASES_CODEX = "https://api.github.com/repos/openai/codex/releases/latest"


def _note_rilascio_codex(*, apri_url=urllib.request.urlopen) -> str | None:
    try:
        richiesta = urllib.request.Request(URL_RELEASES_CODEX, headers={"User-Agent": "orchestratore-llm"})
        with apri_url(richiesta, timeout=15) as risposta:
            dati = json.loads(risposta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return None
    corpo = dati.get("body")
    return corpo.strip() if isinstance(corpo, str) and corpo.strip() else None


def _note_rilascio_gemini(*, esegui=subprocess.run) -> str | None:
    eseguibile = _risolvi_eseguibile("agy")
    if eseguibile is None:
        return None
    try:
        risultato = esegui([eseguibile, "changelog"], capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return risultato.stdout.strip() if risultato.returncode == 0 and risultato.stdout.strip() else None


def note_rilascio(agente: str, **kwargs: Any) -> str | None:
    """Testo grezzo delle note di rilascio, per fonte quando ce n'e' una
    affidabile nota. Per claude non ne conosciamo una: torna None (non e' un
    errore, e' un limite noto - la notifica in bacheca resta comunque utile
    coi soli numeri di versione, il resto lo si approfondisce a mano)."""
    if agente == "codex":
        return _note_rilascio_codex(**kwargs)
    if agente == "gemini":
        return _note_rilascio_gemini(**kwargs)
    return None


PROMPT_SISTEMA_RIASSUNTO = (
    "Riassumi in italiano semplice, in 3-5 righe, cosa cambia in queste note di "
    "rilascio per chi usa questo strumento da riga di comando ogni giorno. Se ci "
    "sono correzioni di sicurezza o cambi che rompono la compatibilita', mettili "
    "in evidenza per primi. Nessuna premessa, vai dritto al contenuto."
)


def riassumi_note_rilascio(testo: str, *, chiama_locale=None) -> str | None:
    """Passa il testo (gia' recuperato altrove) al modello locale per un
    riassunto - il modello locale non naviga mai internet da solo, riceve
    solo testo. Ritorna None se il modello locale non risponde (fail-soft:
    la notifica in bacheca resta utile anche senza riassunto)."""
    if chiama_locale is None:
        chiama_locale = litellm.completamento_locale
    try:
        risposta, _misurazione = chiama_locale(
            messaggi=[
                {"role": "system", "content": PROMPT_SISTEMA_RIASSUNTO},
                {"role": "user", "content": testo[:6000]},
            ],
            max_tokens=400, temperature=0.2,
        )
    except Exception:
        return None
    riassunto = litellm.testo_da_risposta(risposta).strip()
    return riassunto or None


def notifica_bacheca_aggiornamento(
    radice: Path, agente: str, installata: str, disponibile: str, riassunto: str | None = None,
) -> dict[str, Any]:
    """Apre un thread in bacheca indirizzato a claude, mittente=sistema -
    stesso schema degli altri eventi automatici del postino. Non e' un
    checkpoint (nessun thread precedente da cui dipendere): e' l'apertura,
    claude fa l'approfondimento e la richiesta di consenso quando lo raccoglie."""
    testo = (
        f"AGGIORNAMENTO DISPONIBILE per {agente}: installata {installata}, "
        f"disponibile {disponibile}."
    )
    if riassunto:
        testo += f"\n\nRiassunto del modello locale sulle note di rilascio:\n{riassunto}"
    else:
        testo += (
            "\n\nNessun riassunto disponibile (nessuna fonte nota di note di rilascio per "
            "questo tool, o modello locale non raggiungibile) - da approfondire a mano."
        )
    messaggio = bacheca.costruisci_messaggio(
        mittente="sistema", destinatari=["claude"], tipo="richiesta", testo=testo,
    )
    percorso = radice / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
    bacheca.aggiungi_messaggio(percorso, messaggio)
    return messaggio


def esegui_controllo_e_notifica(radice: Path = RADICE) -> dict[str, Any]:
    """Il compito completo, chiamabile sia da un'Attivita' Pianificata di
    Windows (settimanale) sia al volo su richiesta. Read-only sulle CLI, mai
    un aggiornamento automatico: solo verifica + notifica."""
    assicura_llama_attivo()
    esito = verifica_tutti()
    notificati = []
    for agente, info in esito.items():
        if not info["aggiornamento_disponibile"]:
            continue
        note = note_rilascio(agente)
        riassunto = riassumi_note_rilascio(note) if note else None
        messaggio = notifica_bacheca_aggiornamento(
            radice, agente, info["installata"], info["disponibile"], riassunto,
        )
        notificati.append(messaggio["id_messaggio"])
    return {"verifica": esito, "notificati": notificati}


def main() -> int:
    esito = esegui_controllo_e_notifica()
    print(json.dumps(esito, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
