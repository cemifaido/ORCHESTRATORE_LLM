#!/usr/bin/env python3
"""Servizi applicativi di sola lettura e proiezioni per la Dashboard.

Modulo estratto da interfaccia.py nel Lotto D (backlog architetturale D2).
Raccoglie i casi d'uso puri/semipuri di lettura: stato aggregato, commit replay,
proiezione bacheca, feed e thread history.
"""
from __future__ import annotations

import sys
from math import ceil
from pathlib import Path

from fastapi import HTTPException

import bacheca
import commit_replay
import dashboard_config
import dashboard_flussi
import dashboard_os
import dashboard_progetti
import motore_flusso
import registro

AGENTI_BACHECA_DASHBOARD = dashboard_config.AGENTI_BACHECA_DASHBOARD


def postino_attivo(percorso_progetto: Path) -> bool:
    """Restituisce True se il postino automatico e' ATTIVO per il progetto.
    Richiede la presenza esplicita del file dati_locali/orchestrazione/POSTINO_ATTIVO.
    Default: SPENTO (False, fail-closed).
    """
    pa = percorso_progetto / "dati_locali" / "orchestrazione" / "POSTINO_ATTIVO"
    return pa.exists()


def imposta_postino(percorso_progetto: Path, attivo: bool) -> bool:
    """Attiva o disattiva il postino automatico creando o rimuovendo il file POSTINO_ATTIVO."""
    pa = percorso_progetto / "dati_locali" / "orchestrazione" / "POSTINO_ATTIVO"
    pa.parent.mkdir(parents=True, exist_ok=True)
    if attivo:
        if not pa.exists():
            try:
                pa.write_text("POSTINO_ATTIVO=1\n", encoding="utf-8")
            except Exception as e:
                print(f"[POSTINO TOGGLE] Impossibile creare {pa}: {e}", file=sys.stderr)
    else:
        if pa.exists():
            try:
                pa.unlink()
            except Exception as e:
                print(f"[POSTINO TOGGLE] Impossibile rimuovere {pa}: {e}", file=sys.stderr)
    return postino_attivo(percorso_progetto)


def postino_headless_attivo(percorso_progetto: Path) -> bool:
    """Restituisce True se il DISPATCH HEADLESS e' attivo per il progetto.
    Richiede la presenza esplicita del file dati_locali/orchestrazione/POSTINO_HEADLESS_ATTIVO.
    Default: SPENTO (fail-closed).
    """
    ph = percorso_progetto / "dati_locali" / "orchestrazione" / "POSTINO_HEADLESS_ATTIVO"
    return ph.exists()


def imposta_postino_headless(percorso_progetto: Path, attivo: bool) -> bool:
    """Attiva o disattiva il dispatch headless creando o rimuovendo POSTINO_HEADLESS_ATTIVO."""
    ph = percorso_progetto / "dati_locali" / "orchestrazione" / "POSTINO_HEADLESS_ATTIVO"
    ph.parent.mkdir(parents=True, exist_ok=True)
    if attivo:
        if not ph.exists():
            try:
                ph.write_text("POSTINO_HEADLESS_ATTIVO=1\n", encoding="utf-8")
            except Exception as e:
                print(f"[POSTINO TOGGLE] Impossibile creare {ph}: {e}", file=sys.stderr)
    else:
        if ph.exists():
            try:
                ph.unlink()
            except Exception as e:
                print(f"[POSTINO TOGGLE] Impossibile rimuovere {ph}: {e}", file=sys.stderr)
    return postino_headless_attivo(percorso_progetto)


