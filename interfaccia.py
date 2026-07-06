#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess
import threading
import time
from math import ceil
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Orchestratore LLM — Dashboard")

# Tutti i percorsi dell'orchestratore sono relativi a questo file, non alla cwd del
# processo: interfaccia.py deve funzionare anche se lanciato da una cwd diversa
# (es. un servizio, un task scheduler, un IDE con working directory non impostata).
RADICE = Path(__file__).resolve().parent

PERCORSO_PROGETTI = RADICE / "dati_locali" / "progetti.json"
PERCORSO_HTML = RADICE / "interfaccia.html"
SCRIPT_SENTINELLA_CENTRALE = RADICE / "sentinella.py"
SCRIPT_INTERFACCIA = RADICE / "interfaccia.py"
HOST_DASHBOARD = os.environ.get("ORCHESTRATORE_HOST", "127.0.0.1")
PORTA_DASHBOARD = int(os.environ.get("ORCHESTRATORE_PORTA", "8095"))

# Assicura caricamento moduli locali del framework
sys.path.append(str(RADICE))
import registro  # noqa: E402
import commit_replay  # noqa: E402
import bacheca  # noqa: E402

AGENTI_BACHECA_DASHBOARD = ("claude", "codex", "gemini")


class ProgettoInput(BaseModel):
    nome: str
    percorso: str

class SentinellaInput(BaseModel):
    progetto_id: str
    comando: str

def leggi_progetti() -> list[dict]:
    if not PERCORSO_PROGETTI.exists():
        PERCORSO_PROGETTI.parent.mkdir(parents=True, exist_ok=True)
        default_config = {
            "progetti": [
                {
                    "id": "orchestratore",
                    "nome": "Orchestratore Centrale",
                    "percorso": str(RADICE)
                }
            ]
        }
        PERCORSO_PROGETTI.write_text(json.dumps(default_config, indent=2, ensure_ascii=False), encoding="utf-8")
        return default_config["progetti"]
    try:
        return json.loads(PERCORSO_PROGETTI.read_text(encoding="utf-8")).get("progetti", [])
    except Exception:
        return []

def salva_progetti(progetti: list[dict]):
    PERCORSO_PROGETTI.parent.mkdir(parents=True, exist_ok=True)
    PERCORSO_PROGETTI.write_text(json.dumps({"progetti": progetti}, indent=2, ensure_ascii=False), encoding="utf-8")


# Sincronizzazione multi-agente (vedi docs/REGOLE_GENERALI_PROGRAMMAZIONE_...MD,
# sezione "Sincronizzazione multi-agente (tassativo)"): ogni progetto integrato riceve
# le istruzioni per Claude Code, Gemini e Codex, cosi' anche loro leggono/registrano
# sul registro condiviso del progetto invece di lavorare alla cieca.
ISTRUZIONI_AGENTI = [
    ("CLAUDE.md", "Claude Code", "claude"),
    ("GEMINI.md", "Gemini (antigravity-ide)", "gemini"),
    ("AGENTS.md", "Codex", "codex"),
]

_LETTURA_EVENTI_RECENTI = """python -c @'
import json
with open("dati_locali/orchestrazione/eventi.jsonl", encoding="utf-8") as f:
    for r in f.readlines()[-10:]:
        e = json.loads(r)
        print(e["timestamp"], "[" + e["agente"] + "]", e.get("note","")[:200])
'@"""


