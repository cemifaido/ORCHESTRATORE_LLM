#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import registro
import triage_locale


_PERCORSO_REAL = Path("config") / "comandi.json"
_PERCORSO_ESEMPIO = Path("config") / "comandi.esempio.json"
PERCORSO_COMANDI_PREDEFINITO = _PERCORSO_REAL if _PERCORSO_REAL.exists() else _PERCORSO_ESEMPIO
PERCORSO_REGISTRO_PREDEFINITO = Path("dati_locali") / "orchestrazione" / "eventi.jsonl"
PERCORSO_LOG_PREDEFINITO = Path("dati_locali") / "orchestrazione" / "log_comandi"


def adesso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def carica_comandi(percorso: Path) -> dict:
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    if dati.get("versione_schema") != 1:
        raise ValueError("versione_schema dei comandi non supportata")
    comandi = dati.get("comandi")
    if not isinstance(comandi, dict):
        raise ValueError("configurazione comandi non valida")
    return comandi


def tronca(testo: str, limite: int) -> str:
    if len(testo) <= limite:
        return testo
    return testo[:limite] + "\n...[output troncato]..."


def salva_log_output(id_evento: str, output: str, cartella_log: Path = PERCORSO_LOG_PREDEFINITO) -> dict:
    cartella_log.mkdir(parents=True, exist_ok=True)
    percorso = cartella_log / f"{id_evento}.log"
    percorso.write_text(output, encoding="utf-8", newline="\n")
    return {
        "log_output": str(percorso),
        "sha256_output": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "estratto_output": tronca(output, 2000),
    }


def verifica_connessione(indirizzo: str) -> bool:
    try:
        if indirizzo.startswith("http://") or indirizzo.startswith("https://"):
            parsed = urlparse(indirizzo)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        elif ":" in indirizzo:
            host, _, porta = indirizzo.rpartition(":")
            port = int(porta)
        else:
            host = indirizzo
            port = 80

        with socket.create_connection((host, port), timeout=2.0):
            return True
    except Exception:
        return False


def esegui(nome: str, comandi: dict, *, radice_progetto: Path | None = None) -> tuple[str, int, int, str]:
    if nome not in comandi:
        raise ValueError(f"comando non ammesso: {nome}")
    configurazione = comandi[nome]

    # Pre-check di rete/infrastruttura
    risorse = configurazione.get("verifiche_connessione", [])
    if isinstance(risorse, list) and risorse:
        for risorsa in risorse:
            if not verifica_connessione(risorsa):
                messaggio = (
                    f"[Errore Ambiente] La risorsa di rete '{risorsa}' non è raggiungibile. "
                    "Assicurati che il server sia acceso e in ascolto prima di lanciare il test."
                )
                return "errore_ambiente", 111, 0, messaggio

    argomenti = configurazione.get("argomenti")
    if not isinstance(argomenti, list) or not argomenti:
        raise ValueError(f"argomenti non validi per comando {nome}")
    cartella = Path(configurazione.get("cartella", ".")).resolve()
    if radice_progetto is not None and not cartella.is_relative_to(radice_progetto.resolve()):
        # comandi.json e' trattato come dato di configurazione del progetto, ma
        # non e' firmato/verificato: senza questo controllo un file malevolo
        # potrebbe far girare comandi arbitrari fuori dalla cartella del
        # progetto (bug reale trovato in revisione di sicurezza, 2026-08-25).
        raise ValueError(f"cartella fuori dalla radice del progetto: {cartella}")
    timeout = int(configurazione.get("timeout_secondi", 60))
    limite_output = int(configurazione.get("limite_output_caratteri", 20000))

    inizio = time.perf_counter()
    ambiente = os.environ.copy()
    # Impedisce a Git di risalire oltre la cartella configurata quando il comando
    # gira in una directory che non è un repository. Evita output enormi dal parent.
    ambiente["GIT_CEILING_DIRECTORIES"] = str(cartella.parent)

    # Feedback visibile: l'output viene catturato (buffer), quindi senza questo la console
    # resta muta per tutta la durata del comando e sembra bloccata.
    print(f"[sentinella] avvio '{nome}' (timeout {timeout}s, output catturato)...", file=sys.stderr, flush=True)

    try:
        completato = subprocess.run(
            argomenti,
            cwd=cartella,
            text=True,
            stdin=subprocess.DEVNULL,  # niente stdin: un eventuale prompt fallisce subito invece di appendere
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            shell=False,
            check=False,
            env=ambiente,
        )
        codice = completato.returncode
        output = completato.stdout or ""
        esito = "superato" if codice == 0 else "fallito"
    except subprocess.TimeoutExpired as errore:
        codice = 124
        output_parziale = errore.stdout or ""
        output = output_parziale.decode(errors="replace") if isinstance(output_parziale, bytes) else output_parziale
        esito = "timeout"

    latenza_ms = int((time.perf_counter() - inizio) * 1000)
    return esito, codice, latenza_ms, tronca(output, limite_output)


