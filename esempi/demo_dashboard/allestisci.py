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
import subprocess
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
    # Finestra del commit "feat(report): export CSV" (dal commit padre alle 09:05
    # fino alle 09:32): una staffetta fra tutti gli attori, cosi' il "Replay di un
    # Commit Reale" anima piu' passaggi di palla e non solo un paio di nodi.
    c = "demo-export"
    _evento(percorso, 6, id_compito=c, agente="umano", tipo_compito="orchestrazione",
            stato="nuovo", esito_gate="non_eseguito",
            note="Richiesta: aggiungere un export CSV al modulo report (data, importo, categoria).")
    _evento(percorso, 8, id_compito=c, agente="gemini", tipo_compito="orchestrazione",
            stato="passato", esito_gate="non_eseguito",
            note="Triage: divido in tre corsie con write-set disgiunti - export, test, doc.")
    _evento(percorso, 11, id_compito=c, agente="claude", tipo_compito="servizi",
            stato="in_corso", esito_gate="non_eseguito",
            note="Corsia 'export': bozza di export_csv, header piu' righe.")
    _evento(percorso, 14, id_compito=c, agente="codex", tipo_compito="servizi",
            stato="in_corso", esito_gate="non_eseguito",
            note="Corsia 'test': scheletro test_export piu' quattro casi limite.")
    _evento(percorso, 16, id_compito=c, agente="locale", tipo_compito="errore_test",
            stato="passato", esito_gate="superato",
            note="Triage gate lint/tipi in locale: nessun rilievo, zero costo.",
            metadati={"token_totali": 1850})
    _evento(percorso, 19, id_compito=c, agente="claude", tipo_compito="servizi",
            stato="passato", esito_gate="superato",
            note="Integrato quoting minimo e header; gate verde in locale.")
    _evento(percorso, 21, id_compito=c, agente="codex", tipo_compito="revisione",
            stato="da_rivedere", esito_gate="non_eseguito",
            note="Review corsia 'export': manca newline='' su Windows, per il resto ok.")
    _evento(percorso, 23, id_compito=c, agente="claude", tipo_compito="servizi",
            stato="passato", esito_gate="superato",
            note="Applicato newline='' e ritestato: 6/6 verde.")
    _evento(percorso, 26, id_compito=c, agente="gemini", tipo_compito="documentazione",
            stato="passato", esito_gate="non_eseguito",
            note="Corsia 'doc': guida_report.md aggiornata con colonne e formato.")
    _evento(percorso, 28, id_compito=c, agente="locale", tipo_compito="errore_test",
            stato="passato", esito_gate="superato",
            note="Triage suite completa: routine, 6/6 verde, zero costo.",
            metadati={"token_totali": 2100})
    _evento(percorso, 30, id_compito=c, agente="umano", tipo_compito="orchestrazione",
            stato="accettato", esito_gate="non_eseguito", verdetto_umano="approvato",
            note="Approvato: commit feat(report) export CSV.")
    _evento(percorso, 72, id_compito="demo-chiuso", agente="claude", tipo_compito="interfaccia",
            stato="passato", esito_gate="superato", note="Richiesta: rinomina SOGLIA | Fatto: 4 file")


_EXPORT_PY = (
    "import csv\n\n"
    "def export_csv(righe, destinazione):\n"
    "    # quoting minimo: solo dove serve, per non gonfiare il file\n"
    "    with open(destinazione, 'w', newline='') as f:\n"
    "        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)\n"
    "        w.writerow(['data', 'importo', 'categoria'])\n"
    "        w.writerows(righe)\n"
)


def _scenario_note() -> None:
    # export.py e' gia' stato creato da _scenario_git (commit 2): qui solo le note.
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


def _git(*args: str, minuti: int | None = None) -> None:
    env = None
    if minuti is not None:
        data = _ts(minuti)
        env = {"GIT_AUTHOR_DATE": data, "GIT_COMMITTER_DATE": data}
        env = {**_os_environ(), **env}
    subprocess.run(["git", "-C", str(PROGETTO), *args], check=True, capture_output=True, env=env)


def _os_environ() -> dict[str, str]:
    import os
    return dict(os.environ)


def _scenario_git() -> None:
    """Rende il progetto demo un piccolo repo git con commit datati allineati agli
    eventi del registro, cosi' la funzione "Replay di un Commit Reale" della
    dashboard ha qualcosa da riprodurre. Autore generico, niente firme."""
    (PROGETTO / "tests").mkdir(parents=True, exist_ok=True)
    (PROGETTO / "docs").mkdir(parents=True, exist_ok=True)
    (PROGETTO / "report").mkdir(parents=True, exist_ok=True)
    (PROGETTO / "report" / "__init__.py").write_text("", encoding="utf-8")
    (PROGETTO / "report" / "config.py").write_text("SOGLIA = 1000\n", encoding="utf-8")
    (PROGETTO / ".gitignore").write_text("dati_locali/\n", encoding="utf-8")

    _git("init", "-q", "-b", "main")
    _git("config", "user.name", "Squadra Demo")
    _git("config", "user.email", "demo@example.invalid")
    _git("config", "commit.gpgsign", "false")

    _git("add", "-A")
    _git("commit", "-q", "-m", "chore: avvio progetto report", minuti=5)

    (PROGETTO / "report" / "export.py").write_text(_EXPORT_PY, encoding="utf-8")
    (PROGETTO / "tests" / "test_export.py").write_text(
        "from report.export import export_csv\n\n"
        "def test_header_e_ordine_colonne(tmp_path):\n"
        "    dest = tmp_path / 'out.csv'\n"
        "    export_csv([('2026-01-01', '10.00', 'spesa')], dest)\n"
        "    assert dest.read_text().splitlines()[0] == 'data,importo,categoria'\n",
        encoding="utf-8")
    (PROGETTO / "docs" / "guida_report.md").write_text(
        "# Guida ai report\n\nL'export CSV produce le colonne data, importo, categoria.\n",
        encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-q", "-m", "feat(report): export CSV con header e quoting minimo", minuti=32)

    cfg = PROGETTO / "report" / "config.py"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("SOGLIA", "SOGLIA_IMPORTO"), encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-q", "-m", "refactor(report): rinomina SOGLIA in SOGLIA_IMPORTO", minuti=74)


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


def _elimina_progetto() -> None:
    """Rimuove la cartella del progetto demo. Gli oggetti in .git sono read-only
    su Windows e fanno fallire l'unlink: prima togli il flag da tutti i file."""
    import os
    import stat
    for radice, _dirs, file in os.walk(PROGETTO):
        for nome in file:
            try:
                os.chmod(os.path.join(radice, nome), stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(PROGETTO)


def main() -> int:
    if PROGETTO.exists():
        _elimina_progetto()
    ORCH.mkdir(parents=True, exist_ok=True)
    _scenario_git()
    _scenario_bacheca()
    _scenario_registro()
    _scenario_note()
    _registra_progetto()
    print(f"Demo allestita in {PROGETTO}")
    print("Registrata come progetto 'demo' nella dashboard, con 3 commit git da riprodurre.")
    print("Ora: python interfaccia.py  ->  http://127.0.0.1:8095  ->  seleziona 'Demo (dati finti)'")
    print("Per il replay: pannello 'Replay di un Commit Reale' -> scegli il commit 'feat(report): export CSV...'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
