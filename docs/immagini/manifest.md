# Manifesto delle schermate di documentazione

Tutte le immagini sono catturate dal progetto **"Demo (dati finti)"**
(`esempi/demo_dashboard/allestisci.py`) — nessun percorso reale, credenziale o
dato operativo privato.

| File | Didascalia | Uso |
|---|---|---|
| `piano-corsie.png` | Widget "corsie" del piano dichiarato su un thread: avanzamento percentuale, passi con proprietario e `write_set` disgiunto, azioni disponibili. | README.md / README_EN.md, sezione "Squadra all'opera". |
| `piano-collisione.png` | Avviso di collisione fra due passi in corso che scrivono lo stesso file (`write_x_write`) — avviso, non blocco. | README.md / README_EN.md, sezione "Squadra all'opera". |
| `bacheca-3-agenti.png` | Pannello della bacheca: profilo operativo, messaggi pendenti per agente, garanzie reali per agente, banner conflitto. | README.md / README_EN.md, sezione "Squadra all'opera". |

## Scartate (contenevano dati reali)

- `dashboard-timeline.png` — la Timeline eventi aggrega **tutti** i progetti, non
  solo la Demo: mostrava id-compito reali di questa sessione e testo di
  un'approvazione umana. La vista non ha un filtro per-progetto, quindi la
  schermata della timeline è stata rimossa dal set.
- `replay-commit.png` — mostrava un commit reale con autore; l'etichetta del
  progetto ("Demo") era anche incoerente col contenuto. Rimossa.