def determina_stato(esito: str) -> str:
    if esito == "superato":
        return "passato"
    if esito == "errore_ambiente":
        return "errore_ambiente"
    return "fallito"


def classifica_deterministica(esito: str, codice: int, output: str) -> dict[str, Any] | None:
    """Classifica output ripetitivi con regole deterministicamente verificabili.

    Ritorna None quando l'output e' ambiguo: in quel caso, se richiesto, si passa al
    modello locale. La sentinella non usa mai questa funzione per "spiegare" un bug:
    decide solo se il risultato e' routine o se va scalato.
    """
    testo = output.strip()
    testo_minuscolo = testo.lower()
    segnali_sospetti = (
        "traceback",
        "assertionerror",
        "exception",
        "failed",
        "failure",
        "error",
        "warning",
        "deprecated",
        "errore",
        "fallito",
    )

    if esito == "superato" and codice == 0:
        if not testo:
            return {
                "esito": "routine",
                "motivo": "codice 0 e output vuoto: esito ripetitivo deterministico",
                "token_totali": None,
            }
        if not any(segnale in testo_minuscolo for segnale in segnali_sospetti):
            return {
                "esito": "routine",
                "motivo": "codice 0 senza segnali di errore o warning",
                "token_totali": None,
            }
        return None

    if esito in {"fallito", "timeout", "errore_ambiente"}:
        if esito == "timeout":
            return {"esito": "escalation", "motivo": "timeout del comando", "token_totali": None}
        if esito == "errore_ambiente":
            return {"esito": "escalation", "motivo": "errore ambiente pre-gate", "token_totali": None}
        if not testo:
            return {
                "esito": "escalation",
                "motivo": f"codice {codice} senza output diagnostico",
                "token_totali": None,
            }
        if re.search(r"\b(FAILED|ERROR|Traceback|AssertionError)\b", testo):
            return {
                "esito": "escalation",
                "motivo": "fallimento riconosciuto da marker standard nei test",
                "token_totali": None,
            }
    return None


def registra_triage(
    *,
    risultato: dict[str, Any],
    metodo: str,
    percorso_registro: Path,
    id_compito: str,
    comando: str,
    esito_gate: str,
    codice: int,
    latenza_ms: int,
) -> dict[str, Any]:
    id_evento = str(uuid.uuid4())
    evento = {
        "versione_schema": 1,
        "id_evento": id_evento,
        "timestamp": adesso_utc(),
        "id_compito": id_compito,
        "agente": "locale",
        "tipo_compito": "monitoraggio",
        "stato": "passato" if risultato["esito"] == "routine" else "da_rivedere",
        "esito_gate": "non_eseguito",
        "verdetto_umano": "non_revisionato",
        "costo_stimato_usd": 0.0,
        "origine_costo": "misurato",
        "latenza_ms": latenza_ms,
        "regole_incluse": [metodo],
        "file_modificati": [],
        "note": f"[{risultato['esito']}] {risultato['motivo']}",
        "metadati": {
            "metodo": metodo,
            "comando": comando,
            "codice": codice,
            "esito_gate_collegato": esito_gate,
            "token_totali": risultato.get("token_totali"),
        },
    }
    registro.aggiungi_evento(percorso_registro, evento)
    return evento


