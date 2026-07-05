#!/usr/bin/env python3
"""Bacheca multi-agente: messaggistica strutturata fra Claude/Codex/Gemini/locale/umano,
senza hook (vedi docs/RFC_BACHECA_MULTIAGENTE.md). Mirror strutturale di registro.py,
stesso stile e stesse funzioni di validazione condivise.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))

from registro import _messaggio_errore, _validatore_per_schema, adesso_utc, lista_csv  # noqa: E402
from adattatori import litellm  # noqa: E402

PERCORSO_BACHECA_PREDEFINITO = Path("dati_locali") / "orchestrazione" / "messaggi.jsonl"
PERCORSO_SCHEMA_MESSAGGIO = RADICE / "schema" / "messaggio.v1.json"

AGENTI_VALIDI = ("gemini", "claude", "codex", "locale", "umano", "sistema")
TIPI_VALIDI = (
    "richiesta", "risposta", "domanda", "sintesi",
    "presa_in_carico", "chiusura", "annullamento", "segnalazione_conflitto",
    "checkpoint",
)
VERDETTI_VALIDI = ("non_revisionato", "approvato", "respinto", "modifiche_richieste")

# tipi che lasciano un thread "aperto" (in attesa di reazione) finche' non arriva
# una risposta/presa in carico/chiusura - segnalazione_conflitto e' trattato come
# apertura perche' aspetta comunque una reazione (di norma dall'umano). 'checkpoint'
# c'e' per far risultare 'pending' i suoi destinatari (ripresa via hook), ma NON
# influenza lo stato GLOBALE del thread: stato_thread lo salta esplicitamente
# tramite _ultimo_rilevante, sono due assi indipendenti (vedi RFC).
TIPI_APERTURA = {"richiesta", "domanda", "sintesi", "segnalazione_conflitto", "checkpoint"}


def carica_schema_messaggio(percorso: Path = PERCORSO_SCHEMA_MESSAGGIO) -> dict[str, Any]:
    return json.loads(percorso.read_text(encoding="utf-8"))


def valida_messaggio(messaggio: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    schema = schema or carica_schema_messaggio()
    validatore = _validatore_per_schema(schema)
    errori = sorted(validatore.iter_errors(messaggio), key=lambda e: list(e.absolute_path))
    return [_messaggio_errore(errore, messaggio) for errore in errori]


def aggiungi_messaggio(percorso: Path, messaggio: dict[str, Any]) -> None:
    errori = valida_messaggio(messaggio)
    if errori:
        raise ValueError("; ".join(errori))
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with percorso.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(messaggio, ensure_ascii=False, sort_keys=True))
        file.write("\n")


def leggi_messaggi(percorso: Path) -> list[dict[str, Any]]:
    if not percorso.exists():
        return []
    messaggi: list[dict[str, Any]] = []
    with percorso.open("r", encoding="utf-8") as file:
        for numero_riga, riga in enumerate(file, start=1):
            riga = riga.strip()
            if not riga:
                continue
            try:
                messaggio = json.loads(riga)
            except json.JSONDecodeError as errore:
                raise ValueError(f"JSON non valido alla riga {numero_riga}: {errore}") from errore
            errori = valida_messaggio(messaggio)
            if errori:
                raise ValueError(f"messaggio non valido alla riga {numero_riga}: {'; '.join(errori)}")
            messaggi.append(messaggio)
    return messaggi


def leggi_messaggi_progetto(percorso_progetto: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Legge i messaggi di un progetto. Ritorna (messaggi, errore): errore e' None solo
    se la bacheca non esiste ancora (progetto nuovo, o non ha mai usato bacheca.py) o
    e' stata letta senza problemi. Stesso pattern difensivo di
    registro.leggi_eventi_progetto(): una bacheca corrotta non deve sembrare un
    progetto senza messaggi ne' far cadere chi la consuma (es. la dashboard)."""
    percorso_messaggi = percorso_progetto / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
    if not percorso_messaggi.exists():
        return [], None
    try:
        return leggi_messaggi(percorso_messaggi), None
    except Exception as errore:
        return [], f"bacheca corrotta ({percorso_messaggi}): {errore}"


