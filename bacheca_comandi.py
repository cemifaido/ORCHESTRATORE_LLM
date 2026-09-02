"""Casi d'uso della CLI bacheca, separati dal parser/entrypoint."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


from registro import adesso_utc, lista_csv
from bacheca_proiezioni import (
    AGENTI_VALIDI,
    a_utc as _a_utc,
    checkpoint_ripristinabile_attivo,
    destinatari_pendenti,
    file_occupati,
    marker_quasi_riconosciuto,
    messaggi_aperti_per,
    messaggi_del_thread as _messaggi_del_thread,
    partecipanti_thread,
    riprese_pronte,
    stato_thread,
    ultimo_rilevante as _ultimo_rilevante,
    verdetto_umano_corrente,
)
from bacheca_sintesi import sintetizza_thread

RADICE = Path(__file__).resolve().parent

_bacheca_api: Any = None


def configura(api: Any) -> None:
    """Inietta il modulo bacheca per rompere il ciclo di import."""
    global _bacheca_api
    _bacheca_api = api


def _b() -> Any:
    return _bacheca_api or sys.modules.get("bacheca")


def leggi_messaggi(percorso: Path) -> list[dict[str, Any]]:
    return _b().leggi_messaggi(percorso)


def costruisci_messaggio(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _b().costruisci_messaggio(*args, **kwargs)


def aggiungi_messaggio(percorso: Path, messaggio: dict[str, Any]) -> None:
    _b().aggiungi_messaggio(percorso, messaggio)


def normalizza_agente(agente: str) -> str:
    return _b().normalizza_agente(agente)


def _default_destinatari(messaggi: list[dict[str, Any]], thread_id: str, esclusi: str) -> list[str]:
    return _b()._default_destinatari(messaggi, thread_id, esclusi)


def _formatta_per_hook(
    messaggi_pendenti: list[dict[str, Any]],
    riprese: list[dict[str, Any]] | None = None,
) -> str:
    return _b()._formatta_per_hook(messaggi_pendenti, riprese)


def _arricchisci_hook_con_profilo(testo: str, percorso_bacheca: Path) -> str:
    # Percorso canonico: <radice>/dati_locali/orchestrazione/messaggi.jsonl.
    return _b().arricchisci_hook_con_profilo(testo, percorso_bacheca.parent.parent.parent)


def _contesto_note_codice(percorso_bacheca: Path) -> str:
    """Note di codice ancorate (note_codice.py) per l'iniezione via hook. Una
    nota e' contesto, non un'istruzione; un fallimento qui non deve mai far
    fallire l'hook della bacheca."""
    try:
        import note_codice
        return note_codice.contesto_hook(percorso_bacheca.parent.parent.parent)
    except Exception:  # noqa: BLE001
        return ""


def _registra_contesto_consegna(
    percorso_bacheca: Path, agente: str, pendenti: list[dict[str, Any]]
) -> None:
    """Traccia in hook_contesto.jsonl le coppie (agente, id_messaggio) che
    finiscono nel contesto emesso: prova di `acquisito_da_hook` (vedi
    docs/RFC_STATI_CONSEGNA_RISVEGLIO.md). L'hook resta di sola aggiunta e un
    fallimento qui non deve mai far fallire l'iniezione del contesto."""
    if not pendenti:
        return
    try:
        import consegne_risveglio
        radice = _radice_progetto_da_bacheca(percorso_bacheca)
        consegne_risveglio.registra_contesto_hook(
            radice,
            [(agente, m["id_messaggio"], m["thread_id"]) for m in pendenti],
        )
    except Exception:  # noqa: BLE001
        pass


def _richiedi_thread_esistente(messaggi: list[dict[str, Any]], thread_id: str) -> None:
    _b()._richiedi_thread_esistente(messaggi, thread_id)


def _avvisa_se_marker_quasi_riconosciuto(testo: str) -> None:
    """Il marker '- passo'/'- passo e chiudo' fallisce muto se non e' sulla sua
    riga dedicata (by design, per evitare falsi positivi in prosa) - ma
    l'autore va avvisato subito, non lasciato a scoprirlo da un thread che non
    si sveglia. Su stderr apposta: non deve mai sporcare il JSON su stdout che
    altri comandi/script possono parsare."""
    if marker_quasi_riconosciuto(testo):
        print(
            "ATTENZIONE: l'ultima riga del messaggio contiene qualcosa che somiglia "
            "a '- passo'/'- passo e chiudo' ma non e' un match esatto (deve essere "
            "SOLO quello sulla sua riga, niente altro testo) - il marker NON verra' "
            "riconosciuto. Vedi docs/RFC_BACHECA_MULTIAGENTE.md §3.3bis.",
            file=sys.stderr,
        )