def classifica_con_guardia_locale(esito: str, codice: int, output: str, contesto: str) -> tuple[dict[str, Any], str, int]:
    inizio = time.perf_counter()
    risultato = classifica_deterministica(esito, codice, output)
    if risultato is not None:
        return risultato, "triage_deterministico", int((time.perf_counter() - inizio) * 1000)

    risultato = triage_locale.classifica(output, contesto=contesto)
    return risultato, "triage_locale", int((time.perf_counter() - inizio) * 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinella deterministica: esegue solo comandi whitelistati")
    parser.add_argument("comando")
    parser.add_argument("--config", default=str(PERCORSO_COMANDI_PREDEFINITO))
    parser.add_argument("--registro", default=str(PERCORSO_REGISTRO_PREDEFINITO))
    parser.add_argument("--id-compito", default="gate")
    parser.add_argument(
        "--triage-locale",
        action="store_true",
        help="registra una classificazione routine/escalation: pattern deterministici prima, LLM locale solo se ambiguo",
    )
    args = parser.parse_args()

    try:
        percorso_config = Path(args.config).resolve()
        comandi = carica_comandi(percorso_config)
        # config/comandi.json vive sempre dentro <progetto>/config/ per
        # convenzione del progetto (vedi docs/ORCHESTRAZIONE_LAVORATORI.md):
        # risalire due livelli da' la radice del progetto target.
        radice_progetto = percorso_config.parent.parent
        esito, codice, latenza_ms, output = esegui(args.comando, comandi, radice_progetto=radice_progetto)
    except Exception as errore:
        print(f"errore sentinella: {errore}", file=sys.stderr)
        return 2

    id_evento = str(uuid.uuid4())
    metadati_output = salva_log_output(id_evento, output)
    evento = {
        "versione_schema": 1,
        "id_evento": id_evento,
        "timestamp": adesso_utc(),
        "id_compito": args.id_compito,
        "agente": "locale",
        "tipo_compito": "monitoraggio" if esito == "superato" else "errore_test",
        "stato": determina_stato(esito),
        "esito_gate": esito,
        "verdetto_umano": "non_revisionato",
        "costo_stimato_usd": 0.0,
        "origine_costo": "misurato",
        "latenza_ms": latenza_ms,
        "regole_incluse": ["whitelist_comandi", "timeout", "limite_output"],
        "file_modificati": [],
        "note": f"comando={args.comando}; codice={codice}",
        "metadati": metadati_output,
    }
    registro.aggiungi_evento(Path(args.registro), evento)

    evento_triage = None
    if args.triage_locale:
        risultato_triage, metodo_triage, latenza_triage_ms = classifica_con_guardia_locale(
            esito,
            codice,
            output,
            contesto=f"sentinella comando={args.comando}; esito_gate={esito}; codice={codice}",
        )
        evento_triage = registra_triage(
            risultato=risultato_triage,
            metodo=metodo_triage,
            percorso_registro=Path(args.registro),
            id_compito=args.id_compito,
            comando=args.comando,
            esito_gate=esito,
            codice=codice,
            latenza_ms=latenza_triage_ms,
        )

    risposta = {"esito": esito, "codice": codice, "latenza_ms": latenza_ms, "output": output, "evento": evento}
    if evento_triage is not None:
        risposta["triage"] = evento_triage
    print(json.dumps(risposta, ensure_ascii=False, indent=2))
    return 0 if esito == "superato" else 1


if __name__ == "__main__":
    raise SystemExit(main())
