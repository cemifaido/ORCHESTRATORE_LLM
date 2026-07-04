#!/usr/bin/env python3
"""Cruscotto web locale dell'orchestratore: una pagina che si aggiorna da sola.

Legge il registro `eventi.jsonl` a ogni richiesta e mostra, per agente, esecuzioni/costo/
latenza/rework/voti + gli ultimi eventi. Solo libreria standard: nessuna dipendenza.

    python cruscotto_web.py --registro dati_locali/orchestrazione/eventi.jsonl --porta 8787

Poi apri http://127.0.0.1:8787 nel browser. La pagina fa polling ogni pochi secondi.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import registro

PERCORSO_REGISTRO = Path("dati_locali") / "orchestrazione" / "eventi.jsonl"


def costruisci_dati(percorso: Path) -> dict[str, Any]:
    eventi = registro.leggi_eventi(percorso)
    stat = registro.metriche(eventi)
    agenti = []
    for agente, r in sorted(stat.items()):
        agenti.append({
            "agente": agente,
            "esecuzioni": r["esecuzioni"],
            "costo": round(float(r["costo"]), 4),
            "latenza_ms": int(r["latenza"]),
            "rework": r["rework"],
            "qualita": registro.media_voto(int(r["voto_q_somma"]), int(r["voto_q_n"])),
            "velocita": registro.media_voto(int(r["voto_v_somma"]), int(r["voto_v_n"])),
        })
    campi = ("timestamp", "id_compito", "agente", "tipo_compito", "stato",
             "esito_gate", "verdetto_umano", "voto_qualita", "voto_velocita", "note")
    ultimi = [{c: e.get(c) for c in campi} for e in eventi[-30:][::-1]]
    return {
        "totale_eventi": len(eventi),
        "costo_totale": round(sum(float(e.get("costo_stimato_usd") or 0) for e in eventi), 4),
        "latenza_totale_ms": sum(int(e.get("latenza_ms") or 0) for e in eventi),
        "agenti": agenti,
        "ultimi": ultimi,
    }


PAGINA = """<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>Cruscotto orchestratore</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; margin: 1.5rem; background:#0f172a; color:#e2e8f0; }
  h1 { font-size: 1.3rem; } h2 { font-size: 1rem; margin-top: 1.5rem; color:#94a3b8; }
  .cards { display:flex; gap:1rem; flex-wrap:wrap; margin:1rem 0; }
  .card { background:#1e293b; border:1px solid #334155; border-radius:8px; padding:.8rem 1.2rem; min-width:9rem; }
  .card b { display:block; font-size:1.5rem; }
  table { border-collapse: collapse; width:100%; margin-top:.5rem; font-size:.9rem; }
  th,td { border:1px solid #334155; padding:.35rem .6rem; text-align:left; }
  th { background:#1e293b; } td.n { text-align:right; font-variant-numeric: tabular-nums; }
  .rw { color:#f87171; font-weight:600; } .ok { color:#4ade80; }
  .muted { color:#64748b; font-size:.8rem; }
</style></head>
<body>
  <h1>Cruscotto orchestratore LLM <span class="muted" id="agg"></span></h1>
  <div class="cards">
    <div class="card">Eventi <b id="tot">–</b></div>
    <div class="card">Costo totale <b id="costo">–</b></div>
    <div class="card">Latenza cumulata <b id="lat">–</b></div>
  </div>
  <h2>Per agente</h2>
  <table><thead><tr><th>Agente</th><th>Esec.</th><th>Costo $</th><th>Latenza ms</th><th>Rework</th><th>Qualità</th><th>Velocità</th></tr></thead>
  <tbody id="agenti"></tbody></table>
  <h2>Ultimi eventi</h2>
  <table><thead><tr><th>Quando</th><th>Compito</th><th>Agente</th><th>Tipo</th><th>Stato</th><th>Gate</th><th>Umano</th><th>Q</th><th>V</th><th>Note</th></tr></thead>
  <tbody id="ultimi"></tbody></table>
<script>
const esc = s => (s==null?'':String(s)).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function agg() {
  try {
    const d = await (await fetch('/dati')).json();
    tot.textContent = d.totale_eventi;
    costo.textContent = '$' + d.costo_totale.toFixed(4);
    lat.textContent = (d.latenza_totale_ms/1000).toFixed(1) + ' s';
    agenti.innerHTML = d.agenti.map(a =>
      `<tr><td>${esc(a.agente)}</td><td class=n>${a.esecuzioni}</td><td class=n>${a.costo.toFixed(4)}</td>`+
      `<td class=n>${a.latenza_ms}</td><td class="n ${a.rework?'rw':'ok'}">${a.rework}</td>`+
      `<td class=n>${a.qualita??'—'}</td><td class=n>${a.velocita??'—'}</td></tr>`).join('');
    ultimi.innerHTML = d.ultimi.map(e =>
      `<tr><td>${esc(e.timestamp)}</td><td>${esc(e.id_compito)}</td><td>${esc(e.agente)}</td>`+
      `<td>${esc(e.tipo_compito)}</td><td>${esc(e.stato)}</td>`+
      `<td class="${e.esito_gate==='fallito'?'rw':'ok'}">${esc(e.esito_gate)}</td>`+
      `<td>${esc(e.verdetto_umano)}</td><td class=n>${e.voto_qualita??'—'}</td>`+
      `<td class=n>${e.voto_velocita??'—'}</td><td>${esc(e.note)}</td></tr>`).join('');
    agg_el.textContent = '· aggiornato ' + new Date().toLocaleTimeString();
  } catch (err) { agg_el.textContent = '· errore: ' + err; }
}
const agg_el = document.getElementById('agg');
agg(); setInterval(agg, 3000);
</script></body></html>"""


class Gestore(BaseHTTPRequestHandler):
    def _invia(self, codice: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codice)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self) -> None:  # noqa: N802 (nome imposto da http.server)
        if self.path.rstrip("/") in ("", "/"):
            self._invia(200, PAGINA.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path.startswith("/dati"):
            try:
                dati = costruisci_dati(PERCORSO_REGISTRO)
                self._invia(200, json.dumps(dati, ensure_ascii=False).encode("utf-8"), "application/json")
            except Exception as errore:  # il registro potrebbe essere temporaneamente incoerente
                self._invia(500, json.dumps({"errore": str(errore)}).encode("utf-8"), "application/json")
            return
        self._invia(404, b"not found", "text/plain")

    def log_message(self, *_args: Any) -> None:  # silenzia il log per riga
        pass


def main() -> int:
    global PERCORSO_REGISTRO
    parser = argparse.ArgumentParser(description="Cruscotto web dell'orchestratore (auto-aggiornante)")
    parser.add_argument("--registro", default=str(PERCORSO_REGISTRO))
    parser.add_argument("--porta", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    PERCORSO_REGISTRO = Path(args.registro)
    server = ThreadingHTTPServer((args.host, args.porta), Gestore)
    print(f"Cruscotto attivo su http://{args.host}:{args.porta}  (registro: {PERCORSO_REGISTRO})")
    print("Premi Ctrl+C per fermarlo.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nfermato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