def normalizza_agente(valore: str) -> str:
    """Case-insensitive: il modello locale a volte restituisce nomi con maiuscola
    (es. 'Gemini' invece di 'gemini') - vedi RFC §3.4, correzione di parsing nota."""
    valore_norm = valore.strip().lower()
    if valore_norm not in AGENTI_VALIDI:
        raise ValueError(f"agente non valido: {valore!r} (ammessi: {', '.join(AGENTI_VALIDI)})")
    return valore_norm


def costruisci_messaggio(
    *,
    mittente: str,
    destinatari: list[str],
    tipo: str,
    testo: str,
    thread_id: str | None = None,
    file_modificati: list[str] | None = None,
    riferimenti: list[str] | None = None,
    correla_a: str | None = None,
    ttl_minuti: int | None = None,
    verdetto_umano: str = "non_revisionato",
    metadati: dict[str, Any] | None = None,
) -> dict[str, Any]:
    id_messaggio = str(uuid.uuid4())
    return {
        "versione_schema": 1,
        "id_messaggio": id_messaggio,
        "thread_id": thread_id or id_messaggio,
        "timestamp": adesso_utc(),
        "mittente": mittente,
        "destinatari": destinatari,
        "tipo": tipo,
        "testo": testo,
        "file_modificati": file_modificati or [],
        "riferimenti": riferimenti or [],
        "correla_a": correla_a,
        "ttl_minuti": ttl_minuti,
        "verdetto_umano": verdetto_umano,
        "metadati": metadati or {},
    }


def _messaggi_del_thread(messaggi: list[dict[str, Any]], thread_id: str) -> list[dict[str, Any]]:
    rilevanti = [m for m in messaggi if m["thread_id"] == thread_id]
    rilevanti.sort(key=lambda m: m["timestamp"])
    return rilevanti


def partecipanti_thread(messaggi: list[dict[str, Any]], thread_id: str) -> set[str]:
    partecipanti: set[str] = set()
    for m in _messaggi_del_thread(messaggi, thread_id):
        partecipanti.add(m["mittente"])
        partecipanti.update(m["destinatari"])
    return partecipanti


def _ultimo_rilevante(messaggi: list[dict[str, Any]], thread_id: str) -> dict[str, Any]:
    """L'ultimo messaggio che determina lo STATO GLOBALE del thread, ignorando
    eventuali 'checkpoint' successivi: un checkpoint e' un'annotazione di
    avanzamento, non una transizione di stato - non deve far tornare 'aperto' un
    thread gia' preso in carico. Se il thread ha solo checkpoint (caso limite),
    ritorna comunque l'ultimo messaggio in assoluto invece di sollevare un errore."""
    rilevanti = _messaggi_del_thread(messaggi, thread_id)
    non_checkpoint = [m for m in rilevanti if m["tipo"] != "checkpoint"]
    return non_checkpoint[-1] if non_checkpoint else rilevanti[-1]


def stato_thread(messaggi: list[dict[str, Any]], thread_id: str) -> str:
    """Stato GLOBALE derivato dall'ultimo messaggio pertinente (pure event-sourcing:
    nessun campo di stato viene mai scritto nel record - RFC §3.3)."""
    rilevanti = _messaggi_del_thread(messaggi, thread_id)
    if not rilevanti:
        return "inesistente"
    tipo = _ultimo_rilevante(messaggi, thread_id)["tipo"]
    if tipo in TIPI_APERTURA:
        return "aperto"
    if tipo == "presa_in_carico":
        return "preso_in_carico"
    if tipo == "risposta":
        return "risposto"
    if tipo == "chiusura":
        return "chiuso"
    if tipo == "annullamento":
        return "annullato"
    return "sconosciuto"


