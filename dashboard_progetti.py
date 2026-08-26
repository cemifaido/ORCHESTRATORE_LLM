#!/usr/bin/env python3
"""Gestione e repository dei progetti monitorati dall'Orchestratore LLM.

Modulo estratto da interfaccia.py nel Lotto D (backlog architetturale D2).
Isola l'I/O su progetti.json, l'integrazione di directory target e la generazione
delle istruzioni di sincronizzazione multi-agente.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from fastapi import HTTPException

import dashboard_config
from osservabilita import log_evento

RADICE = dashboard_config.RADICE
PERCORSO_PROGETTI = dashboard_config.PERCORSO_PROGETTI

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


def integra_progetto(dest_path: Path) -> None:
    """Prepara un progetto target: solo dati/config locali, nessun codice orchestratore.
    registro.py/sentinella.py restano un'unica copia centrale (questa cartella); la
    dashboard li invoca sempre da qui con --config/--registro e cwd sul progetto target,
    cosi' un aggiornamento dell'orchestratore vale per tutti i progetti senza dover
    re-integrare nulla. Vedi docs/ORCHESTRAZIONE_LAVORATORI.md."""
    dest_path = dest_path.resolve()
    if dest_path == RADICE:
        return
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

    # 3. Copia la configurazione di esempio se non esiste già
    src_cfg = RADICE / "config" / "comandi.esempio.json"
    dest_cfg = dest_path / "config" / "comandi.esempio.json"
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


def leggi_progetti(percorso_progetti: Path | None = None) -> list[dict]:
    """Legge l'elenco dei progetti registrati da progetti.json.

    Se il file non esiste, crea la configurazione di default con l'orchestratore centrale.
    Se il file e' corrotto o ha forma inattesa, logga su stderr e ritorna [].
    """
    if percorso_progetti is None:
        percorso_progetti = PERCORSO_PROGETTI
    if not percorso_progetti.exists():
        percorso_progetti.parent.mkdir(parents=True, exist_ok=True)
        default_config = {
            "progetti": [
                {
                    "id": "orchestratore",
                    "nome": "Orchestratore Centrale",
                    "percorso": str(RADICE)
                }
            ]
        }
        percorso_progetti.write_text(json.dumps(default_config, indent=2, ensure_ascii=False), encoding="utf-8")
        return default_config["progetti"]
    try:
        raw = json.loads(percorso_progetti.read_text(encoding="utf-8")).get("progetti", [])
    except (OSError, json.JSONDecodeError) as errore:
        msg = f"[progetti.json] impossibile leggere {percorso_progetti}: {errore}"
        print(msg, file=sys.stderr)
        log_evento("dashboard_progetti", "error", msg, percorso=str(percorso_progetti))
        return []
    if isinstance(raw, dict):
        return [
            {"id": k, **v} if isinstance(v, dict) else {"id": k, "nome": k, "percorso": str(v)}
            for k, v in raw.items()
        ]
    if isinstance(raw, list):
        return raw
    msg_inatteso = f"[progetti.json] campo 'progetti' di tipo inatteso ({type(raw).__name__}) in {percorso_progetti}, ignorato"
    print(msg_inatteso, file=sys.stderr)
    log_evento("dashboard_progetti", "warning", msg_inatteso, percorso=str(percorso_progetti))
    return []


def salva_progetti(progetti: list[dict], percorso_progetti: Path | None = None) -> None:
    """Salva l'elenco dei progetti registrati in formato JSON indentato."""
    if percorso_progetti is None:
        percorso_progetti = PERCORSO_PROGETTI
    percorso_progetti.parent.mkdir(parents=True, exist_ok=True)
    percorso_progetti.write_text(json.dumps({"progetti": progetti}, indent=2, ensure_ascii=False), encoding="utf-8")


def percorso_comandi_progetto(p_path: Path) -> Path:
    """Restituisce il percorso del file comandi.json o comandi.esempio.json per il progetto."""
    p_comandi_path = p_path / "config" / "comandi.json"
    if p_comandi_path.exists():
        return p_comandi_path
    return p_path / "config" / "comandi.esempio.json"


def comandi_disponibili_progetto(p_path: Path) -> list[dict[str, str]]:
    """Restituisce la lista dei comandi configurati per il progetto."""
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
    """Arricchisce un dizionario progetto con la lista dei comandi disponibili."""
    p_path = Path(proj["percorso"])
    return {
        "id": proj["id"],
        "nome": proj["nome"],
        "percorso": str(p_path),
        "comandi": comandi_disponibili_progetto(p_path),
    }


def progetto_o_404(progetto_id: str, progetti: list[dict] | None = None) -> dict:
    """Cerca un progetto per id o solleva HTTPException(404)."""
    if progetti is None:
        progetti = leggi_progetti()
    progetto = next((p for p in progetti if p["id"] == progetto_id), None)
    if not progetto:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return progetto
