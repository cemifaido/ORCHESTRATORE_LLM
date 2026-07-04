#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import registro


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
        else:
            parti = indirizzo.split(":")
            host = parti[0]
            port = int(parti[1]) if len(parti) > 1 else 80
            
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except Exception:
        return False


def esegui(nome: str, comandi: dict) -> tuple[str, int, int, str]:
    if nome not in comandi:
        raise ValueError(f"comando non ammesso: {nome}")
    configurazione = comandi[nome]
    
    # Pre-check di rete/infrastruttura
    risorse = configurazione.get("verifiche_connessione", [])
    if isinstance(risorse, list) and risorse:
        for risorsa in risorse:
            if not verifica_connessione(risorsa):
                messaggio = f"[Errore Ambiente] La risorsa di rete '{risorsa}' non è raggiungibile. Assicurati che il server sia acceso e in ascolto prima di lanciare il test."
                return "errore_ambiente", 111, 0, messaggio

    argomenti = configurazione.get("argomenti")
    if not isinstance(argomenti, list) or not argomenti:
        raise ValueError(f"argomenti non validi per comando {nome}")
    cartella = Path(configurazione.get("cartella", ".")).resolve()
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
        output = errore.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        esito = "timeout"

    latenza_ms = int((time.perf_counter() - inizio) * 1000)
    return esito, codice, latenza_ms, tronca(output, limite_output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinella deterministica: esegue solo comandi whitelistati")
    parser.add_argument("comando")
    parser.add_argument("--config", default=str(PERCORSO_COMANDI_PREDEFINITO))
    parser.add_argument("--registro", default=str(PERCORSO_REGISTRO_PREDEFINITO))
    parser.add_argument("--id-compito", default="gate")
    args = parser.parse_args()

    try:
        comandi = carica_comandi(Path(args.config))
        esito, codice, latenza_ms, output = esegui(args.comando, comandi)
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
        "stato": "passato" if esito == "superato" else "fallito",
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
    print(json.dumps({"esito": esito, "codice": codice, "latenza_ms": latenza_ms, "output": output, "evento": evento}, ensure_ascii=False, indent=2))
    return 0 if esito == "superato" else 1


if __name__ == "__main__":
    raise SystemExit(main())
