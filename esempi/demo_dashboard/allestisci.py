#!/usr/bin/env python3
"""Allestisce un progetto DEMO con dati generici (nessun contenuto reale) da
usare per le schermate del README senza esporre conversazioni/percorsi veri.

Cosa fa:
1. genera bacheca, registro, note di codice e stati di consegna finti in
   esempi/demo_dashboard/progetto/dati_locali/orchestrazione/ (cartella
   gitignored: rigenerabile, non versionata);
2. registra il progetto "demo" in dati_locali/progetti.json della dashboard.

Poi: `python interfaccia.py`, apri http://127.0.0.1:8095 e seleziona "Demo".

Idempotente: si puo' rilanciare (ricrea da zero la cartella del progetto demo).
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

import bacheca  # noqa: E402
import note_codice  # noqa: E402
import registro  # noqa: E402

PROGETTO = Path(__file__).resolve().parent / "progetto"
ORCH = PROGETTO / "dati_locali" / "orchestrazione"
BASE = datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc)


def _ts(minuti: int) -> str:
    return (BASE + timedelta(minutes=minuti)).isoformat().replace("+00:00", "Z")


def _msg(percorso: Path, minuti: int, **kw: object) -> dict:
    m = bacheca.costruisci_messaggio(**kw)  # type: ignore[arg-type]
    m["timestamp"] = _ts(minuti)
    bacheca.aggiungi_messaggio(percorso, m)
    return m


def _piano_evento(percorso: Path, minuti: int, thread_id: str, attore: str, piano: dict) -> None:
    """Evento `piano` con timestamp controllato: le funzioni di piano_comandi
    userebbero l'ora reale e romperebbero l'ordine append-only del demo."""
    m = bacheca.costruisci_messaggio(
        mittente=attore, destinatari=["umano"], tipo="risposta",
        testo=f"[piano] {piano['azione']} {piano['passo_id']}", thread_id=thread_id, piano=piano,
    )
    m["timestamp"] = _ts(minuti)
    bacheca.aggiungi_messaggio(percorso, m)


def _crea_passo(percorso: Path, minuti: int, thread_id: str, piano_id: str, passo_id: str,
                descrizione: str, write_set: list[str]) -> None:
    _piano_evento(percorso, minuti, thread_id, "umano", {
        "azione": "crea_passo", "piano_id": piano_id, "passo_id": passo_id, "attore": "umano",
        "campi": {"descrizione": descrizione, "write_set": write_set},
    })


def _prendi_passo(percorso: Path, minuti: int, thread_id: str, piano_id: str, passo_id: str,
                  attore: str) -> None:
    _piano_evento(percorso, minuti, thread_id, attore, {
        "azione": "aggiorna_passo", "piano_id": piano_id, "passo_id": passo_id, "attore": attore,
        "precondizione": {"versione": 0, "stato": "non_iniziato"},
        "campi": {"proprietario": attore, "stato": "in_corso"},
    })


def _evento(percorso: Path, minuti: int, **kw: object) -> None:
    ev = {
        "versione_schema": 1, "id_evento": str(uuid.uuid4()), "timestamp": _ts(minuti),
        "verdetto_umano": "non_revisionato", "costo_stimato_usd": 0.0,
        "origine_costo": "stimato", "latenza_ms": 0, "regole_incluse": ["demo"], "note": "",
    }
    ev.update(kw)
    registro.aggiungi_evento(percorso, ev)


def _scenario_bacheca() -> None:
    percorso = ORCH / "messaggi.jsonl"

    # -- Thread 1: un compito con piano dichiarato a corsie --------------------
    richiesta = _msg(
        percorso, 0, mittente="umano", destinatari=["claude", "codex", "gemini"],
        tipo="richiesta", thread_id="demo-export",
        testo="Aggiungiamo un export CSV al modulo report: colonna data, importo, categoria.",
    )
    _msg(percorso, 3, mittente="claude", destinatari=["umano", "codex", "gemini"],
         tipo="presa_in_carico", thread_id="demo-export", correla_a=richiesta["id_messaggio"],
         testo="claude ha preso in carico il thread")
    _msg(percorso, 5, mittente="claude", destinatari=["umano", "codex", "gemini"],
         tipo="risposta", thread_id="demo-export",
         testo="Divido in tre corsie con write-set disgiunti: il modulo di export, i test, la doc.")

    _crea_passo(percorso, 7, "demo-export", "P1", "export",
                "Funzione export_csv nel modulo report", ["report/export.py"])
    _crea_passo(percorso, 8, "demo-export", "P1", "test", "Test dell'export CSV",
                ["tests/test_export.py"])
    _crea_passo(percorso, 9, "demo-export", "P1", "doc", "Aggiornare la guida utente",
                ["docs/guida_report.md"])
    _prendi_passo(percorso, 10, "demo-export", "P1", "export", "claude")
    _prendi_passo(percorso, 11, "demo-export", "P1", "test", "codex")
    _prendi_passo(percorso, 12, "demo-export", "P1", "doc", "gemini")

    _msg(percorso, 20, mittente="codex", destinatari=["claude", "umano"], tipo="risposta",
         thread_id="demo-export", testo="Passo 'test' in corso: scheletro pronto, mancano i casi limite.")
    _msg(percorso, 26, mittente="claude", destinatari=["umano", "codex", "gemini"], tipo="risposta",
         thread_id="demo-export", correla_a=richiesta["id_messaggio"],
         testo="Passo 'export' completato: export_csv scrive data/importo/categoria, quoting corretto.")
    _piano_evento(percorso, 27, "demo-export", "claude", {
        "azione": "aggiorna_passo", "piano_id": "P1", "passo_id": "export", "attore": "claude",
        "precondizione": {"versione": 1, "stato": "in_corso"}, "campi": {"stato": "fatto"}})

    # -- Thread 2: una collisione di piano rilevata dal sistema ---------------
    r2 = _msg(percorso, 40, mittente="umano", destinatari=["codex", "gemini"], tipo="richiesta",
              thread_id="demo-collisione", testo="Sistemate insieme la validazione degli importi.")
    _crea_passo(percorso, 41, "demo-collisione", "P2", "a", "Validazione lato modello",
                ["report/validazione.py"])
    _crea_passo(percorso, 42, "demo-collisione", "P2", "b", "Messaggi d'errore validazione",
                ["report/validazione.py"])
    _prendi_passo(percorso, 43, "demo-collisione", "P2", "a", "codex")
    _prendi_passo(percorso, 44, "demo-collisione", "P2", "b", "gemini")
    _msg(percorso, 45, mittente="sistema", destinatari=["umano", "codex", "gemini"],
         tipo="segnalazione_conflitto", thread_id="demo-collisione", correla_a=r2["id_messaggio"],
         testo="I passi 'a' e 'b' scrivono entrambi report/validazione.py: serve una decisione "
               "(restringere i write-set o un handoff).",
         metadati={"origine": "watcher_piano_overlap", "coppia": "write_x_write"})

    # -- Thread 3: un compito chiuso, per la timeline -------------------------
    r3 = _msg(percorso, 60, mittente="umano", destinatari=["claude"], tipo="richiesta",
              thread_id="demo-chiuso", testo="Rinomina la costante SOGLIA in SOGLIA_IMPORTO.")
    _msg(percorso, 62, mittente="claude", destinatari=["umano"], tipo="presa_in_carico",
         thread_id="demo-chiuso", correla_a=r3["id_messaggio"], testo="claude ha preso in carico il thread")
    _msg(percorso, 70, mittente="claude", destinatari=["umano"], tipo="chiusura",
         thread_id="demo-chiuso", testo="Fatto: rinomina in 4 file, gate verde, commit a1b2c3d.")

    # -- Thread 4: un messaggio in attesa, con stato di consegna -------------
    r4 = _msg(percorso, 80, mittente="umano", destinatari=["gemini"], tipo="richiesta",
              thread_id="demo-attesa", testo="Puoi rivedere la formattazione della tabella riepilogo?")
    for riga in (
        {"agente": "gemini", "id_messaggio": r4["id_messaggio"], "thread_id": "demo-attesa",
         "quando": _ts(81)},
    ):
        (ORCH / "hook_contesto.jsonl").open("a", encoding="utf-8").write(json.dumps(riga) + "\n")
    (ORCH / "consegne_risveglio.jsonl").open("a", encoding="utf-8").write(json.dumps({
        "versione_schema": 1, "agente": "gemini", "id_messaggio": r4["id_messaggio"],
        "stato": "attenzione_richiamata", "motivo": None, "canale": "os_wake",
        "origine": "watcher", "quando": _ts(80),
    }) + "\n")


def _scenario_registro() -> None:
    percorso = ORCH / "eventi.jsonl"
    _evento(percorso, 24, id_compito="demo-export", agente="codex", tipo_compito="servizi",
            stato="passato", esito_gate="superato",
            note="Richiesta: export CSV | Fatto: scheletro test + 6 casi")
    _evento(percorso, 28, id_compito="demo-export", agente="claude", tipo_compito="servizi",
            stato="passato", esito_gate="superato",
            note="Richiesta: export CSV | Fatto: report/export.py, quoting e header")
    _evento(percorso, 30, id_compito="demo-export", agente="umano", tipo_compito="orchestrazione",
            stato="accettato", esito_gate="non_eseguito", verdetto_umano="approvato",
            note="approvato il commit dell'export CSV")
    _evento(percorso, 72, id_compito="demo-chiuso", agente="claude", tipo_compito="interfaccia",
            stato="passato", esito_gate="superato", note="Richiesta: rinomina SOGLIA | Fatto: 4 file")


def _scenario_note() -> None:
    (PROGETTO / "report").mkdir(parents=True, exist_ok=True)
    modulo = PROGETTO / "report" / "export.py"
    modulo.write_text(
        "import csv\n\n"
        "def export_csv(righe, destinazione):\n"
        "    # quoting minimo: solo dove serve, per non gonfiare il file\n"
        "    with open(destinazione, 'w', newline='') as f:\n"
        "        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)\n"
        "        w.writerow(['data', 'importo', 'categoria'])\n"
        "        w.writerows(righe)\n",
        encoding="utf-8",
    )
    note_codice.aggiungi_nota(
        PROGETTO, "report/export.py", 4, 4,
        "QUOTE_MINIMAL e' voluto: con QUOTE_ALL i file crescono del ~30% e "
        "il consumatore a valle non lo richiede.", "claude", adesso=_ts(29),
    )
    note_codice.aggiungi_nota(
        PROGETTO, "report/export.py", 6, 6,
        "L'ordine delle colonne e' un contratto con l'importatore: non riordinare "
        "senza avvisare.", "umano", adesso=_ts(31),
    )


def _registra_progetto() -> None:
    percorso_progetti = RADICE / "dati_locali" / "progetti.json"
    percorso_progetti.parent.mkdir(parents=True, exist_ok=True)
    try:
        dati = json.loads(percorso_progetti.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        dati = {"progetti": []}
    progetti = [p for p in dati.get("progetti", []) if p.get("id") != "demo"]
    progetti.append({"id": "demo", "nome": "Demo (dati finti)", "percorso": str(PROGETTO)})
    dati["progetti"] = progetti
    percorso_progetti.write_text(json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    if PROGETTO.exists():
        shutil.rmtree(PROGETTO)
    ORCH.mkdir(parents=True, exist_ok=True)
    _scenario_bacheca()
    _scenario_registro()
    _scenario_note()
    _registra_progetto()
    print(f"Demo allestita in {PROGETTO}")
    print("Registrata come progetto 'demo' nella dashboard.")
    print("Ora: python interfaccia.py  ->  http://127.0.0.1:8095  ->  seleziona 'Demo (dati finti)'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