def _contenuto_istruzioni_agente(nome_file: str, nome_strumento: str, agente: str) -> str:
    altri_file = ", ".join(f"`{nf}`" for nf, _, _ in ISTRUZIONI_AGENTI if nf != nome_file)
    return f"""# Istruzioni per {nome_strumento} in questo repository

**Ultimo aggiornamento di questo file**: mai (aggiornalo a fine compito, vedi sotto)

Questo progetto è monitorato dall'Orchestratore LLM (`{RADICE}`). Se altri assistenti
AI (Claude Code, Gemini/antigravity-ide, Codex) lavorano su questo stesso progetto in
sessioni separate, sincronizzatevi in modo asincrono tramite il registro condiviso di
**questo** progetto (`dati_locali/orchestrazione/eventi.jsonl`) — come un team che si
aggiorna tramite changelog condiviso invece che a voce. File equivalenti per gli altri
strumenti: `CLAUDE.md`, `GEMINI.md`, `AGENTS.md` (locali, non committati in questo
repository).

**Pre-check economico, prima di leggere il registro**: confronta la riga "Ultimo
aggiornamento" in cima a questo file con quella in cima a {altri_file}. Se una delle
altre due è più recente della tua, un'altra sessione ha lavorato dopo di te — vai a
leggere il registro (sotto) per sapere cosa. Se la tua è già la più recente, puoi
saltare la lettura del registro: nessuno ha lavorato da allora. Il timestamp da solo
dice *che* qualcosa è successo, non *cosa*: per il contenuto serve sempre il registro.

## All'inizio di un compito: leggi cosa è già successo

Se il pre-check sopra dice che serve:

```powershell
{_LETTURA_EVENTI_RECENTI}
```

Se il file non esiste ancora, non è stato registrato nulla: procedi normalmente. Se un
evento recente descrive una decisione o un bug corretto rilevante per il tuo compito,
non ripartire da zero: costruisci sopra quello.

## Dopo un compito reale: registralo

```powershell
python "{RADICE}\\registro.py" aggiungi `
  --id-compito "<slug-breve-del-compito>" `
  --agente {agente} `
  --tipo-compito "<servizi|interfaccia|documentazione|revisione|sicurezza|monitoraggio|errore_test|orchestrazione>" `
  --stato "<passato|fallito>" `
  --esito-gate "<superato|fallito|non_eseguito>" `
  --costo-stimato-usd 0.0 `
  --latenza-ms 0 `
  --regole-incluse "sessione_interattiva" `
  --note "Richiesta: <cosa ha chiesto l'utente, in breve> | Fatto: <cosa hai fatto e verificato>"
```

Si usa lo script centrale dell'orchestratore (mai una copia locale), così resta sempre
aggiornato; il registro di *questo* progetto viene comunque usato di default perché il
percorso è relativo alla cartella da cui lanci il comando (dove ti trovi tu), non a
dove si trova lo script.

Regole pratiche:
- `esito_gate=superato` solo se hai davvero rieseguito test/lint/quality gate e sono
  passati — non dichiararlo senza averlo verificato.
- `note` deve avere **sia** la richiesta originale **sia** l'esito: un registro che
  mostra solo "cosa ha fatto l'agente" senza "cosa è stato chiesto" perde metà della
  storia.
- Non registrare eventi per semplici domande/spiegazioni senza modifiche di codice.

## Registrare anche l'approvazione finale dell'umano

Il registro non deve raccontare solo "cosa ha fatto l'agente": anche il via libera
dell'umano è un fatto operativo, e lo schema ha già un campo apposta (`verdetto_umano`)
che altrimenti resta sempre `non_revisionato` per sempre. **Quando l'utente dà
un'approvazione esplicita e finale** (tipicamente prima di un `git commit`, ma vale per
qualunque decisione irreversibile), registra un evento separato:

```powershell
python "{RADICE}\\registro.py" aggiungi `
  --id-compito "<stesso-id-compito-o-riferimento-al-lavoro-approvato>" `
  --agente umano `
  --tipo-compito "orchestrazione" `
  --stato "accettato" `
  --esito-gate "non_eseguito" `
  --verdetto-umano "approvato" `
  --costo-stimato-usd 0.0 `
  --latenza-ms 0 `
  --note "<cosa ha approvato l'utente, es. 'approvato il commit <hash-breve>'>"
```

Non farlo per ogni singolo messaggio (sarebbe rumore) — solo per un'approvazione
esplicita e concreta a un'azione con effetto reale (commit, push, cancellazione,
decisione architetturale importante).

**Subito dopo aver registrato l'evento**, aggiorna la riga "Ultimo aggiornamento di
questo file" in cima a **questo** file (mai gli altri, quelli li aggiornano loro) con
il timestamp corrente:

```powershell
python -c "import registro; print(registro.adesso_utc())"
```

## Delegare la guardia (non la risposta) al modello locale

Principio: "a te delego la risposta, non la guardia". Non leggere personalmente ogni
riga di un output ripetitivo se puoi evitarlo — ma il modo più economico non è sempre
il modello locale:

- **Output con formato fisso e noto** (es. il riepilogo di `unittest`: "OK" oppure
  "FAILED"/"ERROR"): un pattern-match diretto è deterministico, istantaneo, a costo
  zero — anche più economico di una chiamata al modello locale, che comunque richiede
  latenza per generare una risposta. Usalo direttamente, non serve altro.
- **Output non strutturato o imprevedibile** (un errore di lint mai visto, uno stack
  trace da interpretare, warning ambigui) dove un pattern fisso non basta a fidarsi:
  gira l'output a `triage_locale.py` (nella cartella dell'orchestratore), che usa il
  modello locale (llama-server, gratis, sempre acceso) per classificarlo.

```powershell
python -m unittest discover -s tests | python "{RADICE}\\triage_locale.py"
```

Quando il controllo passa dalla sentinella centrale, preferisci il flag integrato:

```powershell
python "{RADICE}\\sentinella.py" test_servizi --triage-locale
```

La sentinella registra sempre l'evento del gate; con `--triage-locale` registra anche
un secondo evento `agente=locale` sullo stesso `id_compito`. Per output ovvi usa pattern
deterministici, per output ambigui chiama il modello locale.

Ritorna JSON `{{"esito": "routine"|"escalation", "motivo": "..."}}` ed esce con codice
0 (routine) o 1 (escalation). Se `routine`, fidati e prosegui senza rileggere tutto
l'output a mano. Se `escalation` (o se il modello locale non è raggiungibile — in tal
caso ritorna comunque `escalation` per sicurezza), leggi l'output per davvero e
ragiona tu: il triage locale classifica, non risolve.

Non usarlo per decisioni architetturali o revisioni di codice: solo per il primo
filtro su output ripetitivi (test, lint, build) dove "ha funzionato sì/no" è la
domanda, non "perché"/"come".
"""