def stato_per_destinatario(messaggi: list[dict[str, Any]], thread_id: str, agente: str) -> str:
    """Stato PER DESTINATARIO (RFC §3.3): risolve l'ambiguita' di 'ultimo messaggio
    pertinente' su thread con piu' destinatari - un thread globalmente 'risposto' da
    un agente puo' avere un altro agente ancora 'pending'. 'pending' solo se l'agente
    e' stato indirizzato da un messaggio di tipo "apertura" (TIPI_APERTURA: richiesta/
    domanda/sintesi/segnalazione_conflitto - stesso set che tiene aperto il thread a
    livello globale) piu' di recente di quanto lui stesso abbia scritto nel thread.
    Una 'risposta' o una 'chiusura' indirizzata a qualcuno NON lo rende pending: e'
    terminale/informativa, non una richiesta di reazione (altrimenti chi ha appena
    fatto una domanda risulterebbe sempre 'pending' solo perche' ha ricevuto la
    risposta indirizzata a lui, rumore che va contro il principio "pull, non ogni
    messaggio richiede una reazione" - RFC §3.6)."""
    rilevanti = _messaggi_del_thread(messaggi, thread_id)
    if not rilevanti:
        return "inesistente"
    if stato_thread(messaggi, thread_id) in ("chiuso", "annullato"):
        return "resolved"

    # Indice nella lista ordinata, non il timestamp come stringa: adesso_utc() ha
    # precisione al secondo, quindi messaggi scritti nello stesso secondo (comune
    # anche in produzione con scritture ravvicinate, non solo nei test) avrebbero
    # timestamp identici - un confronto ">" fra stringhe uguali e' sempre falso e
    # sbaglierebbe silenziosamente verso 'resolved'. _messaggi_del_thread ordina in
    # modo stabile, quindi l'indice riflette l'ordine reale anche a parita' di
    # timestamp.
    indice_indirizzato_apertura: int | None = None
    indice_inviato: int | None = None
    for i, m in enumerate(rilevanti):
        if agente in m["destinatari"] and m["tipo"] in TIPI_APERTURA:
            indice_indirizzato_apertura = i
        if m["mittente"] == agente:
            indice_inviato = i

    if indice_indirizzato_apertura is None:
        return "resolved"
    if indice_inviato is None:
        return "pending"
    return "pending" if indice_indirizzato_apertura > indice_inviato else "resolved"


def destinatari_pendenti(messaggi: list[dict[str, Any]], thread_id: str) -> list[str]:
    """prossimo_destinatario e' sempre derivato cosi', mai chiesto al modello locale
    (RFC §6.1: lo spike ha mostrato che anche con un prompt buono il modello puo'
    sbagliare l'instradamento). Nota: va controllato ogni partecipante mai
    interpellato nel thread, non solo i destinatari dell'ultimo messaggio - un
    thread con [claude, codex] dove risponde solo claude ha come ultimo messaggio
    quello di claude (indirizzato a 'umano'), ma codex resta comunque pending."""
    if not _messaggi_del_thread(messaggi, thread_id):
        return []
    return sorted(
        agente for agente in partecipanti_thread(messaggi, thread_id)
        if stato_per_destinatario(messaggi, thread_id, agente) == "pending"
    )


def verdetto_umano_corrente(messaggi: list[dict[str, Any]], thread_id: str) -> str:
    """Il verdetto CORRENTE del thread e' l'ultimo verdetto_umano != non_revisionato
    (RFC §3.2): un vecchio messaggio approvato non va confuso con l'ultimo messaggio
    operativo, che puo' avere solo il default."""
    for m in reversed(_messaggi_del_thread(messaggi, thread_id)):
        if m["verdetto_umano"] != "non_revisionato":
            return m["verdetto_umano"]
    return "non_revisionato"


