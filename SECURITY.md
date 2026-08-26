# Sicurezza

Squadra coordina più assistenti AI sullo stesso codicebase e tiene un registro
append-only di quello che fanno: la superficie di rischio principale non è
"un exploit da remoto", ma azioni indesiderate compiute da un agente con
accesso al repository (scrittura di file, comandi, eventuale dispatch verso
altri agenti). La postura completa — mitigazioni già in atto, confini di
responsabilità, ipotesi esplicite — è documentata in
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## Segnalare una vulnerabilità

Se trovi un problema di sicurezza (bypass della whitelist della Sentinella,
modo per far eseguire comandi arbitrari, fuga di dati locali verso un
provider, escalation nel dispatch headless del Postino, o altro):

- **Non aprire una issue pubblica.** Scrivi direttamente a
  **paolo.pavesi@gmail.com** con una descrizione del problema, i passi per
  riprodurlo e l'impatto che ritieni possibile.
- In alternativa, se disponibile sul repository GitHub, usa la funzione
  "Report a vulnerability" (GitHub Security Advisories) per una segnalazione
  privata.

Non è richiesto alcun formalismo particolare: una descrizione chiara basta a
partire. Prova a includere versione di Squadra/commit, sistema operativo e,
se pertinente, quale componente (Sentinella, bacheca, registro, Postino,
dashboard) è coinvolto.

## Cosa aspettarti

Questo è un progetto personale mantenuto part-time: non c'è una SLA formale,
ma le segnalazioni di sicurezza hanno priorità sul resto. Riceverai una
conferma di lettura appena possibile e sarai tenuto/a informato/a sui
progressi fino alla risoluzione o alla chiusura motivata della segnalazione.

## Fuori perimetro

Non sono considerate vulnerabilità di Squadra:

- Comportamento dei provider AI esterni (Claude, Codex, Gemini) o dei loro
  account/API — segnalali direttamente al provider.
- Configurazioni locali non generiche che un utente ha scelto di committare
  di propria iniziativa, in violazione delle indicazioni di
  `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` e di `.gitignore`.
- Mancanza di funzionalità di sicurezza non ancora previste dal
  [threat model](docs/THREAT_MODEL.md) — proponile come discussione/issue,
  non come segnalazione riservata.
