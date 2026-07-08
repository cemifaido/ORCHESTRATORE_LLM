#!/usr/bin/env python3
"""Orchestratore del loop di brainstorming a tre voci (Claude headless <-> Gemini e
Codex pull-manuale), come definito in docs/PIANO_SPERIMENTAZIONE_HEADLESS.md.

Fasi automatizzate qui (1 e 1.5 del piano):
  1. Invoca Claude Code CLI in modalita' non interattiva (`claude -p`, incluso
     nell'abbonamento flat) con l'argomento del brainstorming, e scrive il
     risultato in bacheca come nuovo thread.
  2. Chiama il modello locale (bacheca.sintetizza_thread, gia' esistente) per
     ridurre l'output di Claude a una sintesi compatta, e la indirizza a Gemini e
     Codex come destinatari paralleli.

Fase 2 (Gemini/Codex) resta deliberatamente NON automatizzata: nessuno dei due ha
un canale headless o hook verificato per il flat (docs/RFC_BACHECA_MULTIAGENTE.md
§4.3, §4.4), quindi il pull resta manuale - l'utente esegue
`python bacheca.py prossimo --agente <gemini|codex>` aprendo la sessione, come per
qualunque altro thread in bacheca. La sintesi/triage finale sulla risposta usa il
comando gia' esistente `python bacheca.py sintetizza --thread-id <id>`, non
duplicato qui.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))

import bacheca  # noqa: E402

CLAUDE_CLI = os.environ.get("CLAUDE_CLI_PATH", "claude")
TIMEOUT_CLAUDE_SECONDI = 180

PROMPT_TEMPLATE = (
    "Obiettivo brainstorming: {argomento}\n\n"
    "Fornisci una proposta tecnica concisa e strutturata. Il tuo output verra' "
    "sintetizzato da un modello locale e poi letto da un secondo collaboratore "
    "(Gemini) in un turno successivo, quindi sii esplicito e autosufficiente."
)


def invoca_claude_headless(
    prompt: str, timeout: int = TIMEOUT_CLAUDE_SECONDI, binario: str = CLAUDE_CLI
) -> dict[str, Any]:
    """Invoca Claude Code CLI in modalita' non interattiva (-p/--print). Se
    il binario standalone 'claude' non viene trovato in PATH, effettua un
    fallback trasparente lanciando 'npx @anthropic-ai/claude-code'."""
    args = [binario, "-p", prompt]
    try:
        completato = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        if binario == "claude":
            npx_bin = "npx.cmd" if os.name == "nt" else "npx"
            fallback_args = [npx_bin, "@anthropic-ai/claude-code", "-p", prompt]
            try:
                completato = subprocess.run(
                    fallback_args,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            except FileNotFoundError:
                return {"ok": False, "errore": f"binario 'claude' e fallback '{npx_bin}' non trovato in PATH"}
            except subprocess.TimeoutExpired:
                return {"ok": False, "errore": f"npx @anthropic-ai/claude-code -p non ha risposto entro {timeout}s"}
        else:
            return {"ok": False, "errore": f"binario '{binario}' non trovato in PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "errore": f"{binario} -p non ha risposto entro {timeout}s"}

    if completato.returncode != 0:
        return {
            "ok": False,
            "errore": f"Esecuzione fallita (codice {completato.returncode}): {completato.stderr.strip()[:500]}",
        }

    testo = completato.stdout.strip()
    if not testo:
        return {"ok": False, "errore": "L'esecuzione ha risposto con output vuoto"}
    return {"ok": True, "testo": testo}


def avvia_brainstorming(
    argomento: str, percorso_bacheca: Path = bacheca.PERCORSO_BACHECA_PREDEFINITO
) -> dict[str, Any]:
    """Fasi 1 e 1.5 del piano: Claude headless + sintesi locale, poi indirizzato a
    Gemini per il pull manuale. Ritorna un riepilogo per il chiamante CLI; scrive
    sempre in bacheca solo se Claude ha risposto (niente thread orfani su un
    fallimento a monte)."""
    esito_claude = invoca_claude_headless(PROMPT_TEMPLATE.format(argomento=argomento))
    if not esito_claude["ok"]:
        return {"ok": False, "fase": "claude", "errore": esito_claude["errore"]}

    messaggio_claude = bacheca.costruisci_messaggio(
        mittente="claude",
        destinatari=["locale"],
        tipo="sintesi",
        testo=esito_claude["testo"],
        metadati={"fonte": "claude -p (headless)", "argomento": argomento},
    )
    bacheca.aggiungi_messaggio(percorso_bacheca, messaggio_claude)
    thread_id = messaggio_claude["thread_id"]

    messaggi = bacheca.leggi_messaggi(percorso_bacheca)
    esito_sintesi = bacheca.sintetizza_thread(messaggi, thread_id)

    if esito_sintesi["ok"]:
        testo_sintesi = esito_sintesi["sintesi"]
        sintesi_fallita = False
    else:
        # non blocchiamo il loop solo perche' il modello locale non risponde:
        # i destinatari ricevono il testo integrale di Claude invece della sintesi, con
        # nota esplicita nei metadati - mai un thread senza nessuno che lo aspetti.
        testo_sintesi = esito_claude["testo"]
        sintesi_fallita = True

    messaggio_sintesi = bacheca.costruisci_messaggio(
        mittente="locale",
        destinatari=["gemini", "codex"],
        tipo="sintesi",
        testo=testo_sintesi,
        thread_id=thread_id,
        correla_a=messaggio_claude["id_messaggio"],
        metadati={"sintesi_locale_fallita": sintesi_fallita},
    )
    bacheca.aggiungi_messaggio(percorso_bacheca, messaggio_sintesi)

    return {
        "ok": True,
        "thread_id": thread_id,
        "sintesi_locale_fallita": sintesi_fallita,
        "errore_sintesi": esito_sintesi.get("errore") if sintesi_fallita else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--argomento", required=True, help="Obiettivo del brainstorming")
    parser.add_argument(
        "--bacheca",
        default=str(bacheca.PERCORSO_BACHECA_PREDEFINITO),
        help="Percorso del file messaggi.jsonl",
    )
    args = parser.parse_args(argv)

    esito = avvia_brainstorming(args.argomento, Path(args.bacheca))
    if not esito["ok"]:
        print(f"[ERRORE] Fase '{esito['fase']}' fallita: {esito['errore']}", file=sys.stderr)
        return 1

    print(f"Thread creato: {esito['thread_id']}")
    if esito["sintesi_locale_fallita"]:
        print(
            f"[AVVISO] Sintesi locale fallita ({esito['errore_sintesi']}); "
            "Gemini e Codex riceveranno il testo integrale di Claude.",
            file=sys.stderr,
        )

    # Segnale acustico per avvisare l'utente (nativamente su Windows via winsound, fallback bell)
    try:
        import winsound
        winsound.MessageBeep()
    except (ImportError, Exception):
        sys.stdout.write("\a")
        sys.stdout.flush()

    print("\n*** [NOTIFICA] Le fasi automatiche sono terminate! C'e' del lavoro in attesa in bacheca. ***")
    print("Prossimo passo: l'utente apre le sessioni Gemini/Codex ed esegue "
          "'python bacheca.py prossimo --agente <gemini|codex>' per il pull manuale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
