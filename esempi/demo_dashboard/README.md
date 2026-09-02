# Demo dashboard — dati finti per le schermate

`allestisci.py` genera un progetto **demo** con bacheca, registro, note di codice
e stati di consegna completamente inventati (nessuna conversazione o percorso
reale), da usare per le schermate del README senza esporre dati proprietari.

```
python esempi/demo_dashboard/allestisci.py
python interfaccia.py            # dashboard su http://127.0.0.1:8095
```

Nella dashboard seleziona **"Demo (dati finti)"**. Cosa mostra:

- **`demo-export`** — un compito con piano dichiarato a tre corsie (write-set
  disgiunti): un passo `fatto`, due `in_corso` con proprietari diversi;
- **`demo-collisione`** — due passi che scrivono lo stesso file → il widget
  segnala la collisione (avviso, non blocco);
- **`demo-attesa`** — un messaggio pendente per un agente, con lo stato di
  consegna `acquisito_da_hook`;
- **`demo-chiuso`** — un thread concluso;
- il **registro** con quattro eventi (gate superati, un'approvazione umana);
- due **note di codice** ancorate a `report/export.py`.

I dati generati vivono in `progetto/dati_locali/` (gitignored, rigenerabile).
Lo script è idempotente: rilancialo per ripartire da zero.
