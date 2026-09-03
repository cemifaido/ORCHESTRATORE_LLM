#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
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

import console_utf8
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


ESEGUIBILI_AMMESSI = frozenset({"git", "python", "python3", "npm", "npx", "node"})
_SUFFISSI_ESEGUIBILE_WINDOWS = (".exe", ".cmd", ".bat")


def _basename_eseguibile(comando: str) -> str:
    nome = Path(comando).name.lower()
    for suffisso in _SUFFISSI_ESEGUIBILE_WINDOWS:
        if nome.endswith(suffisso):
            return nome[: -len(suffisso)]
    return nome


HOST_LOCALI_NOTI = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
PATTERN_SEGRETI = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{30,}"),
    re.compile(r"(?i)(bearer)\s+([A-Za-z0-9_\-\.]{12,})"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|auth[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{12,})['\"]?"),
]


def redigi_segreti(testo: str) -> str:
    """Redige pattern che sembrano chiavi, token o segreti prima di salvare il log
    (guardrail L1, revisione sicurezza 2026-08-25)."""
    risultato = testo
    for pattern in PATTERN_SEGRETI:
        def _rimpiazza(m: re.Match) -> str:
            if m.lastindex and m.lastindex >= 2:
                valore = m.group(2)
                return m.group(0).replace(valore, "[REDACTED_SECRET]")
            return "[REDACTED_SECRET]"
        risultato = pattern.sub(_rimpiazza, risultato)
    return risultato


def _is_host_locale(host: str) -> bool:
    """Verifica se l'host e' locale (loopback). Restringe le sonde di rete TCP a localhost
    per prevenire SSRF / port scanning di rete interna tramite comandi.json malevoli
    (guardrail M5, revisione sicurezza 2026-08-25)."""
    if host.lower() in HOST_LOCALI_NOTI:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_unspecified
    except ValueError:
        return False


def salva_log_output(id_evento: str, output: str, cartella_log: Path = PERCORSO_LOG_PREDEFINITO) -> dict:
    cartella_log.mkdir(parents=True, exist_ok=True)
    percorso = cartella_log / f"{id_evento}.log"
    output_redatto = redigi_segreti(output)
    percorso.write_text(output_redatto, encoding="utf-8", newline="\n")
    return {
        "log_output": str(percorso),
        "sha256_output": hashlib.sha256(output_redatto.encode("utf-8")).hexdigest(),
        "estratto_output": tronca(output_redatto, 2000),
    }


def verifica_connessione(indirizzo: str) -> bool:
    """Sonda (TCP connect) la disponibilita' di un servizio locale. Rifiuta host
    esterni per prevenire port scanning / SSRF."""
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

        if not _is_host_locale(host):
            return False

        with socket.create_connection((host, port), timeout=2.0):
            return True
    except Exception:
        return False


def esegui(nome: str, comandi: dict, *, radice_progetto: Path) -> tuple[str, int, int, str]:
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
    eseguibile = _basename_eseguibile(str(argomenti[0]))
    if eseguibile not in ESEGUIBILI_AMMESSI:
        # comandi.json non e' firmato/verificato: senza allowlist un file
        # malevolo potrebbe far girare un binario arbitrario, non solo
        # limitato alla cartella del progetto (residuo C2, revisione
        # sicurezza v3, 2026-08-26).
        raise ValueError(f"eseguibile non ammesso: {argomenti[0]}")
    cartella = Path(configurazione.get("cartella", ".")).resolve()
    if not cartella.is_relative_to(radice_progetto.resolve()):
        # comandi.json e' trattato come dato di configurazione del progetto, ma
        # non e' firmato/verificato: senza questo controllo un file malevolo
        # potrebbe far girare comandi arbitrari fuori dalla cartella del
        # progetto (bug reale trovato in revisione di sicurezza, 2026-08-25).
        # radice_progetto e' ora obbligatoria (non piu' opzionale): un
        # chiamante che la dimentica prende un TypeError esplicito a tempo di
        # chiamata, invece di restare silenziosamente senza protezione
        # (residuo C2, revisione sicurezza v3, 2026-08-26).
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
    thread_id: str | None,
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
        **({"thread_id": thread_id} if thread_id else {}),
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
    console_utf8.forza_console_utf8()  # accenti dell'output su console Windows non-UTF-8
    parser = argparse.ArgumentParser(description="Sentinella deterministica: esegue solo comandi whitelistati")
    parser.add_argument("comando")
    parser.add_argument("--config", default=str(PERCORSO_COMANDI_PREDEFINITO))
    parser.add_argument("--registro", default=str(PERCORSO_REGISTRO_PREDEFINITO))
    parser.add_argument("--id-compito", default="gate")
    parser.add_argument("--thread-id", default="", help="thread bacheca correlato da propagare negli eventi")
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
        **({"thread_id": args.thread_id} if args.thread_id else {}),
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
            thread_id=args.thread_id or None,
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
