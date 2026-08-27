#!/usr/bin/env python3
"""Definizione dei router FastAPI, modelli Pydantic e controller HTTP per la Dashboard (Lotto E).

Isola le definizioni delle route HTTP e la traduzione dei codici di errore (400/404/500/504)
dai sottodomini di dominio e dalla composition root (interfaccia.py).
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

import bacheca
import dashboard_os
import dashboard_progetti
import dashboard_risvegli
import dashboard_servizi
import postino
import profili_operativi

router = APIRouter()

# -- Modelli Pydantic ---------------------------------------------------------

class ProgettoInput(BaseModel):
    nome: str
    percorso: str


class SentinellaInput(BaseModel):
    progetto_id: str
    comando: str


class PostinoToggleInput(BaseModel):
    progetto_id: str
    attivo: bool


class PostinoHeadlessToggleInput(BaseModel):
    progetto_id: str
    attivo: bool


class PostinoProfiloInput(BaseModel):
    progetto_id: str
    profilo: str


class PostinoRevisioneInput(BaseModel):
    progetto_id: str
    agente: str
    thread_id: str


# -- Controller e Route Handlers ----------------------------------------------

@router.get("/", response_class=HTMLResponse)
def index():
    import interfaccia
    if not interfaccia.PERCORSO_HTML.exists():
        raise HTTPException(status_code=404, detail="File interfaccia.html non trovato")
    return FileResponse(interfaccia.PERCORSO_HTML)


@router.get("/api/stato")
def get_stato(pagina: int = 1, per_pagina: int = 50):
    import interfaccia
    progetti = interfaccia.leggi_progetti()
    return dashboard_servizi.ottieni_stato(pagina=pagina, per_pagina=per_pagina, progetti=progetti)


@router.post("/api/progetti")
def aggiungi_progetto(proj: ProgettoInput):
    import interfaccia
    p_path = Path(proj.percorso).resolve()
    if not p_path.exists() or not p_path.is_dir():
        raise HTTPException(status_code=400, detail="Il percorso indicato non esiste o non è una cartella")

    progetti = interfaccia.leggi_progetti()
    p_id = proj.nome.lower().replace(" ", "_").replace("-", "_")
    p_id = "".join([c for c in p_id if c.isalnum() or c == "_"])

    # Previene duplicati
    if any(p["id"] == p_id or Path(p["percorso"]).resolve() == p_path for p in progetti):
        raise HTTPException(status_code=400, detail="Progetto con questo nome o percorso già registrato")

    try:
        interfaccia.integra_progetto(p_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integrazione automatica fallita: {e}")

    nuovo = {
        "id": p_id,
        "nome": proj.nome,
        "percorso": str(p_path)
    }
    progetti.append(nuovo)
    interfaccia.salva_progetti(progetti)
    return {"status": "ok", "progetto": nuovo}


@router.post("/api/sentinella")
def esegui_sentinella(input_data: SentinellaInput):
    import interfaccia
    progetti = interfaccia.leggi_progetti()
    target = next((p for p in progetti if p["id"] == input_data.progetto_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    p_path = Path(target["percorso"])
    percorso_comandi = dashboard_progetti.percorso_comandi_progetto(p_path)
    if not percorso_comandi.exists():
        raise HTTPException(
            status_code=400,
            detail="Nessuna configurazione comandi trovata nel progetto (config/comandi.json o comandi.esempio.json)",
        )
    percorso_registro = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"

    try:
        codice, dati_output = dashboard_os.esegui_sentinella_subprocess(
            script_sentinella=interfaccia.SCRIPT_SENTINELLA_CENTRALE,
            comando=input_data.comando,
            percorso_comandi=percorso_comandi,
            percorso_registro=percorso_registro,
            cwd_path=p_path,
            timeout_secondi=180,
        )
        return {
            "status": "success" if codice == 0 else "failed",
            "returncode": codice,
            "dati": dati_output,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Esecuzione del comando andata in timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'esecuzione del comando: {e}")


@router.get("/api/commit/lista")
def lista_commit_progetto(progetto_id: str = "orchestratore", limite: int = 20):
    import interfaccia
    progetti = interfaccia.leggi_progetti()
    return dashboard_servizi.ottieni_lista_commit(progetto_id=progetto_id, limite=limite, progetti=progetti)


@router.get("/api/commit/eventi")
def eventi_commit_progetto(progetto_id: str, hash: str):
    import interfaccia
    progetti = interfaccia.leggi_progetti()
    return dashboard_servizi.ottieni_eventi_commit(progetto_id=progetto_id, hash_commit=hash, progetti=progetti)


@router.get("/api/flussi")
def flussi_dichiarati():
    import interfaccia
    return {"flussi": interfaccia.leggi_flussi_dichiarati()}


@router.get("/api/bacheca")
def bacheca_progetto(progetto_id: str = "orchestratore"):
    import interfaccia
    progetti = interfaccia.leggi_progetti()
    return dashboard_servizi.ottieni_bacheca_progetto(progetto_id=progetto_id, progetti=progetti)


@router.post("/api/bacheca/risvegli")
def esegui_risvegli_bacheca(progetto_id: str = "orchestratore"):
    import interfaccia
    progetto = interfaccia._progetto_o_404(progetto_id)
    percorso_progetto = Path(progetto["percorso"])
    messaggi, errore = bacheca.leggi_messaggi_progetto(percorso_progetto)
    if errore:
        return {"progetto_id": progetto_id, "errore": errore, "risvegli": []}

    inizializzato, risvegli = dashboard_risvegli.calcola_ed_esegui_risvegli(percorso_progetto, messaggi)
    return {"progetto_id": progetto_id, "inizializzato": inizializzato, "risvegli": risvegli}


@router.get("/api/bacheca/feed")
def bacheca_feed_progetto(progetto_id: str = "orchestratore", limite: int = 50):
    import interfaccia
    progetti = interfaccia.leggi_progetti()
    return dashboard_servizi.ottieni_bacheca_feed(progetto_id=progetto_id, limite=limite, progetti=progetti)


@router.get("/api/bacheca/thread")
def bacheca_thread_progetto(progetto_id: str, thread_id: str):
    import interfaccia
    progetti = interfaccia.leggi_progetti()
    return dashboard_servizi.ottieni_bacheca_thread(progetto_id=progetto_id, thread_id=thread_id, progetti=progetti)


def _riavvia_dopo_risposta() -> None:
    import interfaccia
    time.sleep(0.5)
    dashboard_os.avvia_processo_sostituto(
        script_interfaccia=interfaccia.SCRIPT_INTERFACCIA,
        radice=interfaccia.RADICE,
    )
    import os
    os._exit(0)


@router.post("/api/sistema/riavvia")
def riavvia_sistema():
    threading.Thread(target=_riavvia_dopo_risposta, daemon=True).start()
    return {"status": "riavvio_in_corso"}


@router.post("/api/bacheca/postino/profilo")
def imposta_postino_profilo(payload: PostinoProfiloInput):
    import interfaccia
    progetto = interfaccia._progetto_o_404(payload.progetto_id)
    p_path = Path(progetto["percorso"])

    try:
        dto = profili_operativi.imposta(p_path, payload.profilo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Housekeeping: pulizia dei vecchi marker legacy su disco
    for marker in ("POSTINO_ATTIVO", "POSTINO_HEADLESS_ATTIVO"):
        f_marker = p_path / "dati_locali" / "orchestrazione" / marker
        if f_marker.exists():
            try:
                f_marker.unlink()
            except Exception:
                pass

    garanzie = profili_operativi.garanzie(dto)
    descrizione = profili_operativi.istruzione_interattiva(dto)
    try:
        limiti = postino.carica_limiti(p_path)
    except Exception:
        limiti = {}

    return {
        "status": "ok",
        "progetto_id": payload.progetto_id,
        "profilo": dto,
        "garanzie_per_agente": garanzie,
        "descrizione": descrizione,
        "limiti_effettivi": limiti,
    }


@router.post("/api/bacheca/postino/toggle")
def toggle_postino(payload: PostinoToggleInput):
    import interfaccia
    progetto = interfaccia._progetto_o_404(payload.progetto_id)
    stato = interfaccia.imposta_postino(Path(progetto["percorso"]), payload.attivo)
    return {"progetto_id": payload.progetto_id, "postino_attivo": stato}


@router.post("/api/bacheca/postino/headless/toggle")
def toggle_postino_headless(payload: PostinoHeadlessToggleInput):
    import interfaccia
    progetto = interfaccia._progetto_o_404(payload.progetto_id)
    stato = interfaccia.imposta_postino_headless(Path(progetto["percorso"]), payload.attivo)
    return {"progetto_id": payload.progetto_id, "postino_headless_attivo": stato}


@router.post("/api/bacheca/postino/revisione")
def richiedi_revisione_postino(payload: PostinoRevisioneInput):
    import interfaccia
    progetto = interfaccia._progetto_o_404(payload.progetto_id)
    if payload.agente not in interfaccia.AGENTI_BACHECA_DASHBOARD:
        raise HTTPException(status_code=400, detail=f"agente non valido: {payload.agente}")
    percorso_progetto = Path(progetto["percorso"])
    profilo_corrente = profili_operativi.carica(percorso_progetto)
    if not profili_operativi.dispatch_abilitato(profilo_corrente):
        return {"esito": "bloccato", "motivo": "dispatch_profilo_disattivato"}
    esito = postino.dispatch(
        percorso_progetto, payload.agente, payload.thread_id, modo="revisione",
    )
    return esito