def _a_utc(timestamp_iso: str) -> datetime:
    """Converte un timestamp ISO8601 ('Z', come quelli emessi da adesso_utc()) in un
    datetime timezone-aware UTC. Stesso pattern gia' usato in commit_replay.py per lo
    stesso motivo: confrontare stringhe grezze o mescolare naive/aware sarebbe
    sbagliato per calcolare la scadenza di un lease."""
    normalizzato = timestamp_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalizzato)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def file_occupati(messaggi: list[dict[str, Any]], adesso: datetime | None = None) -> dict[str, dict[str, Any]]:
    """File attualmente in carico (RFC: coordinamento cooperativo, non un lock del
    filesystem). Considera solo thread ancora nello stato globale 'preso_in_carico'
    (una risposta o chiusura successiva rilascia gia' il claim da sola, tramite
    stato_thread - non serve un rilascio esplicito separato) e con lease non scaduto
    (se ttl_minuti e' None il claim non scade mai). Ritorna {file: {agente,
    thread_id, scadenza}}, scadenza=None se senza ttl."""
    adesso = adesso or datetime.now(timezone.utc)
    per_thread: dict[str, list[dict[str, Any]]] = {}
    for m in messaggi:
        per_thread.setdefault(m["thread_id"], []).append(m)

    occupati: dict[str, dict[str, Any]] = {}
    for thread_id, gruppo in per_thread.items():
        if stato_thread(messaggi, thread_id) != "preso_in_carico":
            continue
        ultimo = _ultimo_rilevante(messaggi, thread_id)  # il presa_in_carico, anche se seguito da checkpoint
        scadenza = None
        if ultimo["ttl_minuti"] is not None:
            scadenza = _a_utc(ultimo["timestamp"]) + timedelta(minutes=ultimo["ttl_minuti"])
            if scadenza < adesso:
                continue  # lease scaduto: non conta piu' come occupato
        for file in ultimo["file_modificati"]:
            occupati[file] = {"agente": ultimo["mittente"], "thread_id": thread_id, "scadenza": scadenza}
    return occupati


def messaggi_aperti_per(messaggi: list[dict[str, Any]], agente: str) -> list[dict[str, Any]]:
    """Vista PER DESTINATARIO usata da 'prossimo --agente X' (compreso --formato hook):
    l'ultimo messaggio di ogni thread in cui 'agente' e' ancora pending."""
    per_thread: dict[str, list[dict[str, Any]]] = {}
    for m in messaggi:
        per_thread.setdefault(m["thread_id"], []).append(m)

    risultato = []
    for thread_id in per_thread:
        if stato_per_destinatario(messaggi, thread_id, agente) == "pending":
            risultato.append(_messaggi_del_thread(messaggi, thread_id)[-1])
    risultato.sort(key=lambda m: m["timestamp"])
    return risultato


def _formatta_per_hook(messaggi_pendenti: list[dict[str, Any]]) -> str:
    """Testo compatto per additionalContext (limite 10.000 caratteri lato Claude Code
    - RFC §4.2): solo thread aperti/pendenti, non l'intero storico."""
    if not messaggi_pendenti:
        return ""
    righe = ["Messaggi in bacheca in attesa di una tua reazione:"]
    for m in messaggi_pendenti:
        righe.append(f"- [{m['mittente']} -> te] ({m['tipo']}, thread {m['thread_id'][:8]}): {m['testo']}")
    return "\n".join(righe)


# Prompt e esempio one-shot gia' validati in esempi/spike_dispatcher_locale.py:
# senza esempio il modello locale non rilevava nessun conflitto (0/3 thread di
# prova); con l'esempio, 2/3 modelli testati lo rilevavano su tutti i thread (RFC
# §6.2/§6.3). Deliberatamente NIENTE 'prossimo_destinatario' qui: RFC §6.1, resta
# sempre derivato deterministicamente da destinatari_pendenti/stato_per_destinatario,
# mai chiesto al modello - lo spike ha mostrato che anche con un prompt buono il
# modello locale puo' sbagliare l'instradamento.
PROMPT_SISTEMA_DISPATCHER = (
    "Sei un dispatcher di messaggistica tecnica tra agenti AI (claude, codex, gemini) "
    "e un umano. Ricevi la cronologia di un thread e devi SOLO analizzarla, non agire. "
    "Rispondi ESCLUSIVAMENTE con un oggetto JSON, senza altro testo, con due chiavi: "
    '"sintesi" (una frase breve in italiano su cosa dice il thread), '
    '"conflitto" (null se non ce n\'e\' uno, altrimenti una frase breve che lo descrive). '
    "Un conflitto e' quando due mittenti affermano fatti incompatibili sulla STESSA cosa "
    "concreta (stesso file, stesso test, stesso stato di una funzionalita'): non basta "
    "che stiano semplicemente discutendo o siano in disaccordo su un'opinione."
)
ESEMPIO_THREAD_DISPATCHER = (
    "[claude -> umano] (risposta) Ho verificato che test_login passa in locale con Python 3.11.\n"
    "[codex -> umano] (risposta) Ho eseguito lo stesso test_login e fallisce con un TypeError in Python 3.11."
)
ESEMPIO_OUTPUT_DISPATCHER = {
    "sintesi": "Claude e Codex riportano esiti opposti sullo stesso test nello stesso ambiente.",
    "conflitto": "Claude dice che test_login passa, Codex dice che fallisce con un TypeError: stesso test, stesso ambiente, esiti incompatibili.",
}