def integra_progetto(dest_path: Path):
    """Prepara un progetto target: solo dati/config locali, nessun codice orchestratore.
    registro.py/sentinella.py restano un'unica copia centrale (questa cartella); la
    dashboard li invoca sempre da qui con --config/--registro e cwd sul progetto target,
    cosi' un aggiornamento dell'orchestratore vale per tutti i progetti senza dover
    re-integrare nulla. Vedi docs/ORCHESTRAZIONE_LAVORATORI.md."""
    # 1. Crea directory locali per dati runtime e configurazioni
    (dest_path / "dati_locali" / "orchestrazione").mkdir(parents=True, exist_ok=True)
    (dest_path / "schema").mkdir(parents=True, exist_ok=True)
    (dest_path / "config").mkdir(parents=True, exist_ok=True)

    # 2. Copia gli schemi come riferimento locale (documentazione): la validazione vera
    #    avviene sempre nell'orchestratore centrale con il proprio schema.
    for schema_file in ["evento.v1.json", "compito.v1.json"]:
        src_schema = RADICE / "schema" / schema_file
        if src_schema.exists():
            shutil.copy(src_schema, dest_path / "schema" / schema_file)

    # 3. Copia configurazioni di esempio se non esistono già
    for cfg in ["comandi.esempio.json", "agenti.esempio.json"]:
        src_cfg = RADICE / "config" / cfg
        dest_cfg = dest_path / "config" / cfg
        if src_cfg.exists() and not dest_cfg.exists():
            shutil.copy(src_cfg, dest_cfg)

    # 4. Scrive le istruzioni di sincronizzazione multi-agente se non esistono già
    #    (non sovrascrive personalizzazioni fatte a mano nel progetto target).
    for nome_file, nome_strumento, agente in ISTRUZIONI_AGENTI:
        dest_file = dest_path / nome_file
        if not dest_file.exists():
            dest_file.write_text(_contenuto_istruzioni_agente(nome_file, nome_strumento, agente), encoding="utf-8")

    # 5. Aggiorna il file .gitignore del progetto target
    gitignore_path = dest_path / ".gitignore"
    regole_orchestratore = [
        "\n# File dell'Orchestratore LLM (dati/config locali, il codice resta centrale)",
        "dati_locali/orchestrazione/",
        "schema/evento.v1.json",
        "schema/compito.v1.json",
        "config/comandi.json",
        "config/comandi.esempio.json",
        "config/agenti.json",
        "config/agenti.esempio.json",
        "\n# Istruzioni per assistenti AI (sincronizzazione multi-agente via registro):",
        "# locali per operatore/macchina, non condivise nel repository.",
        "CLAUDE.md",
        "GEMINI.md",
        "AGENTS.md"
    ]

    contenuto_attuale = ""
    if gitignore_path.exists():
        try:
            contenuto_attuale = gitignore_path.read_text(encoding="utf-8")
        except Exception:
            pass

    nuove_regole = []
    for r in regole_orchestratore:
        if r.strip() and r.strip() not in contenuto_attuale:
            nuove_regole.append(r)

    if nuove_regole:
        try:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                if contenuto_attuale and not contenuto_attuale.endswith("\n"):
                    f.write("\n")
                f.write("\n".join(nuove_regole) + "\n")
        except Exception:
            pass

