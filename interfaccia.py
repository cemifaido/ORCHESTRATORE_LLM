#!/usr/bin/env python3
"""Composition root e facade per la Dashboard dell'Orchestratore LLM (Lotto D + E).

Architettura modulare disaccoppiata (backlog architetturale D2):
- dashboard_config.py: percorsi, configurazione .env, host/porta/chiave e bind di rete.
- dashboard_progetti.py: repository progetti.json, integrazione target e istruzioni agenti.
- dashboard_flussi.py: flussi dichiarati e adapter verso motore_flusso.
- dashboard_servizi.py: use case di sola lettura (stato, commit replay, bacheca/feed/thread).
- dashboard_os.py: adapter a basso livello per sistema operativo, probe PID e subprocess.
- dashboard_risvegli.py: logica notifiche, prompt LLM e decisione policy risvegli.
- interfaccia_api.py: router FastAPI, modelli Pydantic e controller HTTP.

Questo modulo orchestra l'avvio di FastAPI, registra middleware e watcher,
e mantiene la facade retrocompatibile verificata dalla suite di test.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel as BaseModel

import bacheca as bacheca
import dashboard_config
import dashboard_flussi
import dashboard_os
import dashboard_progetti
import dashboard_risvegli
import dashboard_servizi
import interfaccia_api
import postino as postino

# -- Re-export configurazione e costanti (Lotti D & E) ------------------------
RADICE = dashboard_config.RADICE
PERCORSO_PROGETTI = dashboard_config.PERCORSO_PROGETTI
PERCORSO_HTML = dashboard_config.PERCORSO_HTML
PERCORSO_FLUSSI = dashboard_config.PERCORSO_FLUSSI
SCRIPT_SENTINELLA_CENTRALE = dashboard_config.SCRIPT_SENTINELLA_CENTRALE
SCRIPT_INTERFACCIA = dashboard_config.SCRIPT_INTERFACCIA
HOST_DASHBOARD = dashboard_config.HOST_DASHBOARD
PORTA_DASHBOARD = dashboard_config.PORTA_DASHBOARD
CHIAVE_API_DASHBOARD = dashboard_config.CHIAVE_API_DASHBOARD
AGENTI_BACHECA_DASHBOARD = dashboard_config.AGENTI_BACHECA_DASHBOARD
_INDIRIZZI_LOOPBACK = dashboard_config._INDIRIZZI_LOOPBACK
bind_e_loopback = dashboard_config.bind_e_loopback
_bind_e_loopback = dashboard_config.bind_e_loopback
carica_env = dashboard_config.carica_env
verifica_bind_sicuro = dashboard_config.verifica_bind_sicuro

# -- Re-export repository progetti e funzioni di facciata ---------------------
ISTRUZIONI_AGENTI = dashboard_progetti.ISTRUZIONI_AGENTI
_LETTURA_EVENTI_RECENTI = dashboard_progetti._LETTURA_EVENTI_RECENTI
_contenuto_istruzioni_agente = dashboard_progetti._contenuto_istruzioni_agente
integra_progetto = dashboard_progetti.integra_progetto
percorso_comandi_progetto = dashboard_progetti.percorso_comandi_progetto
comandi_disponibili_progetto = dashboard_progetti.comandi_disponibili_progetto
arricchisci_progetto = dashboard_progetti.arricchisci_progetto
progetto_o_404 = dashboard_progetti.progetto_o_404


def leggi_progetti() -> list[dict]:
    """Legge i progetti rispettando il PERCORSO_PROGETTI configurato o patchato."""
    return dashboard_progetti.leggi_progetti(PERCORSO_PROGETTI)


def salva_progetti(progetti: list[dict]) -> None:
    """Salva i progetti rispettando il PERCORSO_PROGETTI configurato o patchato."""
    dashboard_progetti.salva_progetti(progetti, PERCORSO_PROGETTI)


def _progetto_o_404(progetto_id: str) -> dict:
    """Cerca il progetto tra quelli attualmente letti (o mockati) o solleva 404."""
    progetti = leggi_progetti()
    progetto = next((p for p in progetti if p["id"] == progetto_id), None)
    if not progetto:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return progetto


# -- Re-export flussi ---------------------------------------------------------
def leggi_flussi_dichiarati() -> dict[str, dict]:
    """Legge i flussi rispettando il PERCORSO_FLUSSI configurato o patchato."""
    return dashboard_flussi.leggi_flussi_dichiarati(PERCORSO_FLUSSI)


calcola_fase_flusso = dashboard_flussi.calcola_fase_flusso
_calcola_fase_flusso = dashboard_flussi.calcola_fase_flusso

# -- Re-export servizi e stato postino ----------------------------------------
postino_attivo = dashboard_servizi.postino_attivo
imposta_postino = dashboard_servizi.imposta_postino
postino_headless_attivo = dashboard_servizi.postino_headless_attivo
imposta_postino_headless = dashboard_servizi.imposta_postino_headless


def _pid_vivo(pid: Any) -> bool:
    return dashboard_os.pid_vivo(pid)


def _trova_ultima_sessione_claude(percorso_progetto: Path) -> str | None:
    dir_sessioni = Path.home() / ".claude" / "sessions"
    if not dir_sessioni.exists():
        return None
    sessioni = []
    for f in dir_sessioni.glob("*.json"):
        try:
            dati = json.loads(f.read_text(encoding="utf-8"))
            cwd_sessione = Path(dati.get("cwd", ""))
            if cwd_sessione.resolve() != percorso_progetto.resolve():
                continue
            if not _pid_vivo(dati.get("pid")):
                continue
            sessioni.append((dati.get("startedAt", 0), dati.get("sessionId")))
        except Exception:
            pass
    if not sessioni:
        return None
    sessioni.sort(reverse=True)
    return sessioni[0][1]


# -- Re-export risvegli e helper interni --------------------------------------
_esegui_risveglio_os = dashboard_risvegli.esegui_risveglio_os
_genera_prompt_risveglio_con_llm = dashboard_risvegli.genera_prompt_risveglio_con_llm
_thread_pendenti_per_agente = dashboard_risvegli.thread_pendenti_per_agente
_percorso_stato_risvegli = dashboard_risvegli.percorso_stato_risvegli
_leggi_stato_risvegli = dashboard_risvegli.leggi_stato_risvegli
_scrivi_stato_risvegli = dashboard_risvegli.scrivi_stato_risvegli
_riavvia_dopo_risposta = interfaccia_api._riavvia_dopo_risposta

# -- Re-export controller e modelli Pydantic ----------------------------------
ProgettoInput = interfaccia_api.ProgettoInput
SentinellaInput = interfaccia_api.SentinellaInput
PostinoToggleInput = interfaccia_api.PostinoToggleInput
PostinoHeadlessToggleInput = interfaccia_api.PostinoHeadlessToggleInput
PostinoRevisioneInput = interfaccia_api.PostinoRevisioneInput

index = interfaccia_api.index
get_stato = interfaccia_api.get_stato
aggiungi_progetto = interfaccia_api.aggiungi_progetto
esegui_sentinella = interfaccia_api.esegui_sentinella
interpreta_output_sentinella = dashboard_os.interpreta_output_sentinella
lista_commit_progetto = interfaccia_api.lista_commit_progetto
eventi_commit_progetto = interfaccia_api.eventi_commit_progetto
flussi_dichiarati = interfaccia_api.flussi_dichiarati
bacheca_progetto = interfaccia_api.bacheca_progetto
esegui_risvegli_bacheca = interfaccia_api.esegui_risvegli_bacheca
bacheca_feed_progetto = interfaccia_api.bacheca_feed_progetto
bacheca_thread_progetto = interfaccia_api.bacheca_thread_progetto
riavvia_sistema = interfaccia_api.riavvia_sistema
toggle_postino = interfaccia_api.toggle_postino
toggle_postino_headless = interfaccia_api.toggle_postino_headless
richiedi_revisione_postino = interfaccia_api.richiedi_revisione_postino

# Verifica bind di sicurezza all'avvio
verifica_bind_sicuro()

# -- Istanza FastAPI e Composition Root ---------------------------------------
app = FastAPI(title="Orchestratore LLM — Dashboard")

# Montaggio file statici (CSS, JS)
app.mount("/static", StaticFiles(directory=dashboard_config.PERCORSO_STATIC), name="static")


@app.middleware("http")
async def _richiedi_chiave_su_bind_esposto(request: Request, call_next):
    """Nessun controllo extra su loopback. Su bind non-loopback verifica X-Orchestratore-Key."""
    if not bind_e_loopback(HOST_DASHBOARD):
        fornita = request.headers.get("X-Orchestratore-Key", "")
        if not secrets.compare_digest(fornita, CHIAVE_API_DASHBOARD):
            return JSONResponse({"errore": "non autorizzato"}, status_code=401)
    return await call_next(request)


# Registrazione route API
app.include_router(interfaccia_api.router)

# -- Watcher Postino Background -----------------------------------------------
_last_mtimes: dict[str, float] = {}

async def _watcher_postino_loop():
    while True:
        try:
            await asyncio.sleep(2.5)
            progetti = leggi_progetti()
            for proj in progetti:
                pid = proj.get("id")
                p_path_str = proj.get("percorso")
                if not pid or not p_path_str:
                    continue
                p_path = Path(p_path_str)
                if not p_path.exists() or not postino_attivo(p_path):
                    continue
                f_msg = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
                if not f_msg.exists():
                    continue
                try:
                    mtime = f_msg.stat().st_mtime
                except Exception:
                    continue
                last_mtime = _last_mtimes.get(pid)
                if last_mtime is not None and mtime > last_mtime:
                    _last_mtimes[pid] = mtime
                    try:
                        esegui_risvegli_bacheca(progetto_id=pid)
                    except Exception as ex:
                        print(f"[WATCHER POSTINO] Errore risveglio per {pid}: {ex}", file=sys.stderr)
                else:
                    _last_mtimes[pid] = mtime
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[WATCHER POSTINO] Errore nel ciclo del watcher: {e}", file=sys.stderr)


@app.on_event("startup")
async def _avvia_watcher_postino():
    in_test = (
        "unittest" in sys.modules
        or any("unittest" in arg or "pytest" in arg for arg in sys.argv)
        or os.environ.get("TESTING") == "true"
    )
    if not in_test:
        asyncio.create_task(_watcher_postino_loop())


if __name__ == "__main__":
    tentativi_rimasti = 20
    while True:
        try:
            uvicorn.run(app, host=HOST_DASHBOARD, port=PORTA_DASHBOARD)
            break
        except SystemExit:
            tentativi_rimasti -= 1
            if tentativi_rimasti <= 0:
                raise
            time.sleep(0.5)
