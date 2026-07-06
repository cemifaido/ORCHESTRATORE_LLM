# Esperimento Sveglia Agenti e Polling Asincrono

Questo documento riporta l'analisi scientifica, le fasi sperimentali, gli intoppi tecnici e le conclusioni relative all'implementazione sperimentale di una "sveglia" (wake-up) automatica per stimolare gli agenti inattivi.

---

## 🎯 Obiettivi dell'Esperimento

Nel contesto del coordinamento multi-agente asincrono tramite bacheca (`bacheca.py`), l'interazione richiede solitamente che l'operatore umano o gli agenti leggano e scrivano in modalità "pull". 
Per ridurre la latenza di attivazione e superare i limiti di integrazione, abbiamo testato:
1. **Sveglia Manuale (Trigger Un click)**: Un pulsante sulla dashboard per inviare un prompt esplicito a un agente specifico per fargli elaborare i messaggi pendenti.
2. **Polling Automatico (Ciclo 15 secondi)**: Un thread demone in background che scansiona la bacheca e sveglia automaticamente gli agenti destinatari di richieste pendenti.

---

## 🏗️ Architettura e Comandi di Risveglio

Il backend del server locale (`interfaccia.py`) è stato dotato di endpoint dedicati per invocare i comandi nativi degli agenti in background:

*   **Gemini (Antigravity IDE)**:
    ```powershell
    antigravity-ide.cmd chat --reuse-window "python bacheca.py prossimo --agente gemini"
    ```
*   **Claude (Claude Code)**:
    ```powershell
    npx @anthropic-ai/claude-code "python bacheca.py prossimo --agente claude"
    ```
*   **Codex (Codex CLI)**:
    ```powershell
    codex.cmd "python bacheca.py prossimo --agente codex"
    ```

---

## 🧪 Fasi Sperimentali ed Esiti

### 1. Codex (CLI)
*   **Bug di Configurazione Rilevato**: Durante l'attivazione iniziale, Codex falliva con un errore relativo all'invalidità del modello configurato (`The model "\" does not appear in the list...`). È stato diagnosticato che il file globale `~/.codex/config.json` era corrotto nel campo `"model": "\\"`. Abbiamo risolto impostando correttamente `"model": "o4-mini"`.
*   **Risultato del Trigger**: Il comando si è avviato correttamente aprendo una nuova scheda di terminale Codex, ma si è bloccato a causa della mancanza di crediti/quota sull'account OpenAI del cliente (`⚠️ Insufficient quota`).
*   **Verdetto**: Il trigger di per sé funziona ma l'agente non è operativo per motivi di fatturazione esterni.

### 2. Claude (CLI)
*   **Risultato del Trigger**: Il comando `npx @anthropic-ai/claude-code` si avvia correttamente e apre una scheda terminale concorrente.
*   **Blocco di Autenticazione**: Trattandosi di un nuovo processo avviato in background dal server Uvicorn, esso non eredita la sessione autenticata o il token memorizzato nella cache del terminale interattivo principale dell'utente. Di conseguenza, Claude si arresta all'avvio chiedendo di eseguire nuovamente l'accesso via OAuth browser.
*   **Verdetto**: La sveglia in background fallisce per barriere di autenticazione.

### 3. Gemini (GUI/IDE)
*   **Bug del Parsing degli Spazi su Windows**: Inizialmente il trigger falliva silenziosamente perché il percorso dell'eseguibile conteneva spazi (`.../Programs/Antigravity IDE/...`). La chiamata originaria via `cmd.exe /c` spezzava il percorso interpretando erroneamente la prima parte. Corretto lanciando lo script wrapper `.cmd` direttamente in `subprocess.Popen` (sfruttando il quoting nativo di Python).
*   **Risultato del Trigger**: Il comando `antigravity-ide.cmd chat --reuse-window` viene eseguito con successo dal sistema (codice di uscita 0). Tuttavia, **l'IDE non reagisce in alcun modo**: non si focalizza, non apre la chat e non digita il prompt. Questo comportamento è stato confermato sia per le chiamate in background che per quelle digitate manualmente dall'utente nel proprio terminale interattivo.
*   **Ipotesi Electron IPC**: Il protocollo IPC di Electron richiede che il processo chiamante e l'IDE risiedano nella stessa "Window Station" interattiva. L'avvio del server in modalità nascosta (`-WindowStyle Hidden`) isola il processo chiamante, inibendo la comunicazione. Inoltre, la versione dell'IDE potrebbe ignorare l'input o trattarlo come stub.

---

## 📌 Conclusioni e Decisioni Architetturali

L'esperimento ha dimostrato l'inutilizzabilità pratica della sveglia attiva asincrona in questo ambiente di sviluppo locale:

1.  **Limiti strutturali dei CLI (Claude/Codex)**: Le interfacce a riga di comando non dispongono di un canale di comunicazione a caldo per iniettare testo in sessioni interattive già aperte. Qualsiasi trigger esterno crea nuovi processi orfani paralleli soggetti a barriere di autenticazione (Claude) o spreco di risorse.
2.  **Limiti dell'IPC GUI (Gemini/IDE)**: La CLI nativa dell'IDE non recapita correttamente le istruzioni di chat alla finestra attiva, rendendo inefficace il risveglio.
3.  **Verdetto Finale**: 
    *   **Il polling automatico in background è stato disattivato** per tutti gli agenti (interruttore della Dashboard impostato permanentemente su `False` e modificato in `🧪 Polling Auto Gemini (15s)` come test isolato).
    *   L'architettura del progetto si affida interamente agli **hook di sessione passivi** (`UserPromptSubmit` e `.agents/hooks.json`), che leggono la bacheca in background solo *mentre* l'utente interagisce attivamente con l'agente nella sua chat principale, garantendo efficacia a costo zero e senza interruzioni di flusso.