@app.get("/", response_class=HTMLResponse)
def index():
    if not PERCORSO_HTML.exists():
        raise HTTPException(status_code=404, detail="File interfaccia.html non trovato")
    return FileResponse(PERCORSO_HTML)

def percorso_comandi_progetto(p_path: Path) -> Path:
    p_comandi_path = p_path / "config" / "comandi.json"
    if p_comandi_path.exists():
        return p_comandi_path
    return p_path / "config" / "comandi.esempio.json"


def comandi_disponibili_progetto(p_path: Path) -> list[dict[str, str]]:
    p_comandi_path = percorso_comandi_progetto(p_path)
    if not p_comandi_path.exists():
        return []
    try:
        dati_c = json.loads(p_comandi_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [
        {"nome": nome, "descrizione": cfg.get("descrizione") or nome}
        for nome, cfg in dati_c.get("comandi", {}).items()
    ]


def arricchisci_progetto(proj: dict) -> dict:
    p_path = Path(proj["percorso"])
    return {
        "id": proj["id"],
        "nome": proj["nome"],
        "percorso": str(p_path),
        "comandi": comandi_disponibili_progetto(p_path),
    }


@app.get("/api/stato")
def get_stato(pagina: int = 1, per_pagina: int = 50):
    progetti = leggi_progetti()
    progetti_arricchiti = [arricchisci_progetto(proj) for proj in progetti]

    tutti_eventi, progetto_stats = registro.carica_eventi_multi_progetto(progetti)
    tutti_eventi.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    agente_stats = registro.metriche(tutti_eventi)
    livello_stats = registro.metriche_per_livello(tutti_eventi)

    # Paginazione: solo la tabella timeline viene affettata. Gli aggregati sopra
    # (agente_stats, livello_stats, globali) restano calcolati su TUTTI gli eventi,
    # non solo sulla pagina corrente.
    per_pagina = max(1, per_pagina)
    pagine_totali = max(1, ceil(len(tutti_eventi) / per_pagina))
    pagina = min(max(1, pagina), pagine_totali)
    inizio = (pagina - 1) * per_pagina
    eventi_pagina = tutti_eventi[inizio:inizio + per_pagina]

    return {
        "progetti": progetti_arricchiti,
        "globali": {
            "progetti_totali": len(progetti),
            "eventi_totali": len(tutti_eventi),
            "latenza_totale": sum(int(ev.get("latenza_ms") or 0) for ev in tutti_eventi)
        },
        "progetto_stats": progetto_stats,
        "agente_stats": agente_stats,
        "livello_stats": livello_stats,
        "eventi": eventi_pagina,
        "paginazione": {
            "pagina": pagina,
            "per_pagina": per_pagina,
            "pagine_totali": pagine_totali,
            "eventi_totali": len(tutti_eventi),
        },
    }


@app.post("/api/progetti")
def aggiungi_progetto(proj: ProgettoInput):
    p_path = Path(proj.percorso).resolve()
    if not p_path.exists() or not p_path.is_dir():
        raise HTTPException(status_code=400, detail="Il percorso indicato non esiste o non è una cartella")

    progetti = leggi_progetti()
    p_id = proj.nome.lower().replace(" ", "_").replace("-", "_")
    p_id = "".join([c for c in p_id if c.isalnum() or c == "_"])

    # Previene duplicati
    if any(p["id"] == p_id or Path(p["percorso"]).resolve() == p_path for p in progetti):
        raise HTTPException(status_code=400, detail="Progetto con questo nome o percorso già registrato")

    # Integra le cartelle e copia i file di configurazione/schema nel target
    try:
        integra_progetto(p_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integrazione automatica fallita: {e}")

    nuovo = {
        "id": p_id,
        "nome": proj.nome,
        "percorso": str(p_path)
    }
    progetti.append(nuovo)
    salva_progetti(progetti)
    return {"status": "ok", "progetto": nuovo}

def interpreta_output_sentinella(output_std: str, output_err: str = "") -> dict:
    """sentinella.py stampa un unico blob JSON (indentato, multi-riga) su stdout e i
    messaggi di avanzamento su stderr. Va decodificato lo stdout per intero: prendere
    solo l'ultima riga (euristica precedente) restituisce "}" con JSON indentato."""
    try:
        return json.loads(output_std.strip())
    except Exception:
        return {"output": output_std, "stderr": output_err}


@app.post("/api/sentinella")
def esegui_sentinella(input_data: SentinellaInput):
    """Lancia sempre la sentinella centrale (questa cartella), mai una copia nel
    progetto target: --config/--registro puntano ai file del target e cwd=p_path fa
    si' che "cartella": "." nei comandi risolva nel progetto giusto. Cosi' un
    aggiornamento di sentinella.py/registro.py vale per tutti i progetti integrati."""
    progetti = leggi_progetti()
    target = next((p for p in progetti if p["id"] == input_data.progetto_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    p_path = Path(target["percorso"])
    percorso_comandi = percorso_comandi_progetto(p_path)
    if not percorso_comandi.exists():
        raise HTTPException(
            status_code=400,
            detail="Nessuna configurazione comandi trovata nel progetto (config/comandi.json o comandi.esempio.json)",
        )
    percorso_registro = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"

    try:
        completato = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_SENTINELLA_CENTRALE),
                input_data.comando,
                "--config", str(percorso_comandi),
                "--registro", str(percorso_registro),
                "--triage-locale",
            ],
            cwd=p_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            shell=False
        )
        dati_output = interpreta_output_sentinella(completato.stdout or "", completato.stderr or "")

        return {
            "status": "success" if completato.returncode == 0 else "failed",
            "returncode": completato.returncode,
            "dati": dati_output
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Esecuzione del comando andata in timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'esecuzione del comando: {e}")




def _progetto_o_404(progetto_id: str) -> dict:
    progetti = leggi_progetti()
    progetto = next((p for p in progetti if p["id"] == progetto_id), None)
    if not progetto:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return progetto


@app.get("/api/commit/lista")
def lista_commit_progetto(progetto_id: str = "orchestratore", limite: int = 20):
    """Ultimi commit del progetto, per popolare il selettore di replay nel pannello
    Live Agent Handoff. Dati reali (git log), non una lista finta."""
    progetto = _progetto_o_404(progetto_id)
    try:
        commit = commit_replay.lista_commit(Path(progetto["percorso"]), limite=limite)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"progetto_id": progetto_id, "commit": commit}


@app.get("/api/commit/eventi")
def eventi_commit_progetto(progetto_id: str, hash: str):
    """Eventi del registro nella finestra temporale di un commit reale, con una stima
    di risparmio calcolata dai token realmente misurati nei controlli fatti dal
    modello locale — non uno scenario finto, replay di cosa e' successo davvero."""
    progetto = _progetto_o_404(progetto_id)
    p_path = Path(progetto["percorso"])
    try:
        inizio, fine = commit_replay.finestra_temporale_commit(p_path, hash)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    percorso_registro = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
    eventi = commit_replay.eventi_nella_finestra(percorso_registro, inizio, fine)
    stima = commit_replay.stima_risparmio(eventi)

    return {
        "progetto_id": progetto_id,
        "hash": hash,
        "eventi": eventi,
        "stima_risparmio": stima,
    }


@app.get("/api/bacheca")
def bacheca_progetto(progetto_id: str = "orchestratore"):
    """Stato della bacheca multi-agente di un progetto: un riepilogo per thread
    (stato, chi aspetta, verdetto umano, ultimo messaggio) piu' i file attualmente
    in carico. Solo visualizzazione (docs/RFC_BACHECA_MULTIAGENTE.md §9.5): nessuna
    azione da qui, quelle restano CLI (bacheca.py chiedi/approva/prendi/...)."""
    progetto = _progetto_o_404(progetto_id)
    messaggi, errore = bacheca.leggi_messaggi_progetto(Path(progetto["percorso"]))
    if errore:
        return {
            "progetto_id": progetto_id,
            "errore": errore,
            "thread": [],
            "occupati": {},
            "pending_per_agente": {agente: 0 for agente in AGENTI_BACHECA_DASHBOARD},
        }

    thread_ids = sorted({m["thread_id"] for m in messaggi})
    thread_riepilogo = []
    pending_per_agente = {agente: 0 for agente in AGENTI_BACHECA_DASHBOARD}
    for tid in thread_ids:
        ultimo = bacheca._messaggi_del_thread(messaggi, tid)[-1]
        aspetta = bacheca.destinatari_pendenti(messaggi, tid)
        for agente in AGENTI_BACHECA_DASHBOARD:
            if agente in aspetta:
                pending_per_agente[agente] += 1
        thread_riepilogo.append({
            "thread_id": tid,
            "stato": bacheca.stato_thread(messaggi, tid),
            "ultimo_mittente": ultimo["mittente"],
            "ultimo_tipo": ultimo["tipo"],
            "ultimo_testo": ultimo["testo"][:200],
            "aspetta": aspetta,
            "verdetto_umano": bacheca.verdetto_umano_corrente(messaggi, tid),
            "file_modificati": ultimo["file_modificati"],
        })

    occupati = {
        f: {
            "agente": info["agente"],
            "thread_id": info["thread_id"],
            "scadenza": info["scadenza"].isoformat() if info["scadenza"] else None,
        }
        for f, info in bacheca.file_occupati(messaggi).items()
    }
    return {
        "progetto_id": progetto_id,
        "thread": thread_riepilogo,
        "occupati": occupati,
        "pending_per_agente": pending_per_agente,
    }


@app.get("/api/bacheca/feed")
def bacheca_feed_progetto(progetto_id: str = "orchestratore", limite: int = 50):
    """Ultimi messaggi in ordine cronologico (tutti i thread mescolati, non
    raggruppati) per il feed live del pannello Bacheca: mostra l'attivita' man mano
    che arriva, senza dover scegliere un thread specifico ne' cliccare nulla."""
    limite = max(1, min(limite, 200))
    progetto = _progetto_o_404(progetto_id)
    messaggi, errore = bacheca.leggi_messaggi_progetto(Path(progetto["percorso"]))
    if errore:
        return {"progetto_id": progetto_id, "errore": errore, "messaggi": []}
    messaggi_ordinati = sorted(messaggi, key=lambda m: m["timestamp"])
    return {"progetto_id": progetto_id, "messaggi": messaggi_ordinati[-limite:]}


@app.get("/api/bacheca/thread")
def bacheca_thread_progetto(progetto_id: str, thread_id: str):
    """Cronologia completa di un thread, per il drill-down nel pannello Bacheca."""
    progetto = _progetto_o_404(progetto_id)
    messaggi, errore = bacheca.leggi_messaggi_progetto(Path(progetto["percorso"]))
    if errore:
        raise HTTPException(status_code=500, detail=errore)
    cronologia = bacheca._messaggi_del_thread(messaggi, thread_id)
    if not cronologia:
        raise HTTPException(status_code=404, detail="Thread non trovato")
    return {"progetto_id": progetto_id, "thread_id": thread_id, "messaggi": cronologia}


def _avvia_processo_sostituto() -> None:
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, str(SCRIPT_INTERFACCIA)], cwd=str(RADICE), env=os.environ.copy(), **kwargs)


def _riavvia_dopo_risposta() -> None:
    # Aspetta che la risposta HTTP sia partita prima di terminare questo processo:
    # uvicorn non ricarica mai il codice modificato, quindi l'unico modo per applicare
    # le modifiche fatte su disco e' rimpiazzare il processo con uno nuovo.
    time.sleep(0.5)
    _avvia_processo_sostituto()
    os._exit(0)


@app.post("/api/sistema/riavvia")
def riavvia_sistema():
    """Avvia un nuovo processo (che ricarica il codice corrente da disco) e pianifica
    la terminazione di questo. Il nuovo processo attende la porta libera all'avvio
    (vedi __main__), quindi non serve sincronizzare a mano lo spegnimento del vecchio."""
    threading.Thread(target=_riavvia_dopo_risposta, daemon=True).start()
    return {"status": "riavvio_in_corso"}


if __name__ == "__main__":
    tentativi_rimasti = 20
    while True:
        try:
            uvicorn.run(app, host=HOST_DASHBOARD, port=PORTA_DASHBOARD)
            break
        except SystemExit:
            tentativi_rimasti -= 1
            if tentativi_rimasti <= 0:
                raise
            time.sleep(0.5)
