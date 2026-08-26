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


def main() -> int:
    percorso_log = RADICE / "dati_locali" / "orchestrazione" / "log_hook_antigravity.jsonl"
    payload_stdin = {}
    try:
        if not sys.stdin.isatty():
            testo_stdin = sys.stdin.read()
            if testo_stdin.strip():
                payload_stdin = json.loads(testo_stdin)
    except Exception:
        pass

    evento_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stdin": payload_stdin,
    }
    try:
        percorso_log.parent.mkdir(parents=True, exist_ok=True)
        with percorso_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evento_log, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # Recupera i messaggi pendenti e formatta per Antigravity
    percorso_bacheca = RADICE / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
    messaggi = bacheca.leggi_messaggi(percorso_bacheca)
    pendenti = bacheca.messaggi_aperti_per(messaggi, "gemini")
    riprese = bacheca.riprese_pronte(messaggi, "gemini")
    testo = bacheca._formatta_per_hook(pendenti, riprese)

    if not testo:
        print(json.dumps({}))
    else:
        print(json.dumps({"injectSteps": [{"ephemeralMessage": testo}]}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
