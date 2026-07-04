#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import registro

PERCORSO_PROGETTI_PREDEFINITO = Path("dati_locali") / "progetti.json"
PERCORSO_CRUSCOTTO_PREDEFINITO = Path("dati_locali") / "orchestrazione" / "cruscotto.md"

def carica_progetti(percorso_progetti: Path) -> list[dict]:
    if not percorso_progetti.exists():
        percorso_progetti.parent.mkdir(parents=True, exist_ok=True)
        default_config = {
            "progetti": [
                {
                    "id": "orchestratore",
                    "nome": "Orchestratore Centrale",
                    "percorso": str(Path(".").resolve())
                }
            ]
        }
        percorso_progetti.write_text(json.dumps(default_config, indent=2, ensure_ascii=False), encoding="utf-8")
        return default_config["progetti"]

    try:
        with percorso_progetti.open("r", encoding="utf-8") as file:
            return json.load(file).get("progetti", [])
    except Exception as e:
        print(f"Errore nel caricamento dei progetti: {e}")
        return []

def denaro(valore: float) -> str:
    return f"${valore:.4f}"

def renderizza(progetti: list[dict]) -> str:
    righe = ["# Cruscotto orchestratore multi-progetto", "", ""]

    tutti_eventi, progetto_stats = registro.carica_eventi_multi_progetto(progetti)
    agente_stats = registro.metriche(tutti_eventi)
    # Ordina gli eventi combinati per timestamp decrescente (ultimi prima)
    tutti_eventi.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    costo_totale = sum(float(ev.get("costo_stimato_usd") or 0.0) for ev in tutti_eventi)
    latenza_totale = sum(int(ev.get("latenza_ms") or 0) for ev in tutti_eventi)

    righe.extend([
        "## Sintesi globale",
        "",
        f"- Progetti monitorati: **{len(progetti)}**",
        f"- Eventi totali registrati: **{len(tutti_eventi)}**",
        f"- Costo stimato totale: **{denaro(costo_totale)}**",
        f"- Latenza cumulata: **{latenza_totale} ms**",
        "",
        "## Per Progetto",
        "",
        "| Progetto | Esecuzioni | Costo | Latenza ms | Rework |",
        "|---|---:|---:|---:|---:|",
    ])
    for stat in sorted(progetto_stats.values(), key=lambda s: s["nome"]):
        righe.append(f"| {stat['nome']} | {stat['esecuzioni']} | {denaro(stat['costo'])} | {stat['latenza']} | {stat['rework']} |")

    progetti_con_errore = [stat for stat in progetto_stats.values() if stat.get("errore")]
    if progetti_con_errore:
        righe.extend(["", "## ⚠ Registri non leggibili", ""])
        for stat in sorted(progetti_con_errore, key=lambda s: s["nome"]):
            righe.append(f"- **{stat['nome']}**: {stat['errore']}")

    righe.extend([
        "",
        "## Per Agente (Globale)",
        "",
        "| Agente | Esecuzioni | Costo | Latenza ms | Rework |",
        "|---|---:|---:|---:|---:|",
    ])
    for agente, riga in sorted(agente_stats.items()):
        righe.append(f"| {agente} | {riga['esecuzioni']} | {denaro(riga['costo'])} | {riga['latenza']} | {riga['rework']} |")

    righe.extend([
        "",
        "## Ultimi eventi (Timeline aggregata)",
        "",
        "| Timestamp | Progetto | Compito | Agente | Tipo | Stato | Gate | Umano | Note |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for ev in tutti_eventi[:30]:
        note = str(ev.get("note", "")).replace("|", "\\|").replace("\n", " ")
        righe.append(
            f"| {ev.get('timestamp', '')} | {ev.get('_progetto_nome', '')} | {ev.get('id_compito', '')} | "
            f"{ev.get('agente', '')} | {ev.get('tipo_compito', '')} | {ev.get('stato', '')} | "
            f"{ev.get('esito_gate', '')} | {ev.get('verdetto_umano', '')} | {note} |"
        )
    righe.append("")
    return "\n".join(righe)

def main() -> int:
    parser = argparse.ArgumentParser(description="Genera il cruscotto Markdown aggregando più progetti")
    parser.add_argument("--progetti", default=str(PERCORSO_PROGETTI_PREDEFINITO))
    parser.add_argument("--output", default=str(PERCORSO_CRUSCOTTO_PREDEFINITO))
    args = parser.parse_args()

    progetti = carica_progetti(Path(args.progetti))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(renderizza(progetti), encoding="utf-8", newline="\n")
    print(f"cruscotto aggregato scritto in {output}")
    return 0

if __name__ == "__main__":
    main()
