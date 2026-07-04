#!/usr/bin/env python3
import sys
import json
import shutil
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Orchestratore LLM — Dashboard")

PERCORSO_PROGETTI = Path("dati_locali") / "progetti.json"
PERCORSO_HTML = Path("interfaccia.html")
SCRIPT_SENTINELLA_CENTRALE = Path(__file__).resolve().parent / "sentinella.py"

# Assicura caricamento moduli locali del framework
sys.path.append(str(Path(".").resolve()))
import registro  # noqa: E402

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
                    "percorso": str(Path(".").resolve())
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
        src_schema = Path("schema") / schema_file
        if src_schema.exists():
            shutil.copy(src_schema, dest_path / "schema" / schema_file)

    # 3. Copia configurazioni di esempio se non esistono già
    for cfg in ["comandi.esempio.json", "agenti.esempio.json"]:
        src_cfg = Path("config") / cfg
        dest_cfg = dest_path / "config" / cfg
        if src_cfg.exists() and not dest_cfg.exists():
            shutil.copy(src_cfg, dest_cfg)

    # 4. Aggiorna il file .gitignore del progetto target
    gitignore_path = dest_path / ".gitignore"
    regole_orchestratore = [
        "\n# File dell'Orchestratore LLM (dati/config locali, il codice resta centrale)",
        "dati_locali/orchestrazione/",
        "schema/evento.v1.json",
        "schema/compito.v1.json",
        "config/comandi.json",
        "config/comandi.esempio.json",
        "config/agenti.json",
        "config/agenti.esempio.json"
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
def get_stato():
    progetti = leggi_progetti()
    progetti_arricchiti = [arricchisci_progetto(proj) for proj in progetti]

    tutti_eventi, progetto_stats = registro.carica_eventi_multi_progetto(progetti)
    tutti_eventi.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    agente_stats = registro.metriche(tutti_eventi)

    return {
        "progetti": progetti_arricchiti,
        "globali": {
            "progetti_totali": len(progetti),
            "eventi_totali": len(tutti_eventi),
            "costo_totale": sum(float(ev.get("costo_stimato_usd") or 0.0) for ev in tutti_eventi),
            "latenza_totale": sum(int(ev.get("latenza_ms") or 0) for ev in tutti_eventi)
        },
        "progetto_stats": progetto_stats,
        "agente_stats": agente_stats,
        "eventi": tutti_eventi[:50]
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

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8095)