def ottieni_stato(
    pagina: int = 1,
    per_pagina: int = 50,
    progetti: list[dict] | None = None,
) -> dict:
    """Calcola lo stato globale aggregato di tutti i progetti registrati."""
    if progetti is None:
        progetti = dashboard_progetti.leggi_progetti()
    progetti_arricchiti = [dashboard_progetti.arricchisci_progetto(proj) for proj in progetti]

    tutti_eventi, progetto_stats = registro.carica_eventi_multi_progetto(progetti)
    tutti_eventi.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    agente_stats = registro.metriche(tutti_eventi)
    livello_stats = registro.metriche_per_livello(tutti_eventi)

    per_pagina = max(1, per_pagina)
    pagine_totali = max(1, ceil(len(tutti_eventi) / per_pagina))
    pagina = min(max(1, pagina), pagine_totali)
    inizio = (pagina - 1) * per_pagina
    eventi_pagina = tutti_eventi[inizio:inizio + per_pagina]

    return {
        "progetti": progetti_arricchiti,
        "globali": {
            "progetti_totali": len(progetti),
            "eventi_totali": len(tutti_eventi),
            "latenza_totale": sum(int(ev.get("latenza_ms") or 0) for ev in tutti_eventi)
        },
        "progetto_stats": progetto_stats,
        "agente_stats": agente_stats,
        "livello_stats": livello_stats,
        "eventi": eventi_pagina,
        "paginazione": {
            "pagina": pagina,
            "per_pagina": per_pagina,
            "pagine_totali": pagine_totali,
            "eventi_totali": len(tutti_eventi),
        },
    }


def ottieni_lista_commit(
    progetto_id: str = "orchestratore",
    limite: int = 20,
    progetti: list[dict] | None = None,
) -> dict:
    """Recupera la lista dei commit recenti con metriche di interazione."""
    progetto = dashboard_progetti.progetto_o_404(progetto_id, progetti=progetti)
    p_path = Path(progetto["percorso"])
    p_reg = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
    try:
        commit = commit_replay.lista_commit(p_path, limite=limite, percorso_registro=p_reg)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"progetto_id": progetto_id, "commit": commit}