def _formatta_thread_per_dispatcher(messaggi_thread: list[dict[str, Any]]) -> str:
    righe = []
    for m in messaggi_thread:
        righe.append(f"[{m['mittente']} -> {', '.join(m['destinatari'])}] ({m['tipo']}) {m['testo']}")
    return "\n".join(righe)


def sintetizza_thread(
    messaggi: list[dict[str, Any]], thread_id: str, modello: str | None = None
) -> dict[str, Any]:
    """Chiama il modello locale per sintetizzare un thread e segnalare un eventuale
    conflitto - mai per decidere prossimo_destinatario (§6.1) ne' per agire. In caso
    di dubbio (modello irraggiungibile, risposta non interpretabile) ritorna sempre
    ok=False: non si inventa una sintesi ne' si nasconde un problema dietro un
    parsing fallito, stesso principio di triage_locale.classifica()."""
    testo_thread = _formatta_thread_per_dispatcher(_messaggi_del_thread(messaggi, thread_id))
    messaggi_prompt = [
        {"role": "system", "content": PROMPT_SISTEMA_DISPATCHER},
        {"role": "user", "content": f"Thread da analizzare:\n{ESEMPIO_THREAD_DISPATCHER}"},
        {"role": "assistant", "content": json.dumps(ESEMPIO_OUTPUT_DISPATCHER, ensure_ascii=False)},
        {"role": "user", "content": f"Thread da analizzare:\n{testo_thread}"},
    ]
    parametri: dict[str, Any] = {"messaggi": messaggi_prompt, "max_tokens": 200, "temperature": 0.0}
    if modello:
        parametri["modello"] = modello

    try:
        risposta, misurazione = litellm.completamento_locale(**parametri)
    except Exception as errore:
        return {"ok": False, "errore": f"modello locale non raggiungibile: {errore}"}

    testo = litellm.testo_da_risposta(risposta)
    try:
        inizio = testo.index("{")
        fine = testo.rindex("}") + 1
        dati = json.loads(testo[inizio:fine])
        sintesi = str(dati.get("sintesi", "")).strip()
        if not sintesi:
            raise ValueError("campo 'sintesi' mancante o vuoto")
        conflitto = dati.get("conflitto")
        if conflitto in (None, "null", ""):
            # correzione di parsing nota (RFC §3.4): il modello a volte restituisce
            # la stringa "null" invece del null JSON vero.
            conflitto = None
        else:
            conflitto = str(conflitto).strip()
        return {
            "ok": True,
            "sintesi": sintesi,
            "conflitto": conflitto,
            "token_totali": misurazione.token_totali,
            "modello": misurazione.modello,
        }
    except Exception as errore:
        return {"ok": False, "errore": f"risposta locale non interpretabile: {testo[:300]} ({errore})"}


def _default_destinatari(messaggi: list[dict[str, Any]], thread_id: str, esclusi: str) -> list[str]:
    destinatari = sorted(partecipanti_thread(messaggi, thread_id) - {esclusi})
    if not destinatari:
        raise ValueError(
            "impossibile dedurre i destinatari di default (thread senza altri partecipanti): "
            "specifica --destinatari esplicitamente"
        )
    return destinatari


