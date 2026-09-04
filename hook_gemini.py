#!/usr/bin/env python3
"""Hook wrapper per Antigravity / Gemini.

Esegue l'iniezione bacheca su PreInvocation e registra traccia di diagnostica
in dati_locali/orchestrazione/log_hook_antigravity.jsonl per collaudo live.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))

import bacheca  # noqa: E402
import capability_policy  # noqa: E402
import scrittura_jsonl  # noqa: E402


def main() -> int:
    percorso_log = RADICE / "dati_locali" / "orchestrazione" / "log_hook_antigravity.jsonl"
    payload_stdin: object = {}
    testo_stdin = ""
    try:
        if not sys.stdin.isatty():
            testo_stdin = sys.stdin.read()
            if testo_stdin.strip():
                payload_stdin = json.loads(testo_stdin)
    except Exception:
        pass

    decisione = capability_policy.autorizza_automazione("gemini", "hook_pull")
    # Non logghiamo il payload grezzo di Antigravity (potrebbe contenere segreti
    # o PII - rilievo review v4 N15): per il collaudo bastano forma e dimensione.
    evento_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stdin_chiavi": sorted(payload_stdin) if isinstance(payload_stdin, dict)
        else type(payload_stdin).__name__,
        "stdin_byte": len(testo_stdin.encode("utf-8")),
        "capability_policy": decisione,
    }
    try:
        scrittura_jsonl.aggiungi_riga_jsonl(percorso_log, evento_log)
    except Exception:
        pass

    if decisione["esito"] != "autorizzato":
        registrato = capability_policy.registra_blocco(RADICE, "gemini", "hook_pull", decisione)
        print(
            f"hook Gemini bloccato dalla policy capability: {decisione['motivo']} "
            f"(log={'ok' if registrato else 'fallito'})",
            file=sys.stderr,
        )
        print(json.dumps({}))
        return 0

    # Recupera i messaggi pendenti e formatta per Antigravity
    percorso_bacheca = RADICE / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
    messaggi = bacheca.leggi_messaggi(percorso_bacheca)
    pendenti = bacheca.messaggi_aperti_per(messaggi, "gemini")
    riprese = bacheca.riprese_pronte(messaggi, "gemini")
    testo = bacheca.arricchisci_hook_con_profilo(
        bacheca._formatta_per_hook(pendenti, riprese), RADICE
    )

    if not testo:
        print(json.dumps({}))
    else:
        print(json.dumps({"injectSteps": [{"ephemeralMessage": testo}]}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
