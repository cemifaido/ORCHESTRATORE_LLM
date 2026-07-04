#!/usr/bin/env python3
"""Triage a costo zero con il modello locale (llama-server).

Non risolve nulla: classifica solo un output (test/lint/build) per decidere se e'
routine o se serve scalare a un agente piu' capace o a un umano. Pensato per essere
richiamato prima di "guardare" personalmente un output di routine — vedi
docs/ORCHESTRAZIONE_LAVORATORI.md, sezione Capoturno.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))

from adattatori import litellm  # noqa: E402
import registro  # noqa: E402

PERCORSO_REGISTRO_PREDEFINITO = Path("dati_locali") / "orchestrazione" / "eventi.jsonl"

PROMPT_SISTEMA = (
    "Sei un assistente di triage tecnico. Ricevi l'output di un comando (test, lint, "
    "build) e devi SOLO classificarlo, non risolverlo. Rispondi ESCLUSIVAMENTE con un "
    'oggetto JSON, senza altro testo, con due chiavi: "esito" ("routine" se tutto ok o '
    'l\'errore e\' banale/noto, "escalation" se serve un umano o un agente piu\' capace) '
    'e "motivo" (una frase breve in italiano che spiega la classificazione).'
)


def classifica(output: str, contesto: str = "") -> dict[str, Any]:
    """Classifica un output come 'routine' o 'escalation'. In caso di dubbio (risposta
    del modello locale non interpretabile) ritorna sempre 'escalation': non si nasconde
    mai un possibile problema dietro un parsing fallito. Include sempre 'token_totali'
    (None se la chiamata stessa e' fallita) per poter stimare in seguito, con dati
    reali, quanto sarebbe costato lo stesso controllo su un modello a pagamento."""
    messaggi = [
        {"role": "system", "content": PROMPT_SISTEMA},
        {"role": "user", "content": f"Contesto: {contesto}\n\nOutput da classificare:\n{output[:4000]}"},
    ]
    try:
        risposta, misurazione = litellm.completamento_locale(messaggi=messaggi, max_tokens=150, temperature=0.0)
    except Exception as errore:
        return {"esito": "escalation", "motivo": f"modello locale non raggiungibile: {errore}", "token_totali": None}

    testo = litellm.testo_da_risposta(risposta)
    try:
        inizio = testo.index("{")
        fine = testo.rindex("}") + 1
        dati = json.loads(testo[inizio:fine])
        esito = dati.get("esito")
        if esito not in ("routine", "escalation"):
            raise ValueError(f"esito non valido: {esito!r}")
        return {"esito": esito, "motivo": str(dati.get("motivo", "")), "token_totali": misurazione.token_totali}
    except Exception:
        return {
            "esito": "escalation",
            "motivo": f"risposta locale non interpretabile: {testo[:200]}",
            "token_totali": misurazione.token_totali,
        }


def registra_classificazione(
    risultato: dict[str, Any],
    latenza_ms: int,
    percorso_registro: Path,
    id_compito: str,
    contesto: str,
) -> None:
    """Registra la classificazione come evento agente=locale: senza questo, il lavoro
    del modello locale sparisce in stdout, esattamente come succedeva a Claude prima di
    iniziare a loggare i propri compiti (vedi CLAUDE.md). token_totali va nei metadati
    (dato reale, non una stima) cosi' un'eventuale stima di risparmio si potra' sempre
    ricalcolare dal dato grezzo invece che da un numero congelato nella nota."""
    evento = {
        "versione_schema": 1,
        "id_evento": str(uuid.uuid4()),
        "timestamp": registro.adesso_utc(),
        "id_compito": id_compito,
        "agente": "locale",
        "tipo_compito": "monitoraggio",
        "stato": "passato" if risultato["esito"] == "routine" else "da_rivedere",
        "esito_gate": "non_eseguito",
        "verdetto_umano": "non_revisionato",
        "costo_stimato_usd": 0.0,
        "origine_costo": "misurato",
        "latenza_ms": latenza_ms,
        "regole_incluse": ["triage_locale"],
        "file_modificati": [],
        "note": f"[{risultato['esito']}] {risultato['motivo']}" + (f" (contesto: {contesto})" if contesto else ""),
        "metadati": {"token_totali": risultato.get("token_totali")},
    }
    registro.aggiungi_evento(percorso_registro, evento)


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage a costo zero con il modello locale")
    parser.add_argument("--registro", default=str(PERCORSO_REGISTRO_PREDEFINITO))
    parser.add_argument("--id-compito", default=f"triage-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--contesto", default="")
    args = parser.parse_args()

    output = sys.stdin.read()
    inizio = time.perf_counter()
    risultato = classifica(output, contesto=args.contesto)
    latenza_ms = int((time.perf_counter() - inizio) * 1000)

    registra_classificazione(risultato, latenza_ms, Path(args.registro), args.id_compito, args.contesto)

    print(json.dumps(risultato, ensure_ascii=False, indent=2))
    return 0 if risultato["esito"] == "routine" else 1


if __name__ == "__main__":
    raise SystemExit(main())