def ottieni_eventi_commit(
    progetto_id: str,
    hash_commit: str,
    progetti: list[dict] | None = None,
) -> dict:
    """Recupera gli eventi e la stima di risparmio per un commit specifico."""
    progetto = dashboard_progetti.progetto_o_404(progetto_id, progetti=progetti)
    p_path = Path(progetto["percorso"])
    try:
        inizio, fine = commit_replay.finestra_temporale_commit(p_path, hash_commit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    percorso_registro = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
    eventi = commit_replay.eventi_nella_finestra(percorso_registro, inizio, fine)
    stima = commit_replay.stima_risparmio(eventi)

    return {
        "progetto_id": progetto_id,
        "hash": hash_commit,
        "eventi": eventi,
        "stima_risparmio": stima,
    }


def ottieni_bacheca_progetto(
    progetto_id: str = "orchestratore",
    progetti: list[dict] | None = None,
) -> dict:
    """Calcola lo stato della bacheca, thread riepilogativi, file occupati e pratiche sospese."""
    progetto = dashboard_progetti.progetto_o_404(progetto_id, progetti=progetti)
    p_path = Path(progetto["percorso"])
    messaggi, errore = bacheca.leggi_messaggi_progetto(p_path)
    if errore:
        return {
            "progetto_id": progetto_id,
            "errore": errore,
            "thread": [],
            "occupati": {},
            "pending_per_agente": {agente: 0 for agente in AGENTI_BACHECA_DASHBOARD},
            "pratiche_sospese": [],
            "flussi": dashboard_flussi.leggi_flussi_dichiarati(),
            "claude_session_id": None,
            "postino_attivo": postino_attivo(p_path),
            "postino_headless_attivo": postino_headless_attivo(p_path),
        }

    eventi, _ = registro.leggi_eventi_progetto(p_path)
    flussi = dashboard_flussi.leggi_flussi_dichiarati()
    flusso_standard = flussi.get("compito_standard", {})

    thread_ids = sorted({m["thread_id"] for m in messaggi})
    thread_riepilogo = []
    pratiche_sospese = []
    pending_per_agente = {agente: 0 for agente in AGENTI_BACHECA_DASHBOARD}

    for tid in thread_ids:
        ultimo = bacheca._messaggi_del_thread(messaggi, tid)[-1]
        aspetta = bacheca.destinatari_pendenti(messaggi, tid)
        for agente in AGENTI_BACHECA_DASHBOARD:
            if agente in aspetta:
                pending_per_agente[agente] += 1

        stato_flusso = motore_flusso.deriva_stato(flusso_standard, eventi, messaggi, tid)
        fase_flusso = stato_flusso["fase"] if stato_flusso["stato"] == "attivo" else (
            "chiusura" if stato_flusso["stato"] == "completato" else None
        )

        thread_riepilogo.append({
            "thread_id": tid,
            "stato": bacheca.stato_thread(messaggi, tid),
            "ultimo_mittente": ultimo["mittente"],
            "ultimo_tipo": ultimo["tipo"],
            "ultimo_testo": ultimo["testo"][:200],
            "aspetta": aspetta,
            "verdetto_umano": bacheca.verdetto_umano_corrente(messaggi, tid),
            "file_modificati": ultimo["file_modificati"],
            "fase_flusso": fase_flusso,
            "stato_flusso": stato_flusso,
        })

        chk = bacheca.checkpoint_ripristinabile_attivo(messaggi, tid)
        if chk and chk.get("ripresa"):
            rip = chk["ripresa"]
            pratiche_sospese.append({
                "thread_id": tid,
                "id_messaggio": chk.get("id_messaggio"),
                "mittente": chk.get("mittente"),
                "timestamp": chk.get("timestamp"),
                "oggetto_atteso": rip.get("oggetto_atteso"),
                "attende": rip.get("attende"),
                "azioni_per_esito": rip.get("azioni_per_esito", {}),
                "contesto_minimo": rip.get("contesto_minimo", {}),
                "verdetto_umano": bacheca.verdetto_umano_corrente(messaggi, tid),
                "testo": chk.get("testo", "")[:200],
            })

    occupati = {
        f: {
            "agente": info["agente"],
            "thread_id": info["thread_id"],
            "scadenza": info["scadenza"].isoformat() if info["scadenza"] else None,
        }
        for f, info in bacheca.file_occupati(messaggi).items()
    }

    return {
        "progetto_id": progetto_id,
        "thread": thread_riepilogo,
        "occupati": occupati,
        "pending_per_agente": pending_per_agente,
        "pratiche_sospese": pratiche_sospese,
        "flussi": dashboard_flussi.leggi_flussi_dichiarati(),
        "claude_session_id": dashboard_os.trova_ultima_sessione_claude(p_path),
        "postino_attivo": postino_attivo(p_path),
        "postino_headless_attivo": postino_headless_attivo(p_path),
    }


def ottieni_bacheca_feed(
    progetto_id: str = "orchestratore",
    limite: int = 50,
    progetti: list[dict] | None = None,
) -> dict:
    """Restituisce gli ultimi messaggi del feed in ordine cronologico."""
    limite = max(1, min(limite, 200))
    progetto = dashboard_progetti.progetto_o_404(progetto_id, progetti=progetti)
    messaggi, errore = bacheca.leggi_messaggi_progetto(Path(progetto["percorso"]))
    if errore:
        return {"progetto_id": progetto_id, "errore": errore, "messaggi": []}
    messaggi_ordinati = sorted(messaggi, key=lambda m: m["timestamp"])
    return {"progetto_id": progetto_id, "messaggi": messaggi_ordinati[-limite:]}


def ottieni_bacheca_thread(
    progetto_id: str,
    thread_id: str,
    progetti: list[dict] | None = None,
) -> dict:
    """Restituisce la cronologia completa di un thread specifico."""
    progetto = dashboard_progetti.progetto_o_404(progetto_id, progetti=progetti)
    messaggi, errore = bacheca.leggi_messaggi_progetto(Path(progetto["percorso"]))
    if errore:
        raise HTTPException(status_code=500, detail=errore)
    cronologia = bacheca._messaggi_del_thread(messaggi, thread_id)
    if not cronologia:
        raise HTTPException(status_code=404, detail="Thread non trovato")
    return {"progetto_id": progetto_id, "thread_id": thread_id, "messaggi": cronologia}
