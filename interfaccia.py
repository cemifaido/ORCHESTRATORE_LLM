#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from collections import defaultdict
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Orchestratore LLM — Dashboard")

PERCORSO_PROGETTI = Path("dati_locali") / "progetti.json"
PERCORSO_HTML = Path("interfaccia.html")

# Assicura caricamento moduli locali del framework
sys.path.append(str(Path(".").resolve()))
import registro

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
    # 1. Crea directory locali per il registro e configurazioni
    (dest_path / "dati_locali" / "orchestrazione").mkdir(parents=True, exist_ok=True)
    (dest_path / "schema").mkdir(parents=True, exist_ok=True)
    (dest_path / "config").mkdir(parents=True, exist_ok=True)
    
    # 2. Copia gli schemi se esistono
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
            
    # 4. Copia i tre script centrali per esecuzione locale
    for script in ["registro.py", "sentinella.py", "genera_cruscotto.py"]:
        src_script = Path(script)
        dest_script = dest_path / script
        if src_script.exists():
            shutil.copy(src_script, dest_script)

    # 5. Aggiorna il file .gitignore del progetto target
    gitignore_path = dest_path / ".gitignore"
    regole_orchestratore = [
        "\n# File dell'Orchestratore LLM",
        "registro.py",
        "sentinella.py",
        "genera_cruscotto.py",
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

@app.get("/api/stato")
def get_stato():
    progetti = leggi_progetti()
    progetti_arricchiti = []
    tutti_eventi = []
    progetto_stats = {}
    agente_stats = defaultdict(lambda: {"esecuzioni": 0, "costo": 0.0, "latenza": 0, "rework": 0})
    
    for proj in progetti:
        p_id = proj["id"]
        p_nome = proj["nome"]
        p_path = Path(proj["percorso"])
        p_eventi_path = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
        
        # Legge comandi whitelistati per il progetto
        comandi_disponibili = []
        p_comandi_path = p_path / "config" / "comandi.json"
        if not p_comandi_path.exists():
            p_comandi_path = p_path / "config" / "comandi.esempio.json"
        if p_comandi_path.exists():
            try:
                dati_c = json.loads(p_comandi_path.read_text(encoding="utf-8"))
                comandi_disponibili = list(dati_c.get("comandi", {}).keys())
            except Exception:
                pass
                
        progetti_arricchiti.append({
            "id": p_id,
            "nome": p_nome,
            "percorso": str(p_path),
            "comandi": comandi_disponibili
        })
        
        eventi_progetto = []
        if p_eventi_path.exists():
            try:
                eventi_progetto = registro.leggi_eventi(p_eventi_path)
            except Exception:
                pass
                
        for ev in eventi_progetto:
            ev["_progetto_nome"] = p_nome
            ev["_progetto_id"] = p_id
            tutti_eventi.append(ev)
            
        costo_proj = sum(float(ev.get("costo_stimato_usd") or 0.0) for ev in eventi_progetto)
        latenza_proj = sum(int(ev.get("latenza_ms") or 0) for ev in eventi_progetto)
        rework_proj = sum(1 for ev in eventi_progetto if ev.get("rework") == "si" or ev.get("esito_gate") == "fallito" or ev.get("verdetto_umano") == "respinto")
        
        progetto_stats[p_id] = {
            "nome": p_nome,
            "percorso": str(p_path),
            "esecuzioni": len(eventi_progetto),
            "costo": costo_proj,
            "latenza": latenza_proj,
            "rework": rework_proj
        }
        
        for ev in eventi_progetto:
            agente = ev["agente"]
            agente_stats[agente]["esecuzioni"] += 1
            agente_stats[agente]["costo"] += float(ev.get("costo_stimato_usd") or 0.0)
            agente_stats[agente]["latenza"] += int(ev.get("latenza_ms") or 0)
            if ev.get("rework") == "si" or ev.get("esito_gate") == "fallito" or ev.get("verdetto_umano") == "respinto":
                agente_stats[agente]["rework"] += 1

    # Ordina eventi per data (ultimi prima)
    tutti_eventi.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

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

@app.post("/api/sentinella")
def esegui_sentinella(input_data: SentinellaInput):
    progetti = leggi_progetti()
    target = next((p for p in progetti if p["id"] == input_data.progetto_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
        
    p_path = Path(target["percorso"])
    sentinella_script = p_path / "sentinella.py"
    if not sentinella_script.exists():
        raise HTTPException(status_code=400, detail="sentinella.py non trovato nel progetto di destinazione")
        
    try:
        completato = subprocess.run(
            [sys.executable, str(sentinella_script), input_data.comando],
            cwd=p_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            shell=False
        )
        # Tenta di decodificare l'output JSON emesso da sentinella.py
        output_std = completato.stdout or ""
        dati_output = {}
        try:
            # sentinella.py stampa l'evento JSON alla fine
            dati_output = json.loads(output_std.strip().splitlines()[-1])
        except Exception:
            dati_output = {"output": output_std}
            
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
