"""Gate runtime fail-closed per le automazioni dichiarate nel catalogo capability."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import scrittura_jsonl
import valida_capability

RADICE = Path(__file__).resolve().parent
PERCORSO_CATALOGO_REALE = RADICE / "config" / "capability_catalogo.json"
PERCORSO_CATALOGO_ESEMPIO = RADICE / "config" / "capability_catalogo.esempio.json"
SUFFISSI_CANALE = {"headless": "cli_headless", "deep_link": "uri_wake", "hook_pull": "hook_pull"}


def percorso_catalogo_predefinito() -> Path:
    return PERCORSO_CATALOGO_REALE if PERCORSO_CATALOGO_REALE.exists() else PERCORSO_CATALOGO_ESEMPIO


def id_capability(agente: str, canale: str) -> str | None:
    suffisso = SUFFISSI_CANALE.get(canale)
    return f"{agente}_{suffisso}" if suffisso else None


def _bloccato(motivo: str, capability: str | None) -> dict[str, str]:
    esito = {"esito": "bloccato", "motivo": motivo}
    if capability is not None:
        esito["capability"] = capability
    return esito


def valuta_catalogo(
    dati: dict[str, Any], agente: str, canale: str, *, ora: datetime | None = None
) -> dict[str, str]:
    """Valuta una capability gia' caricata; nessun I/O, adatta a fixture di test."""
    capability = id_capability(agente, canale)
    if capability is None:
        return _bloccato("canale_capability_sconosciuto", None)
    voce = next((voce for voce in dati.get("capability", []) if voce.get("id") == capability), None)
    if voce is None:
        return _bloccato("capability_assente", capability)
    if voce.get("stato") != "verified":
        return _bloccato("capability_non_verificata", capability)
    if voce.get("modalita_operativa") != "automatica":
        return _bloccato("capability_non_automatica", capability)
    scadenza = voce.get("expires_at")
    if not isinstance(scadenza, str):
        return _bloccato("capability_senza_scadenza", capability)
    try:
        fine = datetime.fromisoformat(scadenza.replace("Z", "+00:00"))
    except ValueError:
        return _bloccato("catalogo_non_valido", capability)
    confronto = ora or datetime.now(timezone.utc)
    if fine.tzinfo is None:
        fine = fine.replace(tzinfo=timezone.utc)
    if fine.astimezone(timezone.utc) <= confronto.astimezone(timezone.utc):
        return _bloccato("capability_scaduta", capability)
    return {"esito": "autorizzato", "capability": capability}


def autorizza_automazione(
    agente: str, canale: str, *, catalogo_path: Path | None = None, ora: datetime | None = None
) -> dict[str, str]:
    """Carica e valida il catalogo; ogni problema e' un blocco fail-closed."""
    percorso = catalogo_path or percorso_catalogo_predefinito()
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _bloccato("catalogo_non_leggibile", id_capability(agente, canale))
    if valida_capability.valida_file(percorso):
        return _bloccato("catalogo_non_valido", id_capability(agente, canale))
    return valuta_catalogo(dati, agente, canale, ora=ora)


def registra_blocco(radice: Path, agente: str, canale: str, decisione: dict[str, str]) -> bool:
    """Rende osservabile un blocco senza trasformarlo in autorizzazione."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agente": agente,
        "canale": canale,
        "esito": "bloccato",
        "motivo": decisione["motivo"],
        "capability": decisione.get("capability"),
    }
    try:
        scrittura_jsonl.aggiungi_riga_jsonl(
            radice / "dati_locali" / "orchestrazione" / "capability_blocchi.jsonl", record
        )
    except (OSError, TimeoutError):
        return False
    return True