def comando_aggiungi(args: argparse.Namespace) -> int:
    percorso = Path(args.bacheca)
    correla_a = args.correla_a or None
    thread_id = args.thread_id or None
    if correla_a:
        # eredita il thread del messaggio correlato, come gia' fa 'rispondi' - senza
        # questo, --correla-a senza --thread-id apre per sbaglio un thread nuovo
        # invece di restare in quello originale (bug reale trovato in uso).
        correlati = [m for m in leggi_messaggi(percorso) if m["id_messaggio"] == correla_a]
        if not correlati:
            raise ValueError(f"nessun messaggio con id_messaggio={correla_a!r}")
        if not thread_id:
            thread_id = correlati[0]["thread_id"]
    messaggio = costruisci_messaggio(
        mittente=normalizza_agente(args.mittente),
        destinatari=[normalizza_agente(a) for a in lista_csv(args.destinatari)],
        tipo=args.tipo,
        testo=args.testo,
        thread_id=thread_id,
        file_modificati=lista_csv(args.file_modificati),
        riferimenti=lista_csv(args.riferimenti),
        correla_a=correla_a,
        ttl_minuti=args.ttl_minuti,
        verdetto_umano=args.verdetto_umano,
    )
    _avvisa_se_marker_quasi_riconosciuto(args.testo)
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def comando_chiedi(args: argparse.Namespace) -> int:
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    destinatari = [normalizza_agente(a) for a in lista_csv(args.a)]
    thread_id = args.thread_id or None
    if thread_id and thread_id not in {m["thread_id"] for m in messaggi}:
        raise ValueError(f"thread_id {thread_id!r} non esiste, ometti --thread-id per aprirne uno nuovo")
    messaggio = costruisci_messaggio(
        mittente="umano",
        destinatari=destinatari,
        tipo=args.tipo,
        testo=args.testo,
        thread_id=thread_id,
    )
    _avvisa_se_marker_quasi_riconosciuto(args.testo)
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def comando_prossimo(args: argparse.Namespace) -> int:
    agente = normalizza_agente(args.agente)
    percorso_bacheca = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso_bacheca)
    pendenti = messaggi_aperti_per(messaggi, agente)
    if args.formato == "hook":
        # le riprese pronte solo nel formato hook: il json resta l'elenco dei soli
        # messaggi pendenti per compatibilita' coi consumatori esistenti (RFC v2 §2.6).
        _registra_contesto_consegna(percorso_bacheca, agente, pendenti)
        testo = _arricchisci_hook_con_profilo(
            _formatta_per_hook(pendenti, riprese_pronte(messaggi, agente)), percorso_bacheca
        )
        note = _contesto_note_codice(percorso_bacheca)
        if note:
            testo = f"{testo}\n\n{note}" if testo else note
        output: dict[str, Any]
        if args.evento == "PreInvocation":
            # Antigravity (hook Gemini) usa un contratto diverso dagli altri due
            # strumenti per questo evento: injectSteps/ephemeralMessage, non
            # hookSpecificOutput/additionalContext (verificato contro lo standard
            # ufficiale di Antigravity, 2026-08-26).
            output = {"injectSteps": [{"ephemeralMessage": testo}]}
        else:
            output = {"hookSpecificOutput": {"hookEventName": args.evento, "additionalContext": testo}}
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(json.dumps(pendenti, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def comando_rispondi(args: argparse.Namespace) -> int:
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    correlati = [m for m in messaggi if m["id_messaggio"] == args.correla_a]
    if not correlati:
        raise ValueError(f"nessun messaggio con id_messaggio={args.correla_a!r}")
    originale = correlati[0]
    mittente = normalizza_agente(args.mittente)
    destinatari = (
        [normalizza_agente(a) for a in lista_csv(args.destinatari)]
        if args.destinatari
        else _default_destinatari(messaggi, originale["thread_id"], mittente)
    )
    messaggio = costruisci_messaggio(
        mittente=mittente,
        destinatari=destinatari,
        tipo="risposta",
        testo=args.testo,
        thread_id=originale["thread_id"],
        correla_a=args.correla_a,
        file_modificati=lista_csv(args.file_modificati),
    )
    _avvisa_se_marker_quasi_riconosciuto(args.testo)
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def comando_prendi(args: argparse.Namespace) -> int:
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    agente = normalizza_agente(args.agente)
    _richiedi_thread_esistente(messaggi, args.thread_id)
    correla_a = getattr(args, "correla_a", None) or None
    if correla_a is not None and not any(m["id_messaggio"] == correla_a for m in messaggi):
        raise ValueError(f"nessun messaggio con id_messaggio={correla_a!r}")
    file_nuovi = lista_csv(args.file_modificati)

    if file_nuovi:
        occupati = file_occupati(messaggi)
        collisioni = {
            f: occupati[f] for f in file_nuovi
            if f in occupati and occupati[f]["agente"] != agente
        }
        if collisioni and not args.forza:
            for f, info in collisioni.items():
                scadenza = info["scadenza"].isoformat() if info["scadenza"] else "senza scadenza"
                print(
                    f"ATTENZIONE: {f} e' gia' in carico a {info['agente']} "
                    f"(thread {info['thread_id'][:8]}, lease {scadenza}). "
                    "Usa --forza solo se l'umano ha autorizzato la sovrapposizione.",
                    file=sys.stderr,
                )
            return 1
        if collisioni:
            # datetime non e' serializzabile in JSON as-is: va convertita prima di
            # finire in metadati, altrimenti json.dumps in aggiungi_messaggio fallisce.
            occupato_da_serializzabile = {
                f: {
                    "agente": info["agente"],
                    "thread_id": info["thread_id"],
                    "scadenza": info["scadenza"].isoformat() if info["scadenza"] else None,
                }
                for f, info in collisioni.items()
            }
            metadati = {"forzato_su_conflitto": True, "occupato_da": occupato_da_serializzabile}
        else:
            metadati = {}
    else:
        metadati = {}

    destinatari = (
        [normalizza_agente(a) for a in lista_csv(args.destinatari)]
        if args.destinatari
        else _default_destinatari(messaggi, args.thread_id, agente)
    )
    messaggio = costruisci_messaggio(
        mittente=agente,
        destinatari=destinatari,
        tipo="presa_in_carico",
        testo=args.testo or f"{agente} ha preso in carico il thread",
        thread_id=args.thread_id,
        ttl_minuti=args.ttl_minuti,
        correla_a=correla_a,
        file_modificati=file_nuovi,
        metadati=metadati,
    )
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def comando_occupati(args: argparse.Namespace) -> int:
    messaggi = leggi_messaggi(Path(args.bacheca))
    occupati = file_occupati(messaggi)
    if not occupati:
        print("Nessun file attualmente in carico.")
        return 0
    print("| File | Agente | Thread | Lease fino a |")
    print("|---|---|---|---|")
    for f, info in sorted(occupati.items()):
        scadenza = info["scadenza"].isoformat() if info["scadenza"] else "senza scadenza"
        print(f"| {f} | {info['agente']} | {info['thread_id'][:8]} | {scadenza} |")
    return 0


def comando_checkpoint(args: argparse.Namespace) -> int:
    """Annotazione strutturata di avanzamento a meta' lavoro, pensata per
    sopravvivere a un'interruzione (pianificata o di emergenza) senza perdere
    contesto: obiettivo, stato, file toccati, cosa manca, test/gate, rischi,
    prossimo passo. Non chiude il thread e non ne cambia lo stato globale
    (vedi _ultimo_rilevante) - resta 'preso_in_carico' finche' non arriva una
    vera risposta/chiusura."""
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    agente = normalizza_agente(args.agente)
    _richiedi_thread_esistente(messaggi, args.thread_id)
    destinatari = (
        [normalizza_agente(a) for a in lista_csv(args.destinatari)]
        if args.destinatari
        else _default_destinatari(messaggi, args.thread_id, agente)
    )
    testo = (
        f"CHECKPOINT\n"
        f"Obiettivo: {args.obiettivo or '(non specificato)'}\n"
        f"Stato attuale: {args.stato_attuale or '(non specificato)'}\n"
        f"File toccati: {args.file_modificati or '(nessuno)'}\n"
        f"Cosa manca: {args.manca or '(non specificato)'}\n"
        f"Test/gate: {args.test or '(non eseguiti/non specificato)'}\n"
        f"Rischi: {args.rischi or '(nessuno segnalato)'}\n"
        f"Prossimo passo: {args.prossimo_passo or '(non specificato)'}"
    )
    ripresa = None
    # getattr coi default: i campi della ripresa sono opzionali anche per chi
    # costruisce argparse.Namespace a mano (test, usi programmatici pre-v2).
    if getattr(args, "attende", ""):
        # checkpoint RIPRISTINABILE (v2): la validazione dei vincoli (oggetto_atteso
        # non vuoto, tutti e tre gli esiti se attende=umano) la fa lo schema in
        # aggiungi_messaggio - qui si costruisce soltanto.
        azioni: dict[str, str] = {}
        if getattr(args, "se_approvato", ""):
            azioni["approvato"] = args.se_approvato
        if getattr(args, "se_respinto", ""):
            azioni["respinto"] = args.se_respinto
        if getattr(args, "se_modifiche_richieste", ""):
            azioni["modifiche_richieste"] = args.se_modifiche_richieste
        for coppia in getattr(args, "esito", []):
            nome, separatore, azione = coppia.partition("=")
            if not separatore or not nome.strip() or not azione.strip():
                raise ValueError(f"--esito richiede il formato nome=azione, ricevuto {coppia!r}")
            azioni[nome.strip()] = azione.strip()
        ripresa = {
            "attende": args.attende,
            "oggetto_atteso": getattr(args, "oggetto_atteso", ""),
            "azioni_per_esito": azioni,
            "contesto_minimo": {
                "thread_id": args.thread_id,
                "riferimenti": lista_csv(getattr(args, "contesto_riferimenti", "")),
                "comandi_consentiti": lista_csv(getattr(args, "comandi_consentiti", "")),
            },
        }
    messaggio = costruisci_messaggio(
        mittente=agente,
        destinatari=destinatari,
        tipo="checkpoint",
        testo=testo,
        thread_id=args.thread_id,
        file_modificati=lista_csv(args.file_modificati),
        ripresa=ripresa,
    )
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _thread_ancora_da_riprendere(messaggi: list[dict[str, Any]]) -> list[str]:
    thread_ids = sorted({m["thread_id"] for m in messaggi})
    return [tid for tid in thread_ids if stato_thread(messaggi, tid) not in ("chiuso", "annullato", "inesistente")]


def comando_ripresa(args: argparse.Namespace) -> int:
    """Vista dei thread e delle riprese rimasti appesi dopo un'interruzione."""
    messaggi = leggi_messaggi(Path(args.bacheca))
    aperti = _thread_ancora_da_riprendere(messaggi)
    riprese_per_agente = {
        agente: riprese_pronte(messaggi, agente)
        for agente in sorted(set(AGENTI_VALIDI) - {"umano", "sistema"})
    }
    riprese_presenti = any(riprese_per_agente.values())
    if not aperti and not riprese_presenti:
        print("Nessun thread aperto o in carico: nulla da riprendere.")
        return 0

    if riprese_presenti:
        print("== Riprese pronte (verdetto arrivato, non ancora eseguite) ==")
        for agente, riprese in riprese_per_agente.items():
            for ripresa in riprese:
                checkpoint = ripresa["checkpoint"]
                azione = ripresa["azione"] or "(nessuna azione prevista per questo esito: rileggere il thread)"
                print(f"- {agente}: thread {checkpoint['thread_id'][:8]}, esito {ripresa['verdetto']}: {azione}")
        print()
    if not aperti:
        return 0

    adesso = datetime.now(timezone.utc)
    print("== Thread ancora aperti o in carico ==")
    print("| Thread | Stato | Lease | File dichiarati | Ultimo mittente |")
    print("|---|---|---|---|---|")
    for thread_id in aperti:
        stato = stato_thread(messaggi, thread_id)
        ultimo = _messaggi_del_thread(messaggi, thread_id)[-1]
        rilevante = _ultimo_rilevante(messaggi, thread_id)
        lease = "-"
        if stato == "preso_in_carico" and rilevante["ttl_minuti"] is not None:
            scadenza = _a_utc(rilevante["timestamp"]) + timedelta(minutes=rilevante["ttl_minuti"])
            lease = "SCADUTO" if scadenza < adesso else scadenza.isoformat()
        file_dichiarati = ", ".join(rilevante["file_modificati"]) or "(nessuno)"
        print(f"| {thread_id[:8]} | {stato} | {lease} | {file_dichiarati} | {ultimo['mittente']} |")

    occupati_attivi = file_occupati(messaggi, adesso=adesso)
    print("\n== File con lease ancora attivo ==")
    if occupati_attivi:
        for file, info in sorted(occupati_attivi.items()):
            print(f"- {file}: {info['agente']} (thread {info['thread_id'][:8]})")
    else:
        print("Nessuno.")
    print(
        "\nAzione consigliata: per ogni thread sopra esegui "
        "'bacheca.py thread <id>' per la cronologia completa, poi decidi se "
        "continuare con lo stesso agente, riassegnare, chiudere se non serve piu', "
        "o chiedere review se ci sono file modificati non verificati. Controlla "
        "anche 'git status'/'git diff' per modifiche non ancora registrate in bacheca."
    )
    return 0


def comando_emergenza(args: argparse.Namespace) -> int:
    """Spegnimento in emergenza: non prova a 'finire bene' il lavoro, lascia un
    segnale minimo ma chiaro. Scrive un checkpoint in bacheca indirizzato a tutti
    gli agenti, salva 'git status --short' su file (best-effort: se git non e'
    disponibile o fallisce, lo annota e prosegue comunque - il checkpoint in
    bacheca non deve dipendere da git) ed elenca i thread ancora da riprendere."""
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    testo = args.testo or "Spegnimento di emergenza, nessun dettaglio fornito."

    try:
        esito = subprocess.run(
            ["git", "status", "--short"], capture_output=True, text=True, timeout=10, cwd=RADICE,
        )
        stato_git = esito.stdout.strip() or "(working tree pulito)"
    except Exception as errore:
        stato_git = f"(impossibile eseguire git status: {errore})"

    aperti = _thread_ancora_da_riprendere(messaggi)
    percorso_snapshot = Path(args.bacheca).parent / "ultimo_checkpoint_emergenza.txt"
    contenuto_snapshot = (
        f"CHECKPOINT EMERGENZA - {adesso_utc()}\n\n"
        f"{testo}\n\n"
        f"git status --short:\n{stato_git}\n\n"
        f"Thread ancora aperti/in carico: {', '.join(t[:8] for t in aperti) or 'nessuno'}\n"
        "Considerare tutto il lavoro in corso come non verificato fino a controllo.\n"
    )
    percorso_snapshot.parent.mkdir(parents=True, exist_ok=True)
    percorso_snapshot.write_text(contenuto_snapshot, encoding="utf-8")

    destinatari = sorted(set(AGENTI_VALIDI) - {"umano", "sistema"})
    messaggio = costruisci_messaggio(
        mittente="umano",
        destinatari=destinatari,
        tipo="checkpoint",
        testo=(
            f"CHECKPOINT EMERGENZA: {testo} Alla ripresa esegui 'git status' e "
            f"'bacheca.py ripresa'. Dettagli completi in {percorso_snapshot.name}. "
            "Tutto il lavoro in corso va considerato non verificato."
        ),
        metadati={"emergenza": True, "thread_ancora_aperti": aperti},
    )
    aggiungi_messaggio(percorso, messaggio)

    print(f"Checkpoint di emergenza scritto in bacheca e in {percorso_snapshot}.")
    print(contenuto_snapshot)
    return 0


def comando_sintetizza(args: argparse.Namespace) -> int:
    """Unico comando di bacheca.py che chiama il modello locale. Scrive sempre come
    mittente='locale' (mai mascherato da altro agente o dall'umano - RFC §3.6): un
    conflitto rilevato diventa un messaggio 'segnalazione_conflitto' indirizzato
    anche a 'umano' (mai una sentenza, solo un allarme - §6.2/§7); altrimenti una
    normale 'sintesi' indirizzata ai partecipanti del thread."""
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    if not _messaggi_del_thread(messaggi, args.thread_id):
        print(f"nessun messaggio per thread_id={args.thread_id!r}", file=sys.stderr)
        return 1

    risultato = sintetizza_thread(messaggi, args.thread_id, modello=args.modello or None)
    if not risultato["ok"]:
        print(f"errore: {risultato['errore']}", file=sys.stderr)
        return 1

    metadati = {
        "fonte": "locale",
        "modello_locale": risultato["modello"],
        "token_totali": risultato["token_totali"],
    }
    partecipanti = partecipanti_thread(messaggi, args.thread_id) - {"locale"}
    if risultato["conflitto"]:
        messaggio = costruisci_messaggio(
            mittente="locale",
            destinatari=sorted(partecipanti | {"umano"}),
            tipo="segnalazione_conflitto",
            testo=f"{risultato['sintesi']}\n\nPOSSIBILE CONFLITTO: {risultato['conflitto']}",
            thread_id=args.thread_id,
            metadati=metadati,
        )
    else:
        messaggio = costruisci_messaggio(
            mittente="locale",
            destinatari=sorted(partecipanti) or ["umano"],
            tipo="sintesi",
            testo=risultato["sintesi"],
            thread_id=args.thread_id,
            metadati=metadati,
        )
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _chiudi(args: argparse.Namespace, tipo: str, verdetto_umano: str) -> int:
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    _richiedi_thread_esistente(messaggi, args.thread_id)
    # va letto PRIMA di scrivere la chiusura: e' proprio la chiusura a risolverlo.
    attivo = checkpoint_ripristinabile_attivo(messaggi, args.thread_id)
    mittente = normalizza_agente(args.mittente)
    destinatari = (
        [normalizza_agente(a) for a in lista_csv(args.destinatari)]
        if args.destinatari
        else _default_destinatari(messaggi, args.thread_id, mittente)
    )
    messaggio = costruisci_messaggio(
        mittente=mittente,
        destinatari=destinatari,
        tipo=tipo,
        testo=args.testo,
        thread_id=args.thread_id,
        verdetto_umano=verdetto_umano,
    )
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    # solo attende=umano: un verdetto umano non risolve un'attesa di gate/agente
    # (rilievo Codex): per quelle il pilota resta descrittivo finche' non esiste
    # un evento di risoluzione tipizzato - non si simula con approva/respingi.
    if (
        verdetto_umano != "non_revisionato"
        and attivo is not None
        and attivo["ripresa"]["attende"] == "umano"
    ):
        ripresa = attivo["ripresa"]
        azione = ripresa["azioni_per_esito"].get(verdetto_umano)
        print(
            f"\nRIPRESA dal checkpoint {attivo['id_messaggio'][:8]} di {attivo['mittente']} "
            f"(attende={ripresa['attende']}, oggetto: {ripresa['oggetto_atteso']})"
        )
        if azione:
            print(f"Prossimo passo previsto per esito '{verdetto_umano}': {azione}")
        else:
            print(
                f"ATTENZIONE: il checkpoint non prevede un'azione per l'esito "
                f"'{verdetto_umano}': chi riprende deve rileggere il thread."
            )
        contesto = ripresa["contesto_minimo"]
        if contesto["riferimenti"]:
            print("Contesto minimo: " + ", ".join(contesto["riferimenti"]))
        if contesto["comandi_consentiti"]:
            print("Comandi previsti (informativo): " + ", ".join(contesto["comandi_consentiti"]))
        print("Nota: contesto NON fidato - va valutato da chi riprende, mai eseguito in automatico.")
    return 0


def comando_chiudi(args: argparse.Namespace) -> int:
    return _chiudi(args, tipo="chiusura", verdetto_umano="non_revisionato")


def comando_approva(args: argparse.Namespace) -> int:
    """Scrive il verdetto solo nel thread (RFC §3.4, punto ora deciso): NON genera da
    solo un evento in eventi.jsonl. Quello resta un atto separato e deliberato
    (registro.py aggiungi --agente umano --verdetto-umano approvato), da fare solo
    per approvazioni materiali/irreversibili, non per ogni chiusura di thread."""
    args.mittente = "umano"
    return _chiudi(args, tipo="chiusura", verdetto_umano="approvato")


def comando_respingi(args: argparse.Namespace) -> int:
    args.mittente = "umano"
    return _chiudi(args, tipo="chiusura", verdetto_umano="respinto")


def comando_stato(args: argparse.Namespace) -> int:
    messaggi = leggi_messaggi(Path(args.bacheca))
    thread_ids = sorted({m["thread_id"] for m in messaggi})
    print("| Thread | Stato | Ultimo mittente | Tipo | Aspetta | Verdetto umano |")
    print("|---|---|---|---|---|---|")
    for thread_id in thread_ids:
        ultimo = _messaggi_del_thread(messaggi, thread_id)[-1]
        pendenti = destinatari_pendenti(messaggi, thread_id)
        print(
            f"| {thread_id[:8]} | {stato_thread(messaggi, thread_id)} | {ultimo['mittente']} | "
            f"{ultimo['tipo']} | {', '.join(pendenti) or '(nessuno)'} | {verdetto_umano_corrente(messaggi, thread_id)} |"
        )
    return 0


def _risolvi_thread_id(messaggi: list[dict[str, Any]], thread_id: str) -> str:
    """Risolve un thread_id esatto o per prefisso univoco (es. 8 caratteri da riepilogo)."""
    if any(m["thread_id"] == thread_id for m in messaggi):
        return thread_id
    corrispondenze = sorted({m["thread_id"] for m in messaggi if m["thread_id"].startswith(thread_id)})
    if len(corrispondenze) == 1:
        return corrispondenze[0]
    return thread_id


def comando_thread(args: argparse.Namespace) -> int:
    messaggi = leggi_messaggi(Path(args.bacheca))
    thread_id = _risolvi_thread_id(messaggi, args.thread_id)
    cronologia = _messaggi_del_thread(messaggi, thread_id)
    if not cronologia:
        print(f"nessun messaggio per thread_id={args.thread_id!r}", file=sys.stderr)
        return 1
    for m in cronologia:
        print(f"[{m['timestamp']}] {m['mittente']} -> {', '.join(m['destinatari'])} ({m['tipo']}): {m['testo']}")
    print(f"\nStato globale: {stato_thread(messaggi, thread_id)}")
    print(f"Verdetto umano corrente: {verdetto_umano_corrente(messaggi, thread_id)}")
    return 0


def comando_riepilogo(args: argparse.Namespace) -> int:
    return comando_stato(args)


def errori_cross_record(messaggi: list[dict[str, Any]], radice_progetto: Path) -> list[str]:
    """Controlli che il singolo schema per-messaggio non puo' fare (RFC v2 §2.3):
    coerenza del thread dichiarato in contesto_minimo ed esistenza dei riferimenti
    (file nel progetto, URL, o id di messaggi/thread gia' in bacheca)."""
    errori: list[str] = []
    id_noti = {m["id_messaggio"] for m in messaggi} | {m["thread_id"] for m in messaggi}
    for m in messaggi:
        ripresa = m.get("ripresa")
        if not ripresa:
            continue
        contesto = ripresa["contesto_minimo"]
        if contesto["thread_id"] != m["thread_id"]:
            errori.append(
                f"messaggio {m['id_messaggio'][:8]}: contesto_minimo.thread_id "
                f"{contesto['thread_id'][:8]!r} diverso dal thread del messaggio {m['thread_id'][:8]!r}"
            )
        for riferimento in contesto["riferimenti"]:
            if riferimento.startswith(("http://", "https://")):
                continue
            if riferimento in id_noti:
                continue
            if (radice_progetto / riferimento).exists():
                continue
            errori.append(
                f"messaggio {m['id_messaggio'][:8]}: riferimento {riferimento!r} "
                "inesistente (ne' file nel progetto, ne' URL, ne' id noto alla bacheca)"
            )
    return errori


def _radice_progetto_da_bacheca(percorso: Path) -> Path:
    """Il layout standard e' <progetto>/dati_locali/orchestrazione/messaggi.jsonl:
    in quel caso la radice per risolvere i riferimenti relativi e' <progetto>.
    Per bacheche in percorsi arbitrari (test, usi ad hoc) si usa la cartella
    del file stesso, cosi' il comportamento resta deterministico."""
    risolto = percorso.resolve()
    if risolto.parent.name == "orchestrazione" and risolto.parent.parent.name == "dati_locali":
        return risolto.parent.parent.parent
    return risolto.parent


def comando_valida(args: argparse.Namespace) -> int:
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    errori = errori_cross_record(messaggi, _radice_progetto_da_bacheca(percorso))
    if errori:
        for errore in errori:
            print(f"errore cross-record: {errore}", file=sys.stderr)
        return 1
    print(f"bacheca valida: {len(messaggi)} messaggi")
    return 0
