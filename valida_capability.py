#!/usr/bin/env python3
"""Validatore read-only del catalogo capability (manifest esplicito di cosa e'
verificato funzionante, per provider/canale). Vedi schema/capability.v1.json,
docs/PIANO_INDUSTRIALIZZAZIONE.md sezione 3, docs/THREAT_MODEL.md sezione 4.

Stesso pattern di valida_flussi.py: solo struttura e invarianti, nessuna
esecuzione. La regola "default deny" (sezione 3 del piano: capability non
verificata => nessuna automazione) e' un invariante strutturale qui, non
ancora un gate a runtime - nessun punto del codice legge oggi questo catalogo
per abilitare/disabilitare un dispatch reale."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

RADICE = Path(__file__).resolve().parent
PERCORSO_SCHEMA_PREDEFINITO = RADICE / "schema" / "capability.v1.json"
_PERCORSO_CATALOGO_REALE = RADICE / "config" / "capability_catalogo.json"
_PERCORSO_CATALOGO_ESEMPIO = RADICE / "config" / "capability_catalogo.esempio.json"
# Il catalogo reale (attestazioni locali, mai committato - vedi .gitignore) ha
# la precedenza se presente; altrimenti si valida il template pubblico.
PERCORSO_CATALOGO_PREDEFINITO = (
    _PERCORSO_CATALOGO_REALE if _PERCORSO_CATALOGO_REALE.exists() else _PERCORSO_CATALOGO_ESEMPIO
)

STATI_CHE_RICHIEDONO_MANUAL_ONLY = {"unknown", "failed", "degraded", "disabled"}
GIORNI_SCADENZA_VERIFIED_AUTOMATICA = 90


def carica_json(percorso: Path) -> Any:
    return json.loads(percorso.read_text(encoding="utf-8"))


def _formato_errore(errore: Any) -> str:
    percorso = ".".join(str(parte) for parte in errore.absolute_path) or "radice"
    return f"{percorso}: {errore.message}"


def _errori_schema(dati: Any, schema: dict[str, Any]) -> list[str]:
    validatore = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        _formato_errore(errore)
        for errore in sorted(validatore.iter_errors(dati), key=lambda e: list(e.absolute_path))
    ]


def _a_utc(timestamp_iso: str) -> datetime:
    normalizzato = timestamp_iso.replace("Z", "+00:00")
    valore = datetime.fromisoformat(normalizzato)
    if valore.tzinfo is None:
        valore = valore.replace(tzinfo=timezone.utc)
    return valore.astimezone(timezone.utc)


def _errori_invarianti(dati: Any) -> list[str]:
    errori: list[str] = []
    voci = dati.get("capability")
    if not isinstance(voci, list):
        return errori

    id_visti: set[str] = set()
    for indice, voce in enumerate(voci):
        if not isinstance(voce, dict):
            continue
        identita = voce.get("id")
        if isinstance(identita, str):
            if identita in id_visti:
                errori.append(f"capability[{indice}]: id duplicato: {identita!r}")
            id_visti.add(identita)

        stato = voce.get("stato")
        modalita = voce.get("modalita_operativa")
        if stato in STATI_CHE_RICHIEDONO_MANUAL_ONLY and modalita == "automatica":
            errori.append(
                f"capability[{indice}] ({identita!r}): stato={stato!r} ma modalita_operativa="
                "'automatica' - default deny (sezione 3 del piano): una capability non "
                "'verified' non puo' essere automatica, va 'manual_only' finche' non e' "
                "verificata o esplicitamente disabilitata."
            )

        checked_at = voce.get("checked_at")
        expires_at = voce.get("expires_at")
        if stato == "verified" and modalita == "automatica" and expires_at is None:
            errori.append(
                f"capability[{indice}] ({identita!r}): stato='verified'+modalita_operativa="
                "'automatica' ma expires_at=null - policy 2026-08-26 (sezione 6 del piano): "
                "un'attestazione automatica non puo' restare permanente, serve una scadenza "
                f"esplicita (al massimo {GIORNI_SCADENZA_VERIFIED_AUTOMATICA} giorni da checked_at)."
            )
        if isinstance(checked_at, str) and isinstance(expires_at, str):
            try:
                inizio = _a_utc(checked_at)
                fine = _a_utc(expires_at)
                if fine <= inizio:
                    errori.append(
                        f"capability[{indice}] ({identita!r}): expires_at non successivo a checked_at"
                    )
                elif (
                    stato == "verified"
                    and modalita == "automatica"
                    and (fine - inizio).days > GIORNI_SCADENZA_VERIFIED_AUTOMATICA
                ):
                    errori.append(
                        f"capability[{indice}] ({identita!r}): expires_at supera i "
                        f"{GIORNI_SCADENZA_VERIFIED_AUTOMATICA} giorni consentiti da checked_at "
                        "per una capability verified+automatica (policy 2026-08-26)."
                    )
            except ValueError as errore:
                errori.append(f"capability[{indice}] ({identita!r}): timestamp non valido: {errore}")

    return errori


def valida_catalogo(dati: Any, schema: dict[str, Any]) -> list[str]:
    """Ritorna gli errori dello schema e delle invarianti fra voci."""
    errori = _errori_schema(dati, schema)
    if errori or not isinstance(dati, dict):
        return errori
    errori.extend(_errori_invarianti(dati))
    return errori


def valida_file(
    percorso_catalogo: Path, percorso_schema: Path = PERCORSO_SCHEMA_PREDEFINITO
) -> list[str]:
    try:
        dati = carica_json(percorso_catalogo)
    except (OSError, json.JSONDecodeError) as errore:
        return [f"impossibile leggere il catalogo {percorso_catalogo}: {errore}"]
    try:
        schema = carica_json(percorso_schema)
    except (OSError, json.JSONDecodeError) as errore:
        return [f"impossibile leggere lo schema {percorso_schema}: {errore}"]
    return valida_catalogo(dati, schema)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida un catalogo capability (read-only).")
    parser.add_argument("catalogo", nargs="?", type=Path, default=PERCORSO_CATALOGO_PREDEFINITO)
    parser.add_argument("--schema", type=Path, default=PERCORSO_SCHEMA_PREDEFINITO)
    args = parser.parse_args(argv)
    errori = valida_file(args.catalogo, args.schema)
    if errori:
        for errore in errori:
            print(f"errore: {errore}", file=sys.stderr)
        return 1
    print(f"catalogo valido: {args.catalogo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