def _richiedi_thread_esistente(messaggi: list[dict[str, Any]], thread_id: str) -> None:
    if not _messaggi_del_thread(messaggi, thread_id):
        raise ValueError(f"thread_id {thread_id!r} non esiste")


# --------------------------------------------------------------------------
# Comandi CLI
# --------------------------------------------------------------------------


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
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def comando_prossimo(args: argparse.Namespace) -> int:
    agente = normalizza_agente(args.agente)
    messaggi = leggi_messaggi(Path(args.bacheca))
    pendenti = messaggi_aperti_per(messaggi, agente)
    if args.formato == "hook":
        testo = _formatta_per_hook(pendenti)
        # hookEventName deve combaciare con l'evento reale che ha invocato l'hook
        # (SessionStart/UserPromptSubmit/BeforeAgent), passato da chi configura
        # l'hook - "prossimo" non e' un evento riconosciuto da nessuno dei tre
        # strumenti, non andava hardcoded.
        output = (
            {"hookSpecificOutput": {"hookEventName": args.evento, "additionalContext": testo}}
            if testo
            else {}
        )
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
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def comando_prendi(args: argparse.Namespace) -> int:
    percorso = Path(args.bacheca)
    messaggi = leggi_messaggi(percorso)
    agente = normalizza_agente(args.agente)
    _richiedi_thread_esistente(messaggi, args.thread_id)
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
    messaggio = costruisci_messaggio(
        mittente=agente,
        destinatari=destinatari,
        tipo="checkpoint",
        testo=testo,
        thread_id=args.thread_id,
        file_modificati=lista_csv(args.file_modificati),
    )
    aggiungi_messaggio(percorso, messaggio)
    print(json.dumps(messaggio, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _thread_ancora_da_riprendere(messaggi: list[dict[str, Any]]) -> list[str]:
    thread_ids = sorted({m["thread_id"] for m in messaggi})
    return [tid for tid in thread_ids if stato_thread(messaggi, tid) not in ("chiuso", "annullato", "inesistente")]


def comando_ripresa(args: argparse.Namespace) -> int:
    """Vista pensata per quando si riaccende dopo un'interruzione: cosa e' rimasto
    appeso, cosa e' scaduto, cosa era in carico a chi. Non decide nulla al posto
    dell'umano, solo mette in fila le domande giuste."""
    messaggi = leggi_messaggi(Path(args.bacheca))
    aperti = _thread_ancora_da_riprendere(messaggi)
    if not aperti:
        print("Nessun thread aperto o in carico: nulla da riprendere.")
        return 0

    adesso = datetime.now(timezone.utc)
    print("== Thread ancora aperti o in carico ==")
    print("| Thread | Stato | Lease | File dichiarati | Ultimo mittente |")
    print("|---|---|---|---|---|")
    for tid in aperti:
        stato = stato_thread(messaggi, tid)
        ultimo = _messaggi_del_thread(messaggi, tid)[-1]
        rilevante = _ultimo_rilevante(messaggi, tid)
        lease = "-"
        if stato == "preso_in_carico" and rilevante["ttl_minuti"] is not None:
            scadenza = _a_utc(rilevante["timestamp"]) + timedelta(minutes=rilevante["ttl_minuti"])
            lease = "SCADUTO" if scadenza < adesso else scadenza.isoformat()
        file_dichiarati = ", ".join(rilevante["file_modificati"]) or "(nessuno)"
        print(f"| {tid[:8]} | {stato} | {lease} | {file_dichiarati} | {ultimo['mittente']} |")

    occupati_attivi = file_occupati(messaggi, adesso=adesso)
    print("\n== File con lease ancora attivo ==")
    if occupati_attivi:
        for f, info in sorted(occupati_attivi.items()):
            print(f"- {f}: {info['agente']} (thread {info['thread_id'][:8]})")
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


def comando_thread(args: argparse.Namespace) -> int:
    messaggi = leggi_messaggi(Path(args.bacheca))
    cronologia = _messaggi_del_thread(messaggi, args.thread_id)
    if not cronologia:
        print(f"nessun messaggio per thread_id={args.thread_id!r}", file=sys.stderr)
        return 1
    for m in cronologia:
        print(f"[{m['timestamp']}] {m['mittente']} -> {', '.join(m['destinatari'])} ({m['tipo']}): {m['testo']}")
    print(f"\nStato globale: {stato_thread(messaggi, args.thread_id)}")
    print(f"Verdetto umano corrente: {verdetto_umano_corrente(messaggi, args.thread_id)}")
    return 0


def comando_riepilogo(args: argparse.Namespace) -> int:
    return comando_stato(args)


def comando_valida(args: argparse.Namespace) -> int:
    messaggi = leggi_messaggi(Path(args.bacheca))
    print(f"bacheca valida: {len(messaggi)} messaggi")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bacheca multi-agente dell'orchestratore LLM")
    parser.add_argument("--bacheca", default=str(PERCORSO_BACHECA_PREDEFINITO))
    sotto = parser.add_subparsers(dest="comando", required=True)

    aggiungi = sotto.add_parser("aggiungi", help="Aggiunge un messaggio generico")
    aggiungi.add_argument("--mittente", required=True, choices=AGENTI_VALIDI)
    aggiungi.add_argument("--destinatari", required=True, help="CSV di agenti")
    aggiungi.add_argument("--tipo", required=True, choices=TIPI_VALIDI)
    aggiungi.add_argument("--testo", required=True)
    aggiungi.add_argument("--thread-id", default="")
    aggiungi.add_argument("--file-modificati", default="")
    aggiungi.add_argument("--riferimenti", default="")
    aggiungi.add_argument("--correla-a", default="")
    aggiungi.add_argument("--ttl-minuti", type=int, default=None)
    aggiungi.add_argument("--verdetto-umano", choices=VERDETTI_VALIDI, default="non_revisionato")
    aggiungi.set_defaults(funzione=comando_aggiungi)

    chiedi = sotto.add_parser("chiedi", help="Convenienza umana: apre/continua un thread come mittente=umano")
    chiedi.add_argument("--a", required=True, help="CSV di agenti destinatari")
    chiedi.add_argument("--tipo", choices=["richiesta", "domanda"], default="richiesta")
    chiedi.add_argument("--testo", required=True)
    chiedi.add_argument("--thread-id", default="", help="Se omesso, apre un thread nuovo")
    chiedi.set_defaults(funzione=comando_chiedi)

    prossimo = sotto.add_parser("prossimo", help="Messaggi pendenti per un agente (vista per destinatario)")
    prossimo.add_argument("--agente", required=True, choices=AGENTI_VALIDI)
    prossimo.add_argument("--formato", choices=["json", "hook"], default="json")
    prossimo.add_argument(
        "--evento", default="SessionStart",
        help="Nome dell'evento hook reale che ha invocato il comando (SessionStart/UserPromptSubmit/BeforeAgent)",
    )
    prossimo.set_defaults(funzione=comando_prossimo)

    rispondi = sotto.add_parser("rispondi", help="Risponde a un messaggio correlato")
    rispondi.add_argument("--correla-a", required=True)
    rispondi.add_argument("--mittente", required=True, choices=AGENTI_VALIDI)
    rispondi.add_argument("--destinatari", default="", help="CSV; default: partecipanti del thread esclusi il mittente")
    rispondi.add_argument("--testo", required=True)
    rispondi.add_argument("--file-modificati", default="")
    rispondi.set_defaults(funzione=comando_rispondi)

    prendi = sotto.add_parser("prendi", help="Presa in carico di un thread (lease non vincolante)")
    prendi.add_argument("--thread-id", required=True)
    prendi.add_argument("--agente", required=True, choices=AGENTI_VALIDI)
    prendi.add_argument("--destinatari", default="")
    prendi.add_argument("--ttl-minuti", type=int, default=None)
    prendi.add_argument("--testo", default="")
    prendi.add_argument("--file-modificati", default="", help="CSV; se un file e' gia' in carico ad altri, avvisa e blocca salvo --forza")
    prendi.add_argument("--forza", action="store_true", help="Procede anche se i file sono gia' in carico ad altri")
    prendi.set_defaults(funzione=comando_prendi)

    occupati = sotto.add_parser("occupati", help="File attualmente in carico (claim attivi, non scaduti)")
    occupati.set_defaults(funzione=comando_occupati)

    checkpoint = sotto.add_parser("checkpoint", help="Annotazione di avanzamento a meta' lavoro (non chiude il thread)")
    checkpoint.add_argument("--thread-id", required=True)
    checkpoint.add_argument("--agente", required=True, choices=AGENTI_VALIDI)
    checkpoint.add_argument("--destinatari", default="")
    checkpoint.add_argument("--obiettivo", default="")
    checkpoint.add_argument("--stato-attuale", default="")
    checkpoint.add_argument("--file-modificati", default="")
    checkpoint.add_argument("--manca", default="")
    checkpoint.add_argument("--test", default="")
    checkpoint.add_argument("--rischi", default="")
    checkpoint.add_argument("--prossimo-passo", default="")
    checkpoint.set_defaults(funzione=comando_checkpoint)

    ripresa = sotto.add_parser("ripresa", help="Vista per riprendere dopo un'interruzione: thread appesi, lease scaduti, file in carico")
    ripresa.set_defaults(funzione=comando_ripresa)

    emergenza = sotto.add_parser("emergenza", help="Checkpoint minimo per uno spegnimento in emergenza (bacheca + git status + thread aperti)")
    emergenza.add_argument("--testo", default="")
    emergenza.set_defaults(funzione=comando_emergenza)

    sintetizza = sotto.add_parser("sintetizza", help="Chiama il modello locale per sintetizzare un thread e segnalare eventuali conflitti")
    sintetizza.add_argument("--thread-id", required=True)
    sintetizza.add_argument("--modello", default="", help="Override del modello locale (default: quello di adattatori/litellm.py)")
    sintetizza.set_defaults(funzione=comando_sintetizza)

    chiudi = sotto.add_parser("chiudi", help="Chiude un thread (senza verdetto)")
    chiudi.add_argument("--thread-id", required=True)
    chiudi.add_argument("--mittente", required=True, choices=AGENTI_VALIDI)
    chiudi.add_argument("--destinatari", default="")
    chiudi.add_argument("--testo", required=True)
    chiudi.set_defaults(funzione=comando_chiudi)

    approva = sotto.add_parser("approva", help="Chiude un thread con verdetto_umano=approvato (mittente sempre umano)")
    approva.add_argument("--thread-id", required=True)
    approva.add_argument("--destinatari", default="")
    approva.add_argument("--testo", required=True)
    approva.set_defaults(funzione=comando_approva)

    respingi = sotto.add_parser("respingi", help="Chiude un thread con verdetto_umano=respinto (mittente sempre umano)")
    respingi.add_argument("--thread-id", required=True)
    respingi.add_argument("--destinatari", default="")
    respingi.add_argument("--testo", required=True)
    respingi.set_defaults(funzione=comando_respingi)

    stato = sotto.add_parser("stato", help="Riepilogo di tutti i thread (stato globale + chi aspetta)")
    stato.set_defaults(funzione=comando_stato)

    thread = sotto.add_parser("thread", help="Cronologia completa di un thread")
    thread.add_argument("thread_id")
    thread.set_defaults(funzione=comando_thread)

    riepilogo = sotto.add_parser("riepilogo", help="Alias di 'stato' (coerenza col nome usato in registro.py)")
    riepilogo.set_defaults(funzione=comando_riepilogo)

    valida = sotto.add_parser("valida", help="Valida tutta la bacheca contro lo schema")
    valida.set_defaults(funzione=comando_valida)

    args = parser.parse_args(argv)
    try:
        return args.funzione(args)
    except Exception as errore:
        print(f"errore: {errore}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
