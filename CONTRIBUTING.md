# Contribuire a Squadra

Grazie per l'interesse. Questo documento spiega come proporre modifiche in
modo che siano facili da rivedere e integrare.

## Prima di iniziare

- Per bug o proposte di funzionalità, apri una issue descrivendo il problema
  o l'idea prima di scrivere codice, così si evita lavoro scartato.
- Per una vulnerabilità di sicurezza, **non aprire una issue pubblica**: segui
  invece [SECURITY.md](SECURITY.md).
- Dai un'occhiata a [docs/INDEX.md](docs/INDEX.md) per orientarti tra le
  guide esistenti prima di riscrivere qualcosa che è già documentato altrove.

## Ambiente di sviluppo

```powershell
git clone <URL-DEL-REPOSITORY> Squadra
cd Squadra
.\setup.ps1
pip install -r requirements-dev.txt
```

Nessun account AI è necessario per contribuire: dashboard, bacheca, registro,
Sentinella e l'intera test suite funzionano anche senza Claude/Codex/Gemini
configurati.

## Quality gate, sempre prima di proporre una modifica

```powershell
python -m pytest
python -m ruff check .
python -m mypy .
python -m xenon --max-absolute C --max-modules B --max-average B .
```

Una pull request che non passa questi quattro controlli non viene presa in
carico per la revisione. Se il repository ha l'hook pre-commit installato
(`setup.ps1` lo propone), questi controlli girano automaticamente prima di
ogni commit.

## Cosa rende una modifica facile da accettare

- **Un cambiamento, una pull request.** Evita di mischiare un refactor con
  una nuova funzionalità.
- **Niente dati proprietari nei commit**: percorsi assoluti della tua
  macchina, credenziali, contenuto reale di sessioni/log. Vedi la sezione
  "Dati proprietari non generici" in `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` —
  vale per chiunque contribuisca, non solo per gli agenti AI.
- **Azioni irreversibili restano manuali**: se la modifica tocca commit,
  push, cancellazioni o dispatch automatico verso altri agenti, deve
  rispettare i confini già descritti in
  [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) — default-deny, verdetto
  umano esplicito, nessuna scorciatoia silenziosa.
- **Test per il comportamento nuovo**, non solo per il caso felice: guarda
  `tests/` per lo stile già in uso nel progetto.

## Stile del codice

- Italiano per nomi di funzioni/variabili/commenti nel dominio applicativo
  (coerente con il resto del codicebase); commenti solo dove il *perché* non
  è ovvio dal codice.
- `ruff`/`mypy`/`xenon` sono la fonte di verità per formato, tipi e
  complessità: non serve discuterne caso per caso, basta farli passare.

## Pull request

Descrivi cosa cambia e perché, non solo cosa fai riga per riga — il "perché"
è quello che si perde più facilmente in revisione. Se la modifica tocca un
comportamento documentato, aggiorna anche la documentazione pertinente nello
stesso PR.
