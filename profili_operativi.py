"""Profili operativi per progetto del Postino, con default fail-closed."""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import registro

PROFILI = ("standard", "brainstorming", "super", "smodata")
PERCORSO_SCHEMA = Path(__file__).resolve().parent / "schema" / "profilo_operativo.v1.json"
NOME_FILE = "profilo_operativo.json"

# Un profilo assente o non ancora supportato non deve mai avviare un agente.
PROFILI_DISPATCH_ABILITATI = {"brainstorming"}

# La UI deve dichiarare il tipo di garanzia effettivo, non solo il nome del profilo.
# super/smodata restano non disponibili finche' la matrice comandi non e' implementata.
GARANZIE: dict[str, dict[str, str]] = {
    "standard": {agente: "enforced" for agente in ("claude", "codex", "gemini")},
    "brainstorming": {"claude": "enforced", "codex": "prompt_only", "gemini": "prompt_only"},
    "super": {agente: "non_disponibile" for agente in ("claude", "codex", "gemini")},
    "smodata": {agente: "non_disponibile" for agente in ("claude", "codex", "gemini")},
}


def percorso_profilo(radice: Path) -> Path:
    return radice / "dati_locali" / "orchestrazione" / NOME_FILE


def _schema() -> dict[str, Any]:
    return json.loads(PERCORSO_SCHEMA.read_text(encoding="utf-8"))


def _errori_profilo(dati: dict[str, Any]) -> list[str]:
    validatore = registro.validatore_per_schema(_schema())
    return [registro.messaggio_errore(errore, dati) for errore in validatore.iter_errors(dati)]


def profilo_standard() -> dict[str, Any]:
    """DTO runtime per una configurazione assente/corrotta: nessun dispatch."""
    return {"profilo": "standard", "revisione": None, "aggiornato_il": None, "origine": "default"}


def carica(radice: Path) -> dict[str, Any]:
    percorso = percorso_profilo(radice)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return profilo_standard()
    if not isinstance(dati, dict) or _errori_profilo(dati):
        return profilo_standard()
    return {**dati, "origine": "configurato"}


def imposta(radice: Path, profilo: str, *, revisione: str | None = None) -> dict[str, Any]:
    if profilo not in PROFILI:
        raise ValueError(f"profilo non valido: {profilo}")
    dati = {
        "versione_schema": 1,
        "profilo": profilo,
        "aggiornato_il": registro.adesso_utc(),
        "revisione": revisione or str(uuid.uuid4()),
    }
    errori = _errori_profilo(dati)
    if errori:
        raise ValueError("; ".join(errori))
    percorso = percorso_profilo(radice)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=percorso.parent, delete=False) as file:
        file.write(json.dumps(dati, ensure_ascii=False, sort_keys=True))
        file.write("\n")
        temporaneo = Path(file.name)
    try:
        os.replace(temporaneo, percorso)
    finally:
        if temporaneo.exists():
            temporaneo.unlink()
    return {**dati, "origine": "configurato"}


def dispatch_abilitato(profilo: dict[str, Any]) -> bool:
    return profilo["profilo"] in PROFILI_DISPATCH_ABILITATI


def garanzie(profilo: dict[str, Any]) -> dict[str, str]:
    return dict(GARANZIE[profilo["profilo"]])


def istruzione_interattiva(profilo: dict[str, Any]) -> str:
    nome = profilo["profilo"]
    if nome == "standard":
        return "Profilo operativo standard: nessuna automazione del Postino e' autorizzata."
    if nome == "brainstorming":
        return "Profilo brainstorming: rispondi in bacheca; se vorresti modificare file, dichiaralo e chiedi come procedere prima di agire."
    return (
        "Profilo %s: la scrittura di file puo' essere richiesta; Git in scrittura "
        "(commit, push, branch, merge, reset) resta vietato senza ordine esplicito dell'umano."
    ) % nome
