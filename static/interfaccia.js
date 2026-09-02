    const I18N = {
      it: {
        // Header & Global
        header_title: "Orchestratore LLM",
        header_subtitle: "Framework di lavoro multi-agente & watchdog",
        btn_refresh: "🔄 Aggiorna Dati",
        btn_restart: "⟲ Riavvia Sistema",
        btn_restart_title: "Riavvia il processo del server per applicare modifiche al codice",
        restart_confirm: "Riavviare il processo del server? La dashboard sarà irraggiungibile per qualche secondo.",
        restart_in_progress: "⟲ Riavvio in corso...",
        restart_requested: "Riavvio richiesto: attendo che il nuovo processo sia pronto...",
        restart_timeout: "Il server non ha risposto entro 30s dopo il riavvio: controllalo manualmente.",
        restart_request_failed: "La richiesta di riavvio non ha ricevuto conferma: il server e' rimasto invariato.",
        code_stale: "⚠ Codice modificato dall'avvio ({files}). Riavvia la dashboard per applicare le modifiche.",
        code_unverifiable: "⚠ Impossibile verificare se il codice del dashboard e' aggiornato.",
        btn_restart_now: "Riavvia ora",
        loading_data_error: "Errore nel caricamento dei dati: ",

        // Summary cards
        card_projects: "Progetti Monitorati",
        card_events: "Eventi Registrati",
        card_latency: "Tempo Elaborazione LLM Cumulato",

        // Left Column: Progetti
        widget_projects_title: "📁 Progetti in Monitoraggio",
        projects_loading: "Caricamento progetti...",
        projects_empty: "Nessun progetto registrato.",
        project_active_modules: "Moduli attivi: ",
        project_llm_time: "Tempo LLM: ",
        project_rework: "Rework: ",
        project_error: "⚠ Registro non leggibile: ",

        // Left Column: Aggiungi Progetto
        widget_add_project_title: "➕ Integra e Monitora Nuovo Progetto",
        label_proj_name: "Nome Progetto",
        placeholder_proj_name: "es. Progetto Esempio",
        label_proj_path: "Percorso Cartella (Assoluto)",
        placeholder_proj_path: "es. D:/Share/py/mio_progetto",
        btn_add_project: "Esegui Integrazione & Monitoraggio",
        project_added_success: 'Progetto "{nome}" integrato e monitorato con successo!',

        // Left Column: Sentinella
        widget_sentinel_title: "⚡ Trigger Guardiano (Sentinella)",
        label_select_proj: "Seleziona Progetto",
        label_whitelisted_cmd: "Comando Whitelistato",
        option_select_proj_first: "Seleziona prima un progetto...",
        option_no_cmd: "Nessun comando configurato",
        btn_run_sentinel: "Lancia Gate Esecuzione",
        sentinel_starting: 'Avvio sentinella per comando "{cmd}" su progetto "{proj}"...\n',
        sentinel_outcome: ">> Esito sentinella: ",
        sentinel_return_code: "codice ritornato: ",
        sentinel_local_triage: "Triage locale: ",
        sentinel_exec_error: "Errore esecuzione: ",
        sentinel_finished: 'Comando "{cmd}" terminato con esito: {gate}',

        // Right Column: Latenze & Grafici
        widget_latency_title: "⏱️ Tempo Elaborazione LLM Cumulato per Agente",
        th_agent: "Agente",
        th_cum_time: "Tempo cumulato",
        th_interactions: "Interazioni",
        latency_no_data: "Nessun dato disponibile.",
        widget_runs_title: "📊 Esecuzioni e Rework per Agente",
        chart_runs_label: "Esecuzioni",
        chart_rework_label: "Rework",
        widget_workshare_title: "📊 Quota Lavoro per Agente (DB / Backend / Frontend)",
        chart_db_label: "Database",
        chart_backend_label: "Backend",
        chart_frontend_label: "Frontend",

        // Replay Commit Reale
        widget_replay_title: "🎬 Replay di un Commit Reale",
        replay_desc: "Scegli un progetto e un commit reale per rivedere, animata sul diagramma, la sequenza di eventi che lo hanno preceduto.",
        label_proj: "Progetto",
        label_relive_commit: "Rivivi un commit reale:",
        btn_play: "🎬 Riproduci",
        commit_select_placeholder: "Seleziona un commit...",
        commit_none_avail: "Nessun commit disponibile",
        commit_load_fail: "Impossibile caricare i commit",
        commit_author_label: "Autore: ",
        interaction_singular: "1 interazione collegata",
        interaction_plural: "{count} interazioni collegate",
        interaction_short_singular: "1 interazione",
        interaction_short_plural: "{count} interazioni",
        select_commit_to_play: "Seleziona un commit da riprodurre.",
        replay_retrieving_events: "<b>[Sistema]</b> Recupero gli eventi reali del commit selezionato...",
        replay_no_events: "Nessun evento registrato nella finestra di questo commit.",
        replay_starting: "<b>[Sistema]</b> Replay di {count} eventi reali di questo commit...",
        replay_complete_header: "📊 REPLAY COMPLETATO — DATI REALI DI QUESTO COMMIT",
        replay_free_checks: "dei controlli di verifica gestiti GRATIS dal modello locale",
        replay_free: "gratis",
        replay_paid: "a pagamento",
        replay_est_savings: "Stima risparmio: ",
        replay_no_savings_checks: "Nessun controllo di verifica in questo commit da cui stimare un risparmio.",

        // SVG Diagram Nodes
        node_umano: "Umano",
        node_gemini: "Gemini",
        node_claude: "Claude",
        node_codex: "Codex",
        node_locale: "Locale",
        node_sistema: "Gestore Squadra",

        // Console Handoff
        console_coop_title: "💬 Registro di Cooperazione & Messaggi",
        console_initial_waiting: "In attesa. Scegli un commit e clicca \"Riproduci\" per rivivere la sequenza...",

        // Anelli Livello
        widget_rings_title: "🎯 Quota Lavoro per Livello (Database · Backend · Frontend)",
        rings_desc: "Anello interno = Database, anello centrale = Backend, anello esterno = Frontend. Ogni anello è diviso per agente (stesso colore del diagramma sopra). Vista decorativa: per confrontare i valori con precisione usa il grafico a barre \"Quota Lavoro per Agente\".",
        ring_db: "Database (centro)",
        ring_backend: "Backend (centrale)",
        ring_frontend: "Frontend (superficie)",

        // Bacheca
        widget_bacheca_title: "🗂️ Bacheca Multi-Agente",
        bacheca_read_only_notice: "Questa vista e' di sola lettura: la fase workflow e' derivata dalle evidenze append-only in bacheca e registro. Un'approvazione si registra nella bacheca, non modifica direttamente la fase.",
        label_profilo_operativo: "📬 Profilo Operativo Postino:",
        header_guarantees_matrix: "🛡️ Garanzie Reali per Agente (Nessuna falsa promessa)",
        label_postino_auto: "📬 Postino Automatico:",
        label_headless_dispatch: "🤖 Dispatch Headless:",
        label_headless_dispatch_title: "Fa rispondere davvero claude/codex in background (claude -p / codex exec), senza aprire finestre. Richiede il Postino Automatico attivo. Gemini non e' supportato (resta a finestra).",
        status_active: "🟢 ATTIVO",
        status_disabled: "🔴 DISATTIVATO",
        postino_auto_on_title: "Postino Automatico attivo (risveglio automatico su nuovi messaggi). Clicca per disattivare.",
        postino_auto_off_title: "Postino Automatico disattivato (file POSTINO_ATTIVO assente). Clicca per attivare.",
        headless_on_title: "Dispatch headless attivo: claude/codex rispondono in background su nuovi messaggi, senza aprire finestre. Clicca per disattivare.",
        headless_off_title: "Dispatch headless disattivato: il postino apre solo la finestra dell'agente, va incollato e inviato a mano. Clicca per attivare.",
        headless_requires_postino: "Richiede prima il Postino Automatico attivo.",
        postino_activated_msg: "Postino Automatico ATTIVATO",
        postino_deactivated_msg: "Postino Automatico DISATTIVATO",
        headless_activated_msg: "Dispatch Headless ATTIVATO",
        headless_deactivated_msg: "Dispatch Headless DISATTIVATO",
        activate_postino_first: "Attiva prima il Postino Automatico.",
        header_pending_agents: "Messaggi pendenti per agente",
        btn_wake: "⚡ Risveglia",
        btn_wake_title: "Apre l'agente e copia il prompt di risveglio",
        btn_copy_cmd: "Copia comando",
        mode_hook_active: "hook attivo",
        mode_manual_pull: "pull manuale",
        header_suspended_tasks: "⏸️ Pratiche Sospese & Checkpoint v2 (Weft)",
        no_suspended_tasks: "Nessuna pratica sospesa in attesa.",
        actions_expected_by_outcome: "Azioni previste per esito:",
        badge_awaits: "Attende: ",
        label_human_verdict: "Verdetto Umano: ",
        header_live_activity: "Attività live",
        btn_feed_start: "▶ Avvia",
        btn_feed_pause: "⏸ Ferma",
        feed_initial_paused: "Live ferma. Premi \"▶ Avvia\" per seguire l'attività in tempo reale (con qualche secondo di ritardo).",
        feed_started: "Live avviata, in attesa del prossimo aggiornamento (ogni 5s)...",
        feed_proj_changed: "Progetto cambiato, in attesa di nuova attività...",
        th_thread: "Thread",
        th_status: "Stato",
        th_phase: "Fase Workflow (compito_standard)",
        th_last_sender: "Ultimo mittente",
        th_type: "Tipo",
        th_awaits: "Aspetta",
        th_human_verdict: "Verdetto umano",
        th_action: "",
        bacheca_loading: "Caricamento bacheca...",
        bacheca_no_threads: "Nessun thread in bacheca per questo progetto.",
        btn_relive: "▶ Rivivi",
        header_locked_files: "File attualmente in carico",
        none_locked: "Nessuno.",
        lease_expires: "lease",
        lease_no_expiry: "senza scadenza",
        conflict_banner: "⚠ {count} conflitto{suffix} segnalat{suffix2}, ancora da revisionare",
        thread_replay_completed: "📬 REPLAY DEL THREAD COMPLETATO",
        thread_loading: "Caricamento thread {id}...",
        thread_load_error: "Impossibile caricare la cronologia del thread.",
        revisione_label: "Chiedi una revisione (sola lettura: git diff/log, test, lint):",
        revisione_btn: "🔎 Revisione da {agente}",
        revisione_in_corso: "Richiesta di revisione a {agente} in corso...",
        revisione_errore: "Errore: {messaggio}",
        wake_prompt_copied: "Prompt per {agente} copiato negli appunti. Se la chat si apre vuota, incolla e invia.",
        wake_copy_fail: "Apro {agente}, ma non sono riuscito a copiare il prompt negli appunti.",
        cmd_copied: "Comando copiato: ",
        cmd_copy_fail: "Impossibile copiare il comando: ",
        auto_wake_sent: "Risveglio automatico inviato per: ",

        // Timeline Eventi
        widget_timeline_title: "⏳ Timeline degli Eventi Aggregati",
        th_timestamp: "Timestamp",
        th_project: "Progetto",
        th_task: "Compito",
        th_gate: "Gate",
        th_human: "Umano",
        th_notes: "Note",
        timeline_loading: "Caricamento eventi...",
        timeline_empty: "Nessun evento in timeline.",
        btn_prev: "‹ Precedente",
        btn_next: "Successiva ›",
        timeline_page_info: "Pagina {page} di {pages} ({total} eventi totali)",

        // Workflow Stepper
        step_task: "1. Compito",
        step_gate: "2. Gate",
        step_triage: "3. Triage",
        step_log: "4. Registro",
        step_human: "5. Umano",
        step_action: "6. Azione",
        step_close: "7. Chiusura",

        // Piano Dichiarato (S14.3)
        piano_title: "🎯 Piano Dichiarato",
        piano_no_steps: "Nessun passo definito in questo piano.",
        piano_progress: "{completed}/{total} passi completati",
        passo_owner: "Proprietario: ",
        passo_unassigned: "(non assegnato)",
        passo_writes: "Scrittura:",
        passo_reads: "Lettura:",
        btn_take_step: "✋ Prendi passo",
        btn_handoff_step: "🤝 Proponi handoff",
        btn_done_step: "✔ Fatto",
        btn_block_step: "⛔ Bloccato",
        handoff_pending_title: "🤝 Proposte di Handoff in Attesa",
        handoff_proposed: "Passo <b>{passo}</b>: proposta da <b>{da}</b> a <b>{a}</b> (richiesta da {attore})",
        btn_approve_handoff: "Approva Handoff",
        piano_collision_warn: "⚠ Attenzione: Rilevata possibile collisione o sovrapposizione tra passi in corso."
      },
      en: {
        // Header & Global
        header_title: "LLM Orchestrator",
        header_subtitle: "Multi-agent teamwork framework & watchdog",
        btn_refresh: "🔄 Refresh Data",
        btn_restart: "⟲ Restart System",
        btn_restart_title: "Restart server process to apply code changes",
        restart_confirm: "Restart server process? The dashboard will be unavailable for a few seconds.",
        restart_in_progress: "⟲ Restart in progress...",
        restart_requested: "Restart requested: waiting for new process to be ready...",
        restart_timeout: "The server did not respond within 30s after restart: please check manually.",
        restart_request_failed: "The restart request was not acknowledged; the server was left unchanged.",
        code_stale: "⚠ Code changed since startup ({files}). Restart the dashboard to apply changes.",
        code_unverifiable: "⚠ Unable to verify whether the dashboard code is current.",
        btn_restart_now: "Restart now",
        loading_data_error: "Error loading data: ",

        // Summary cards
        card_projects: "Monitored Projects",
        card_events: "Recorded Events",
        card_latency: "Cumulative LLM Processing Time",

        // Left Column: Projects
        widget_projects_title: "📁 Monitored Projects",
        projects_loading: "Loading projects...",
        projects_empty: "No registered projects.",
        project_active_modules: "Active modules: ",
        project_llm_time: "LLM Time: ",
        project_rework: "Rework: ",
        project_error: "⚠ Audit log unreadable: ",

        // Left Column: Add Project
        widget_add_project_title: "➕ Integrate & Monitor New Project",
        label_proj_name: "Project Name",
        placeholder_proj_name: "e.g. My App Backend",
        label_proj_path: "Folder Path (Absolute)",
        placeholder_proj_path: "e.g. D:/Share/py/my_project",
        btn_add_project: "Execute Integration & Monitoring",
        project_added_success: 'Project "{nome}" integrated and monitored successfully!',

        // Left Column: Sentinel
        widget_sentinel_title: "⚡ Guardian Trigger (Sentinel)",
        label_select_proj: "Select Project",
        label_whitelisted_cmd: "Whitelisted Command",
        option_select_proj_first: "Select a project first...",
        option_no_cmd: "No command configured",
        btn_run_sentinel: "Run Execution Gate",
        sentinel_starting: 'Starting sentinel for command "{cmd}" on project "{proj}"...\n',
        sentinel_outcome: ">> Sentinel outcome: ",
        sentinel_return_code: "return code: ",
        sentinel_local_triage: "Local triage: ",
        sentinel_exec_error: "Execution error: ",
        sentinel_finished: 'Command "{cmd}" finished with outcome: {gate}',

        // Right Column: Latencies & Charts
        widget_latency_title: "⏱️ Cumulative LLM Processing Time per Agent",
        th_agent: "Agent",
        th_cum_time: "Cumulative time",
        th_interactions: "Interactions",
        latency_no_data: "No data available.",
        widget_runs_title: "📊 Executions and Rework per Agent",
        chart_runs_label: "Executions",
        chart_rework_label: "Rework",
        widget_workshare_title: "📊 Work Share per Agent (DB / Backend / Frontend)",
        chart_db_label: "Database",
        chart_backend_label: "Backend",
        chart_frontend_label: "Frontend",

        // Replay Real Commit
        widget_replay_title: "🎬 Real Commit Replay",
        replay_desc: "Choose a project and a real commit to replay, animated on the diagram, the sequence of events that preceded it.",
        label_proj: "Project",
        label_relive_commit: "Replay a real commit:",
        btn_play: "🎬 Play",
        commit_select_placeholder: "Select a commit...",
        commit_none_avail: "No commit available",
        commit_load_fail: "Unable to load commits",
        commit_author_label: "Author: ",
        interaction_singular: "1 linked interaction",
        interaction_plural: "{count} linked interactions",
        interaction_short_singular: "1 interaction",
        interaction_short_plural: "{count} interactions",
        select_commit_to_play: "Select a commit to replay.",
        replay_retrieving_events: "<b>[System]</b> Retrieving real events for selected commit...",
        replay_no_events: "No events recorded in the window of this commit.",
        replay_starting: "<b>[System]</b> Replaying {count} real events of this commit...",
        replay_complete_header: "📊 REPLAY COMPLETED — REAL DATA FOR THIS COMMIT",
        replay_free_checks: "of verification checks handled for FREE by local model",
        replay_free: "free",
        replay_paid: "paid",
        replay_est_savings: "Estimated savings: ",
        replay_no_savings_checks: "No verification checks in this commit to estimate savings from.",

        // SVG Diagram Nodes
        node_umano: "Human",
        node_gemini: "Gemini",
        node_claude: "Claude",
        node_codex: "Codex",
        node_locale: "Local",
        node_sistema: "Team Manager",

        // Console Handoff
        console_coop_title: "💬 Cooperation Log & Messages",
        console_initial_waiting: "Waiting. Select a commit and click \"Play\" to replay the sequence...",

        // Concentric Rings
        widget_rings_title: "🎯 Work Share per Architectural Layer (DB · Backend · Frontend)",
        rings_desc: "Inner ring = Database, middle ring = Backend, outer ring = Frontend. Each ring is partitioned by agent (same color as diagram above). Decorative view: for precise comparison use the \"Work Share per Agent\" bar chart.",
        ring_db: "Database (inner)",
        ring_backend: "Backend (middle)",
        ring_frontend: "Frontend (outer)",

        // Board
        widget_bacheca_title: "🗂️ Multi-Agent Board",
        bacheca_read_only_notice: "This view is read-only: the workflow phase is derived from append-only board and registry evidence. An approval is recorded on the board; it does not directly change the phase.",
        label_profilo_operativo: "📬 Postino Operating Profile:",
        header_guarantees_matrix: "🛡️ Real Guarantees per Agent (No false promises)",
        label_postino_auto: "📬 Automatic Postman:",
        label_headless_dispatch: "🤖 Headless Dispatch:",
        label_headless_dispatch_title: "Runs claude/codex autonomously in background (claude -p / codex exec) without opening windows. Requires Automatic Postman enabled. Gemini not supported (window only).",
        status_active: "🟢 ACTIVE",
        status_disabled: "🔴 DISABLED",
        postino_auto_on_title: "Automatic Postman active (auto-wakes agents on new messages). Click to disable.",
        postino_auto_off_title: "Automatic Postman disabled (POSTINO_ATTIVO file missing). Click to enable.",
        headless_on_title: "Headless dispatch active: claude/codex respond in background on new messages, without opening windows. Click to disable.",
        headless_off_title: "Headless dispatch disabled: postman opens agent window, must paste and send manually. Click to enable.",
        headless_requires_postino: "Requires Automatic Postman to be active first.",
        postino_activated_msg: "Automatic Postman ACTIVATED",
        postino_deactivated_msg: "Automatic Postman DISABLED",
        headless_activated_msg: "Headless Dispatch ACTIVATED",
        headless_deactivated_msg: "Headless Dispatch DISABLED",
        activate_postino_first: "Activate Automatic Postman first.",
        header_pending_agents: "Pending messages per agent",
        btn_wake: "⚡ Wake up",
        btn_wake_title: "Opens the agent and copies the wakeup prompt",
        btn_copy_cmd: "Copy command",
        mode_hook_active: "hook active",
        mode_manual_pull: "manual pull",
        header_suspended_tasks: "⏸️ Suspended Tasks & Checkpoint v2 (Weft)",
        no_suspended_tasks: "No suspended tasks pending.",
        actions_expected_by_outcome: "Expected actions by outcome:",
        badge_awaits: "Awaiting: ",
        label_human_verdict: "Human Verdict: ",
        header_live_activity: "Live activity",
        btn_feed_start: "▶ Start",
        btn_feed_pause: "⏸ Pause",
        feed_initial_paused: "Live stopped. Press \"▶ Start\" to follow activity in real time (with a few seconds delay).",
        feed_started: "Live started, waiting for next update (every 5s)...",
        feed_proj_changed: "Project changed, waiting for new activity...",
        th_thread: "Thread",
        th_status: "Status",
        th_phase: "Workflow Phase (compito_standard)",
        th_last_sender: "Last sender",
        th_type: "Type",
        th_awaits: "Awaiting",
        th_human_verdict: "Human verdict",
        th_action: "",
        bacheca_loading: "Loading board...",
        bacheca_no_threads: "No threads on the board for this project.",
        btn_relive: "▶ Replay",
        header_locked_files: "Currently locked files",
        none_locked: "None.",
        lease_expires: "lease",
        lease_no_expiry: "no expiry",
        conflict_banner: "⚠ {count} conflict(s) reported, awaiting review",
        thread_replay_completed: "📬 THREAD REPLAY COMPLETED",
        thread_loading: "Loading thread {id}...",
        thread_load_error: "Unable to load thread history.",
        revisione_label: "Request a review (read-only: git diff/log, tests, lint):",
        revisione_btn: "🔎 Review from {agente}",
        revisione_in_corso: "Requesting a review from {agente}...",
        revisione_errore: "Error: {messaggio}",
        wake_prompt_copied: "Prompt for {agente} copied to clipboard. If chat opens empty, paste and send.",
        wake_copy_fail: "Opening {agente}, but failed to copy prompt to clipboard.",
        cmd_copied: "Command copied: ",
        cmd_copy_fail: "Unable to copy command: ",
        auto_wake_sent: "Automatic wakeup sent for: ",

        // Event Timeline
        widget_timeline_title: "⏳ Aggregated Event Timeline",
        th_timestamp: "Timestamp",
        th_project: "Project",
        th_task: "Task",
        th_gate: "Gate",
        th_human: "Human",
        th_notes: "Notes",
        timeline_loading: "Loading events...",
        timeline_empty: "No events in timeline.",
        btn_prev: "‹ Previous",
        btn_next: "Next ›",
        timeline_page_info: "Page {page} of {pages} ({total} total events)",

        // Workflow Stepper
        step_task: "1. Task",
        step_gate: "2. Gate",
        step_triage: "3. Triage",
        step_log: "4. Log",
        step_human: "5. Human",
        step_action: "6. Action",
        step_close: "7. Close",

        // Declared Plan (S14.3)
        piano_title: "🎯 Declared Plan",
        piano_no_steps: "No steps defined in this plan.",
        piano_progress: "{completed}/{total} steps completed",
        passo_owner: "Owner: ",
        passo_unassigned: "(unassigned)",
        passo_writes: "Write set:",
        passo_reads: "Read set:",
        btn_take_step: "✋ Take step",
        btn_handoff_step: "🤝 Propose handoff",
        btn_done_step: "✔ Done",
        btn_block_step: "⛔ Blocked",
        handoff_pending_title: "🤝 Pending Handoff Proposals",
        handoff_proposed: "Step <b>{passo}</b>: proposal from <b>{da}</b> to <b>{a}</b> (requested by {attore})",
        btn_approve_handoff: "Approve Handoff",
        piano_collision_warn: "⚠ Warning: Potential overlap or conflict detected between steps in progress."
      }
    };

    let linguaCorrente = localStorage.getItem("lingua_orchestratore") || "it";
    if (linguaCorrente !== "it" && linguaCorrente !== "en") linguaCorrente = "it";

    function t(key, params = {}, fallback = "") {
      const dict = I18N[linguaCorrente] || I18N["it"];
      let text = dict[key] !== undefined ? dict[key] : (I18N["it"][key] !== undefined ? I18N["it"][key] : (fallback || key));
      if (typeof text === "string" && params && Object.keys(params).length > 0) {
        Object.entries(params).forEach(([k, v]) => {
          text = text.replaceAll(`{${k}}`, v);
        });
      }
      return text;
    }

    function impostaLingua(lingua) {
      if (lingua !== "it" && lingua !== "en") lingua = "it";
      linguaCorrente = lingua;
      localStorage.setItem("lingua_orchestratore", lingua);
      document.documentElement.lang = lingua;

      // Aggiorna stato pulsanti bandiera
      const btnIt = document.getElementById("langItBtn");
      const btnEn = document.getElementById("langEnBtn");
      if (btnIt) btnIt.className = "lang-btn" + (lingua === "it" ? " active" : "");
      if (btnEn) btnEn.className = "lang-btn" + (lingua === "en" ? " active" : "");

      // Aggiorna tutti gli elementi con data-i18n
      document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (key) el.innerHTML = t(key);
      });
      document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
        const key = el.getAttribute("data-i18n-placeholder");
        if (key) el.placeholder = t(key);
      });
      document.querySelectorAll("[data-i18n-title]").forEach(el => {
        const key = el.getAttribute("data-i18n-title");
        if (key) el.title = t(key);
      });

      // Aggiorna etichette SVG diagramma radiale
      const lUmano = document.getElementById("label_node_umano");
      if (lUmano) lUmano.textContent = t("node_umano");
      const lGemini = document.getElementById("label_node_gemini");
      if (lGemini) lGemini.textContent = t("node_gemini");
      const lClaude = document.getElementById("label_node_claude");
      if (lClaude) lClaude.textContent = t("node_claude");
      const lCodex = document.getElementById("label_node_codex");
      if (lCodex) lCodex.textContent = t("node_codex");
      const lLocale = document.getElementById("label_node_locale");
      if (lLocale) lLocale.textContent = t("node_locale");
      const lSistema = document.getElementById("label_node_sistema");
      if (lSistema) lSistema.textContent = t("node_sistema");

      // Re-render dinamico dei componenti per aggiornare testi generati via JS
      aggiornaDati();
      caricaCommit();
    }

    let runsChartInstance = null;
    let livelloChartInstance = null;
    let progettiCorrenti = [];
    let commitCorrenti = [];
    let paginaTimelineCorrente = 1;
    let bachecaFeedAttivo = false;
    let bachecaFeedIdsMostrati = new Set();
    const AGENTI_BACHECA_DASHBOARD = [
      { id: "claude", label: "Claude", modoKey: "mode_hook_active" },
      { id: "codex", label: "Codex", modoKey: "mode_hook_active" },
      { id: "gemini", label: "Gemini", modoKey: "mode_manual_pull" }
    ];

    function escapeHtml(str) {
      if (str == null) return '';
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function formattaOraIt(iso, soloOra = false) {
      const locale = linguaCorrente === "it" ? "it-IT" : "en-US";
      const opzioni = soloOra
        ? { hour: "2-digit", minute: "2-digit", second: "2-digit" }
        : { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" };
      return new Date(iso).toLocaleString(locale, { timeZone: "Europe/Rome", ...opzioni });
    }

    async function copiaTestoNegliAppunti(testo) {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(testo);
        return;
      }
      const area = document.createElement("textarea");
      area.value = testo;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      document.body.removeChild(area);
    }

    let matrixAnimationId = null;

    function initMatrixRain() {
      const canvas = document.getElementById("matrixCanvas");
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      
      const ridimensiona = () => {
        canvas.width = canvas.parentElement.offsetWidth;
        canvas.height = canvas.parentElement.offsetHeight;
      };
      
      ridimensiona();
      window.addEventListener("resize", ridimensiona);
      
      const fontSize = 10;
      const columns = Math.floor(canvas.width / fontSize) + 1;
      const drops = Array(columns).fill(1);
      
      const caratteri = "01M1X0101010101010010101010010101010111010101010101010101ABCDEF";
      let ultimoTempo = 0;
      const fpsInterval = 1000 / 30;
      
      function draw(tempoCorrente) {
        if (document.hidden) {
          matrixAnimationId = null;
          return;
        }
        matrixAnimationId = requestAnimationFrame(draw);
        if (tempoCorrente - ultimoTempo < fpsInterval) return;
        ultimoTempo = tempoCorrente;

        ctx.fillStyle = "rgba(2, 4, 10, 0.08)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = "#39ff14";
        ctx.font = fontSize + "px monospace";
        
        for (let i = 0; i < drops.length; i++) {
          const char = caratteri[Math.floor(Math.random() * caratteri.length)];
          const x = i * fontSize;
          const y = drops[i] * fontSize;
          
          ctx.fillText(char, x, y);
          
          if (y > canvas.height && Math.random() > 0.975) {
            drops[i] = 0;
          }
          drops[i]++;
        }
      }

      const avviaMatrix = () => {
        if (!matrixAnimationId && !document.hidden) {
          matrixAnimationId = requestAnimationFrame(draw);
        }
      };

      const fermaMatrix = () => {
        if (matrixAnimationId) {
          cancelAnimationFrame(matrixAnimationId);
          matrixAnimationId = null;
        }
      };

      document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
          fermaMatrix();
        } else {
          avviaMatrix();
        }
      });
      
      avviaMatrix();
    }

    document.addEventListener("DOMContentLoaded", async () => {
      initMatrixRain();
      impostaLingua(linguaCorrente);

      // Caricamento iniziale completo
      await aggiornaDati();

      // Tier Live: ogni 5 secondi (contatori, postino, pendenti, banner)
      setInterval(aggiornaDatiLive, 5000);

      // Tier Dettaglio: ogni 45 secondi (timeline, grafici, aggregati pesanti)
      setInterval(aggiornaDatiDettaglio, 45000);

      document.getElementById("refreshBtn")?.addEventListener("click", aggiornaDati);
      document.getElementById("addProjectForm")?.addEventListener("submit", aggiungiProgetto);
      document.getElementById("sentinelForm")?.addEventListener("submit", eseguiSentinella);
      document.getElementById("riavviaBtn")?.addEventListener("click", riavviaSistema);

      // Listener per aggiornare la lista dei comandi quando cambia il progetto
      document.getElementById("sentinelProj")?.addEventListener("change", aggiornaComandiSelect);

      // Replay di un commit reale
      caricaCommit();
      document.getElementById("realProjSelect")?.addEventListener("change", caricaCommit);
      document.getElementById("commitSelect")?.addEventListener("change", aggiornaCommitCardSelezionato);
      document.getElementById("customCommitTrigger")?.addEventListener("click", toggleCustomCommitDropdown);
      document.addEventListener("click", (e) => {
        const picker = document.getElementById("customCommitPicker");
        if (picker && !picker.contains(e.target)) {
          chiudiCustomCommitDropdown();
        }
      });
      document.getElementById("replayCommitBtn")?.addEventListener("click", avviaReplayCommit);

      // Bacheca multi-agente
      document.getElementById("bachecaProjSelect")?.addEventListener("change", () => {
        document.getElementById("bachecaDettaglio").innerHTML = "";
        bachecaFeedIdsMostrati = new Set();
        document.getElementById("bachecaFeed").innerHTML = `<div class="handoff-msg system">${t("feed_proj_changed")}</div>`;
        caricaBacheca();
        if (bachecaFeedAttivo) caricaBachecaFeed();
      });
      document.getElementById("bachecaFeedToggle")?.addEventListener("click", () => {
        bachecaFeedAttivo = !bachecaFeedAttivo;
        const btn = document.getElementById("bachecaFeedToggle");
        if (bachecaFeedAttivo) {
          btn.textContent = t("btn_feed_pause");
          btn.style.background = "rgba(244,63,94,0.15)";
          btn.style.borderColor = "rgba(244,63,94,0.4)";
          btn.style.color = "#f87171";
          document.getElementById("bachecaFeed").innerHTML = `<div class="handoff-msg system">${t("feed_started")}</div>`;
          bachecaFeedIdsMostrati = new Set();
          caricaBachecaFeed();
        } else {
          btn.textContent = t("btn_feed_start");
          btn.style.background = "rgba(16,185,129,0.15)";
          btn.style.borderColor = "rgba(16,185,129,0.4)";
          btn.style.color = "#34d399";
        }
      });
      document.getElementById("profiloSelect")?.addEventListener("change", cambiaProfiloOperativo);

      // Paginazione della timeline eventi
      document.getElementById("timelinePrevBtn")?.addEventListener("click", () => {
        if (paginaTimelineCorrente > 1) {
          paginaTimelineCorrente--;
          aggiornaDatiDettaglio();
        }
      });
      document.getElementById("timelineNextBtn")?.addEventListener("click", () => {
        paginaTimelineCorrente++;
        aggiornaDatiDettaglio();
      });

      // IntersectionObserver per refresh on-demand quando la timeline entra in viewport
      const timelineWidget = document.getElementById("timelineWidget");
      if (timelineWidget && "IntersectionObserver" in window) {
        const observer = new IntersectionObserver((entries) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              aggiornaDatiDettaglio();
            }
          });
        }, { threshold: 0.1 });
        observer.observe(timelineWidget);
      }
    });

    async function riavviaSistema() {
      if (!confirm(t("restart_confirm"))) {
        return;
      }
      const btn = document.getElementById("riavviaBtn");
      if (btn) {
        btn.disabled = true;
        btn.textContent = t("restart_in_progress");
      }
      showFeedback(t("restart_requested"), "success");

      let idRiavvio;
      const controller = new AbortController();
      const timeoutRichiesta = setTimeout(() => controller.abort(), 5000);
      try {
        const risposta = await fetch("/api/sistema/riavvia", { method: "POST", signal: controller.signal });
        if (!risposta.ok) throw new Error("riavvio non accettato");
        idRiavvio = (await risposta.json()).id_riavvio;
        if (!idRiavvio) throw new Error("id riavvio assente");
      } catch (err) {
        if (btn) {
          btn.disabled = false;
          btn.textContent = t("btn_restart");
        }
        showFeedback(t("restart_request_failed"), "error");
        return;
      } finally {
        clearTimeout(timeoutRichiesta);
      }

      const attendiRiavvio = async () => {
        for (let tentativo = 0; tentativo < 30; tentativo++) {
          await new Promise(r => setTimeout(r, 1000));
          try {
            const res = await fetch("/api/stato", { cache: "no-store" });
            const stato = res.ok ? await res.json() : null;
            if (stato?.riavvio_dashboard?.id === idRiavvio && stato.riavvio_dashboard.stato === "pronto") {
              window.location.reload();
              return;
            }
          } catch (err) {
            // riprova
          }
        }
        if (btn) {
          btn.disabled = false;
          btn.textContent = t("btn_restart");
        }
        showFeedback(t("restart_timeout"), "error");
      };
      attendiRiavvio();
    }

    function showFeedback(text, type = "success") {
      const banner = document.getElementById("feedbackBanner");
      if (!banner) return;
      banner.textContent = text;
      banner.className = "banner " + type;
      banner.style.display = "block";
      setTimeout(() => {
        banner.style.display = "none";
      }, 5000);
    }

    function aggiornaAvvisoCodice(codice) {
      const banner = document.getElementById("codiceStaleBanner");
      if (!banner) return;
      if (!codice || codice.stato === "allineato") {
        banner.style.display = "none";
        banner.replaceChildren();
        return;
      }
      const testo = codice.stato === "modificato"
        ? t("code_stale", { files: (codice.file_modificati || []).join(", ") || "?" })
        : t("code_unverifiable");
      banner.replaceChildren(document.createTextNode(testo + " "));
      if (codice.stato === "modificato") {
        const pulsante = document.createElement("button");
        pulsante.type = "button";
        pulsante.className = "btn-riavvia";
        pulsante.textContent = t("btn_restart_now");
        pulsante.addEventListener("click", riavviaSistema);
        banner.appendChild(pulsante);
      }
      banner.style.display = "block";
    }

    function sincronizzaSelectProgetti(selectEl, listaProgetti) {
      if (!selectEl || !listaProgetti) return;
      const opzioniEsistenti = Array.from(selectEl.options).map(o => ({ value: o.value, text: o.textContent }));
      const opzioniNuove = listaProgetti.map(p => ({ value: p.id, text: p.nome }));
      
      const sonoUguali = opzioniEsistenti.length === opzioniNuove.length &&
        opzioniEsistenti.every((o, i) => o.value === opzioniNuove[i].value && o.text === opzioniNuove[i].text);
        
      if (sonoUguali) return;

      const prevSelected = selectEl.value;
      selectEl.innerHTML = "";
      opzioniNuove.forEach(opt => {
        const el = document.createElement("option");
        el.value = opt.value;
        el.textContent = opt.text;
        selectEl.appendChild(el);
      });
      if (prevSelected && opzioniNuove.some(o => o.value === prevSelected)) {
        selectEl.value = prevSelected;
      }
    }

    async function aggiornaDatiLive() {
      if (document.hidden) return;
      const bachecaSelect = document.getElementById("bachecaProjSelect");
      const progettoId = (bachecaSelect && bachecaSelect.value) || "orchestratore";

      try {
        const res = await fetch(`/api/stato/live?progetto_id=${encodeURIComponent(progettoId)}`);
        if (!res.ok) return;
        const data = await res.json();

        aggiornaAvvisoCodice(data.codice_dashboard);

        // 1. Stats globali
        const elProj = document.getElementById("valProjects");
        if (elProj && data.globali) elProj.textContent = data.globali.progetti_totali;
        const elEv = document.getElementById("valEvents");
        if (elEv && data.globali) elEv.textContent = data.globali.eventi_totali;
        const elLat = document.getElementById("valLatency");
        if (elLat && data.globali) elLat.textContent = `${(data.globali.latenza_totale || 0).toLocaleString()} ms`;

        // 2. Sincronizzazione select progetti senza rebuild distruttivo
        if (data.progetti_sommario) {
          sincronizzaSelectProgetti(document.getElementById("sentinelProj"), data.progetti_sommario);
          sincronizzaSelectProgetti(document.getElementById("realProjSelect"), data.progetti_sommario);
          sincronizzaSelectProgetti(document.getElementById("bachecaProjSelect"), data.progetti_sommario);
        }

        // 3. Bacheca live
        if (data.bacheca_live) {
          renderizzaPendingBacheca(data.bacheca_live.pending_per_agente, null);
          renderizzaProfiloOperativo(data.bacheca_live);

          const occupatiBox = document.getElementById("bachecaOccupati");
          if (occupatiBox) {
            const occupati = data.bacheca_live.file_occupati || {};
            const fileOccupati = Object.keys(occupati);
            occupatiBox.innerHTML = fileOccupati.length === 0
              ? t("none_locked")
              : fileOccupati.map(f => {
                  const info = occupati[f];
                  const scadenza = info.scadenza ? formattaOraIt(info.scadenza) : t("lease_no_expiry");
                  return `<div>- <b>${escapeHtml(f)}</b>: <span class="tag-agent ${escapeHtml(info.agente)}">${escapeHtml(info.agente)}</span> (${t("lease_expires")} ${scadenza})</div>`;
                }).join("");
          }
        }
      } catch (err) {
        // Fallback silenzioso per poll live
      }
    }

    async function aggiornaDatiDettaglio() {
      try {
        const res = await fetch(`/api/stato?pagina=${paginaTimelineCorrente}&per_pagina=50`);
        if (!res.ok) throw new Error(t("loading_data_error"));
        const data = await res.json();
        aggiornaAvvisoCodice(data.codice_dashboard);

        // Stats globali
        const elProj = document.getElementById("valProjects");
        if (elProj && data.globali) elProj.textContent = data.globali.progetti_totali;
        const elEv = document.getElementById("valEvents");
        if (elEv && data.globali) elEv.textContent = data.globali.eventi_totali;
        const elLat = document.getElementById("valLatency");
        if (elLat && data.globali) elLat.textContent = `${(data.globali.latenza_totale || 0).toLocaleString()} ms`;

        progettiCorrenti = data.progetti || [];

        // Sincronizza select
        sincronizzaSelectProgetti(document.getElementById("sentinelProj"), data.progetti);
        sincronizzaSelectProgetti(document.getElementById("realProjSelect"), data.progetti);
        sincronizzaSelectProgetti(document.getElementById("bachecaProjSelect"), data.progetti);

        aggiornaComandiSelect();

        // Progetti list
        const pList = document.getElementById("projectsList");
        if (pList) {
          pList.innerHTML = "";
          if (!data.progetti || data.progetti.length === 0) {
            pList.innerHTML = `<div style="text-align: center; color: var(--text-muted);">${t("projects_empty")}</div>`;
          } else {
            data.progetti.forEach(p => {
              const pStat = (data.progetto_stats && data.progetto_stats[p.id]) || { esecuzioni: 0, latenza: 0, rework: 0 };
              const card = document.createElement("div");
              card.className = "project-card";
              const avviso = pStat.errore
                ? `<div class="project-error">${t("project_error")}${escapeHtml(pStat.errore)}</div>`
                : "";
              card.innerHTML = `
                <div class="project-head">
                  <span class="project-name">${escapeHtml(p.nome)}</span>
                  <span class="badge">id: ${escapeHtml(p.id)}</span>
                </div>
                <div class="project-path">${escapeHtml(p.percorso)}</div>
                <div class="project-meta-row">
                  <span>${t("project_active_modules")}<b>${pStat.esecuzioni}</b></span>
                  <span>${t("project_llm_time")}<b>${(pStat.latenza || 0).toLocaleString()} ms</b></span>
                  <span>${t("project_rework")}<b class="badge rework">${pStat.rework}</b></span>
                </div>
                ${avviso}
              `;
              pList.appendChild(card);
            });
          }
        }

        // Timeline
        const tBody = document.getElementById("timelineBody");
        if (tBody) {
          tBody.innerHTML = "";
          if (!data.eventi || data.eventi.length === 0) {
            tBody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">${t("timeline_empty")}</td></tr>`;
          } else {
            data.eventi.forEach(ev => {
              const tr = document.createElement("tr");
              tr.innerHTML = `
                <td>${escapeHtml(ev.timestamp) || '—'}</td>
                <td><span class="tag-project">${escapeHtml(ev._progetto_nome) || '—'}</span></td>
                <td>${escapeHtml(ev.id_compito) || '—'}</td>
                <td><span class="tag-agent">${escapeHtml(ev.agente) || '—'}</span></td>
                <td>${escapeHtml(ev.tipo_compito) || '—'}</td>
                <td><span class="status-badge ${escapeHtml(ev.stato)}">${escapeHtml(ev.stato) || '—'}</span></td>
                <td><span class="status-badge ${escapeHtml(ev.esito_gate)}">${escapeHtml(ev.esito_gate) || '—'}</span></td>
                <td><span class="status-badge ${escapeHtml(ev.verdetto_umano)}">${escapeHtml(ev.verdetto_umano) || '—'}</span></td>
                <td title="${escapeHtml(ev.note)}">${escapeHtml(ev.note) || '—'}</td>
              `;
              tBody.appendChild(tr);
            });
          }
        }

        const paginazione = data.paginazione || { pagina: 1, pagine_totali: 1, eventi_totali: (data.eventi ? data.eventi.length : 0) };
        paginaTimelineCorrente = paginazione.pagina;
        const elInfo = document.getElementById("timelinePageInfo");
        if (elInfo) {
          elInfo.textContent = t("timeline_page_info", { page: paginazione.pagina, pages: paginazione.pagine_totali, total: paginazione.eventi_totali });
        }
        const btnPrev = document.getElementById("timelinePrevBtn");
        if (btnPrev) btnPrev.disabled = paginazione.pagina <= 1;
        const btnNext = document.getElementById("timelineNextBtn");
        if (btnNext) btnNext.disabled = paginazione.pagina >= paginazione.pagine_totali;

        // Grafici
        renderizzaGrafici(data.agente_stats || {}, data.livello_stats || {});
        renderizzaAnelliLivello(data.livello_stats || {});

        // Bacheca
        caricaBacheca();
        if (bachecaFeedAttivo) caricaBachecaFeed();

      } catch (err) {
        showFeedback(`${t("loading_data_error")}${err.message}`, "error");
      }
    }

    async function aggiornaDati() {
      await aggiornaDatiLive();
      await aggiornaDatiDettaglio();
    }

    function aggiornaComandiSelect() {
      const projSelect = document.getElementById("sentinelProj");
      const cmdSelect = document.getElementById("sentinelCmd");
      if (!projSelect || !cmdSelect) return;
      const selectedProjId = projSelect.value;
      const prevSelectedCmd = cmdSelect.value;

      cmdSelect.innerHTML = "";

      const proj = progettiCorrenti.find(p => p.id === selectedProjId);
      if (!proj || !proj.comandi || proj.comandi.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = t("option_no_cmd");
        cmdSelect.appendChild(opt);
        return;
      }

      proj.comandi.forEach(cmd => {
        const opt = document.createElement("option");
        opt.value = cmd.nome;
        opt.textContent = cmd.descrizione || cmd.nome;
        cmdSelect.appendChild(opt);
      });

      if (prevSelectedCmd && proj.comandi.some(cmd => cmd.nome === prevSelectedCmd)) {
        cmdSelect.value = prevSelectedCmd;
      }
    }

    function renderizzaTempoLLMPerAgente(agenteStats) {
      const tbody = document.getElementById("latenzaPerAgenteBody");
      if (!tbody) return;
      const agenti = Object.keys(agenteStats).sort();
      if (agenti.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">${t("latency_no_data")}</td></tr>`;
        return;
      }
      tbody.innerHTML = "";
      agenti.forEach(agente => {
        const stat = agenteStats[agente];
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><span class="tag-agent ${escapeHtml(agente)}">${escapeHtml(agente.toUpperCase())}</span></td>
          <td>${(stat.latenza || 0).toLocaleString()} ms</td>
          <td>${stat.esecuzioni}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function renderizzaGrafici(agenteStats, livelloStats) {
      renderizzaTempoLLMPerAgente(agenteStats);

      const agenti = Object.keys(agenteStats).sort();
      const esecuzioni = agenti.map(a => agenteStats[a].esecuzioni);
      const rework = agenti.map(a => agenteStats[a].rework);

      // Chart 2: Esecuzioni e Rework per agente
      if (runsChartInstance) runsChartInstance.destroy();
      const elRuns = document.getElementById("runsChart");
      if (elRuns) {
        const ctxRuns = elRuns.getContext("2d");
        runsChartInstance = new Chart(ctxRuns, {
          type: 'bar',
          data: {
            labels: agenti,
            datasets: [
              {
                label: t("chart_runs_label"),
                data: esecuzioni,
                backgroundColor: 'rgba(59, 130, 246, 0.75)',
                borderColor: '#3b82f6',
                borderWidth: 1
              },
              {
                label: t("chart_rework_label"),
                data: rework,
                backgroundColor: 'rgba(244, 63, 94, 0.75)',
                borderColor: '#f43f5e',
                borderWidth: 1
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } },
              y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', stepSize: 1 } }
            },
            plugins: {
              legend: {
                labels: { color: '#f3f4f6', font: { family: 'Inter' } }
              }
            }
          }
        });
      }

      // Chart 3: quota di lavoro per agente
      const agentiLivello = Object.keys(livelloStats).sort();
      const datiDatabase = agentiLivello.map(a => livelloStats[a].database || 0);
      const datiBackend = agentiLivello.map(a => livelloStats[a].backend || 0);
      const datiFrontend = agentiLivello.map(a => livelloStats[a].frontend || 0);

      if (livelloChartInstance) livelloChartInstance.destroy();
      const elLivello = document.getElementById("livelloChart");
      if (elLivello) {
        const ctxLivello = elLivello.getContext("2d");
        livelloChartInstance = new Chart(ctxLivello, {
          type: 'bar',
          data: {
            labels: agentiLivello,
            datasets: [
              { label: t("chart_db_label"), data: datiDatabase, backgroundColor: '#3987e5', borderColor: '#3987e5', borderWidth: 1 },
              { label: t("chart_backend_label"), data: datiBackend, backgroundColor: '#c98500', borderColor: '#c98500', borderWidth: 1 },
              { label: t("chart_frontend_label"), data: datiFrontend, backgroundColor: '#d55181', borderColor: '#d55181', borderWidth: 1 }
            ]
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', stepSize: 1 } },
              y: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }
            },
            plugins: {
              legend: {
                labels: { color: '#f3f4f6', font: { family: 'Inter' } }
              },
              tooltip: {
                callbacks: {
                  label: function(context) {
                    return `${context.dataset.label}: ${context.parsed.x}`;
                  }
                }
              }
            }
          }
        });
      }
    }

    const COLORI_AGENTE = { umano: '#10b981', gemini: '#00f0ff', claude: '#ff6b00', codex: '#bd00ff', locale: '#94a3b8' };
    const ORDINE_AGENTI = ['umano', 'gemini', 'claude', 'codex', 'locale'];

    function renderizzaAnelliLivello(livelloStats) {
      const svg = document.getElementById("livelloRingsSvg");
      const legenda = document.getElementById("livelloRingsLegend");
      if (!svg || !legenda) return;
      svg.innerHTML = "";
      legenda.innerHTML = "";

      const ns = "http://www.w3.org/2000/svg";
      const CX = 100, CY = 100, SPESSORE = 18, GAP = 2;
      const ANELLI = [
        { livello: "database", raggio: 30, etichettaKey: "ring_db" },
        { livello: "backend", raggio: 55, etichettaKey: "ring_backend" },
        { livello: "frontend", raggio: 80, etichettaKey: "ring_frontend" }
      ];

      ANELLI.forEach(anello => {
        const circonferenza = 2 * Math.PI * anello.raggio;

        const traccia = document.createElementNS(ns, "circle");
        traccia.setAttribute("cx", CX);
        traccia.setAttribute("cy", CY);
        traccia.setAttribute("r", anello.raggio);
        traccia.setAttribute("fill", "none");
        traccia.setAttribute("stroke", "rgba(255,255,255,0.05)");
        traccia.setAttribute("stroke-width", SPESSORE);
        svg.appendChild(traccia);

        const totale = ORDINE_AGENTI.reduce((s, a) => s + ((livelloStats[a] && livelloStats[a][anello.livello]) || 0), 0);
        if (totale === 0) return;

        let offsetAccumulato = 0;
        ORDINE_AGENTI.forEach(agente => {
          const valore = (livelloStats[agente] && livelloStats[agente][anello.livello]) || 0;
          if (valore === 0) return;
          const lunghezzaArco = (valore / totale) * circonferenza;

          const segmento = document.createElementNS(ns, "circle");
          segmento.setAttribute("cx", CX);
          segmento.setAttribute("cy", CY);
          segmento.setAttribute("r", anello.raggio);
          segmento.setAttribute("fill", "none");
          segmento.setAttribute("stroke", COLORI_AGENTE[agente] || "#94a3b8");
          segmento.setAttribute("stroke-width", SPESSORE);
          segmento.setAttribute("stroke-dasharray", `${Math.max(lunghezzaArco - GAP, 0)} ${circonferenza - lunghezzaArco + GAP}`);
          segmento.setAttribute("stroke-dashoffset", String(-offsetAccumulato));
          segmento.setAttribute("transform", `rotate(-90 ${CX} ${CY})`);

          const titolo = document.createElementNS(ns, "title");
          titolo.textContent = `${agente}: ${valore} (${t(anello.etichettaKey)})`;
          segmento.appendChild(titolo);
          svg.appendChild(segmento);
          offsetAccumulato += lunghezzaArco;
        });
      });

      ORDINE_AGENTI.forEach(agente => {
        const riga = document.createElement("div");
        riga.style.display = "flex";
        riga.style.alignItems = "center";
        riga.style.gap = "0.4rem";
        const labelAgente = (agente === "umano" ? t("node_umano") : (agente === "locale" ? t("node_locale") : agente));
        riga.innerHTML = `<span style="width:10px; height:10px; border-radius:50%; background:${COLORI_AGENTE[agente]}; display:inline-block;"></span><span style="color:var(--text-muted);">${escapeHtml(labelAgente)}</span>`;
        legenda.appendChild(riga);
      });
    }

    async function aggiungiProgetto(e) {
      e.preventDefault();
      const nome = document.getElementById("projNome").value;
      const percorso = document.getElementById("projPercorso").value;

      try {
        const res = await fetch("/api/progetti", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nome, percorso })
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Errore");
        }
        showFeedback(t("project_added_success", { nome: nome }), "success");
        document.getElementById("addProjectForm").reset();
        aggiornaDati();
      } catch (err) {
        showFeedback(err.message, "error");
      }
    }

    async function eseguiSentinella(e) {
      e.preventDefault();
      const progetto_id = document.getElementById("sentinelProj").value;
      const comando = document.getElementById("sentinelCmd").value;
      const consoleBox = document.getElementById("consoleOutput");

      consoleBox.style.display = "block";
      consoleBox.textContent = t("sentinel_starting", { cmd: comando, proj: progetto_id });

      try {
        const res = await fetch("/api/sentinella", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ progetto_id, comando })
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Esecuzione fallita");
        }

        const esito = data.status;
        const gateInfo = data.dati.esito || data.dati.evento?.esito_gate || "non_eseguito";
        const returncode = data.returncode;
        const output = data.dati.output || "";
        const triage = data.dati.triage;
        const triageInfo = triage
          ? `\n>> ${t("sentinel_local_triage")}${triage.stato || "n/d"} — ${triage.note || ""} (${triage.metadati?.metodo || "n/d"})\n`
          : "";

        consoleBox.textContent += `\n${t("sentinel_outcome")}${esito.toUpperCase()} (${t("sentinel_return_code")}${returncode})${triageInfo}\nOutput:\n${output}`;
        
        showFeedback(t("sentinel_finished", { cmd: comando, gate: gateInfo.toUpperCase() }), esito === "success" ? "success" : "error");
        aggiornaDati();
      } catch (err) {
        consoleBox.textContent += `\n${t("sentinel_exec_error")}${err.message}`;
        showFeedback(err.message, "error");
      }
    }

    let simTimer = null;

    function fermaSimulazione() {
      if (simTimer) {
        clearInterval(simTimer);
        simTimer = null;
      }
      const elStart = document.getElementById("startSimBtn");
      if (elStart) elStart.style.display = "inline-block";
      const elStop = document.getElementById("stopSimBtn");
      if (elStop) elStop.style.display = "none";
      const elCard = document.getElementById("commitCard");
      if (elCard) elCard.style.display = "none";

      document.querySelectorAll(".agent-node").forEach(node => {
        node.setAttribute("class", "agent-node");
      });
      document.querySelectorAll(".handoff-line").forEach(line => {
        line.setAttribute("class", "handoff-line");
      });
    }

    function renderizzaCustomCommitPicker() {
      const dropdown = document.getElementById("customCommitDropdown");
      const commitSelect = document.getElementById("commitSelect");
      if (!dropdown || !commitSelect) return;
      dropdown.innerHTML = "";

      if (commitCorrenti.length === 0) {
        dropdown.innerHTML = `<div style="padding:0.8rem; color:var(--text-muted); text-align:center; font-size:0.8rem;">${t("commit_none_avail")}</div>`;
        return;
      }

      const hashSelezionato = commitSelect.value;

      commitCorrenti.forEach(c => {
        const item = document.createElement("div");
        item.className = "custom-commit-item" + (c.hash === hashSelezionato ? " selected" : "");
        item.setAttribute("data-hash", c.hash);
        const n = Number(c.interazioni || 0);
        const labelInt = n === 1 ? t("interaction_short_singular") : t("interaction_short_plural", { count: n });
        const dataStr = c.data ? c.data.slice(0, 16).replace("T", " ") : "";
        item.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.3rem;">
            <div style="display:flex; gap:0.5rem; align-items:center;">
              <span class="tag-badge" style="background:rgba(139,92,246,0.18); color:#c4b5fd; font-size:0.72rem; padding:0.12rem 0.45rem; border-radius:4px; font-weight:600; border:1px solid rgba(139,92,246,0.35);">
                ⚡ ${labelInt}
              </span>
              <span style="font-family:'Fira Code',monospace; font-size:0.75rem; color:#a78bfa; font-weight:600;">${c.hash.slice(0, 7)}</span>
            </div>
            <span style="font-size:0.72rem; color:var(--text-muted);">${escapeHtml(dataStr)}</span>
          </div>
          <div style="font-size:0.86rem; font-weight:600; color:var(--text-main); line-height:1.4; white-space:normal; word-break:break-word;">
            ${escapeHtml(c.messaggio)}
          </div>
        `;
        item.addEventListener("click", () => {
          commitSelect.value = c.hash;
          commitSelect.dispatchEvent(new Event("change"));
          chiudiCustomCommitDropdown();
        });
        dropdown.appendChild(item);
      });
    }

    function aggiornaCommitCardSelezionato() {
      const commitSelect = document.getElementById("commitSelect");
      const hash = commitSelect ? commitSelect.value : "";
      if (!hash) {
        const elCard = document.getElementById("commitCard");
        if (elCard) elCard.style.display = "none";
        const triggerTitle = document.getElementById("triggerTitle");
        if (triggerTitle) triggerTitle.textContent = t("commit_select_placeholder");
        return;
      }
      const selectedCommit = commitCorrenti.find(c => c.hash === hash);
      if (selectedCommit) {
        document.getElementById("commitHashVal").textContent = selectedCommit.hash.slice(0, 7);
        document.getElementById("commitDateVal").textContent = formattaOraIt(selectedCommit.data);
        document.getElementById("commitMsgVal").textContent = selectedCommit.messaggio;
        document.getElementById("commitAuthorVal").textContent = `${t("commit_author_label")}${selectedCommit.autore}`;
        const numInterazioni = Number(selectedCommit.interazioni || 0);
        const labelInterazioni = numInterazioni === 1 ? t("interaction_singular") : t("interaction_plural", { count: numInterazioni });
        const badgeEl = document.getElementById("commitInterazioniBadge");
        if (badgeEl) {
          badgeEl.textContent = `⚡ ${labelInterazioni}`;
        }
        document.getElementById("commitCard").style.display = "block";

        const tBadge = document.getElementById("triggerBadge");
        const tDate = document.getElementById("triggerDate");
        const tHash = document.getElementById("triggerHash");
        const tTitle = document.getElementById("triggerTitle");
        if (tBadge) tBadge.textContent = `⚡ ${labelInterazioni}`;
        if (tDate) tDate.textContent = selectedCommit.data ? selectedCommit.data.slice(0, 16).replace("T", " ") : "";
        if (tHash) tHash.textContent = selectedCommit.hash.slice(0, 7);
        if (tTitle) tTitle.textContent = selectedCommit.messaggio;

        renderizzaCustomCommitPicker();
      }
    }

    function toggleCustomCommitDropdown() {
      const dropdown = document.getElementById("customCommitDropdown");
      if (dropdown) dropdown.classList.toggle("open");
    }

    function chiudiCustomCommitDropdown() {
      const dropdown = document.getElementById("customCommitDropdown");
      if (dropdown) dropdown.classList.remove("open");
    }

    async function caricaCommit() {
      const elProj = document.getElementById("realProjSelect");
      const progetto_id = (elProj && elProj.value) || "orchestratore";
      const commitSelect = document.getElementById("commitSelect");
      if (!commitSelect) return;
      try {
        const res = await fetch(`/api/commit/lista?progetto_id=${encodeURIComponent(progetto_id)}&limite=20`);
        if (!res.ok) throw new Error("risposta non valida");
        const data = await res.json();
        commitSelect.innerHTML = "";
        commitCorrenti = data.commit || [];
        if (commitCorrenti.length === 0) {
          commitSelect.innerHTML = `<option value="">${t("commit_none_avail")}</option>`;
          document.getElementById("commitCard").style.display = "none";
          renderizzaCustomCommitPicker();
          return;
        }
        commitCorrenti.forEach(c => {
          const opt = document.createElement("option");
          opt.value = c.hash;
          const numInterazioni = Number(c.interazioni || 0);
          const labelInterazioni = numInterazioni === 1 ? t("interaction_short_singular") : t("interaction_short_plural", { count: numInterazioni });
          opt.textContent = `[${labelInterazioni}] ${c.data.slice(0, 16)} — ${c.messaggio}`;
          opt.title = `${c.messaggio} (${labelInterazioni})`;
          commitSelect.appendChild(opt);
        });
        aggiornaCommitCardSelezionato();
      } catch (err) {
        commitSelect.innerHTML = `<option value="">${t("commit_load_fail")}</option>`;
        commitCorrenti = [];
        const elCard = document.getElementById("commitCard");
        if (elCard) elCard.style.display = "none";
        renderizzaCustomCommitPicker();
      }
    }

    function promptRisveglioAgente(agenteId) {
      return `Leggi i messaggi pendenti in bacheca per ${agenteId} ed esegui quanto richiesto: python bacheca.py prossimo --agente ${agenteId}`;
    }

    function uriRisveglioAgente(agenteId, claudeSessionId) {
      if (agenteId === "claude") {
        const prompt = encodeURIComponent("python bacheca.py prossimo --agente claude");
        const sessParam = claudeSessionId ? `&session=${encodeURIComponent(claudeSessionId)}` : "";
        return `antigravity-ide://anthropic.claude-code/open?prompt=${prompt}${sessParam}`;
      }
      if (agenteId === "codex") {
        return "antigravity-ide://openai.chatgpt/";
      }
      if (agenteId === "gemini") {
        return "antigravity-ide://";
      }
      return "";
    }

    async function apriRisveglioAgente(uri, prompt, agenteId) {
      try {
        await copiaTestoNegliAppunti(prompt);
        showFeedback(t("wake_prompt_copied", { agente: agenteId }), "success");
      } catch (err) {
        showFeedback(t("wake_copy_fail", { agente: agenteId }), "error");
      }
      if (uri) {
        window.location.href = uri;
      }
    }

    function badgeGaranziaHtml(tipo) {
      if (tipo === "enforced") {
        return `<span class="tag-badge" style="background:rgba(16,185,129,0.2); color:#34d399; font-weight:700; font-size:0.72rem; padding:0.1rem 0.4rem; border-radius:4px; border:1px solid rgba(16,185,129,0.4);">🛡️ Enforced</span>`;
      }
      if (tipo === "prompt_only") {
        return `<span class="tag-badge" style="background:rgba(245,158,11,0.2); color:#fbbf24; font-weight:700; font-size:0.72rem; padding:0.1rem 0.4rem; border-radius:4px; border:1px solid rgba(245,158,11,0.4);">⚠️ Prompt only</span>`;
      }
      return `<span class="tag-badge" style="background:rgba(148,163,184,0.15); color:#94a3b8; font-weight:600; font-size:0.72rem; padding:0.1rem 0.4rem; border-radius:4px; border:1px solid rgba(148,163,184,0.3);">⛔ Non disp.</span>`;
    }

    function renderizzaProfiloOperativo(data) {
      if (!data) return;
      const dto = data.profilo || {};
      const nomeProfilo = dto.profilo || "standard";
      const select = document.getElementById("profiloSelect");
      if (select && select.value !== nomeProfilo) {
        select.value = nomeProfilo;
      }

      const badge = document.getElementById("profiloDispatchBadge");
      if (badge) {
        // Il backend e' l'unica fonte di verita' sui profili abilitati: non
        // duplicare qui la policy, altrimenti profili nuovi restano validi ma
        // vengono presentati erroneamente come indisponibili dalla dashboard.
        const dispatchAbilitato = data.postino_headless_attivo === true;
        if (dispatchAbilitato) {
          badge.textContent = `🟢 DISPATCH ATTIVO (${nomeProfilo})`;
          badge.style.background = "rgba(16,185,129,0.15)";
          badge.style.borderColor = "rgba(16,185,129,0.4)";
          badge.style.color = "#34d399";
        } else {
          badge.textContent = nomeProfilo === "standard" ? "🔴 DISPATCH DISATTIVATO (standard)" : `⛔ NON DISPONIBILE (${nomeProfilo})`;
          badge.style.background = "rgba(244,63,94,0.15)";
          badge.style.borderColor = "rgba(244,63,94,0.4)";
          badge.style.color = "#fb7185";
        }
      }

      const descBox = document.getElementById("profiloDescrizione");
      if (descBox) {
        descBox.textContent = data.descrizione_profilo || data.descrizione || "Nessuna descrizione disponibile.";
      }

      const garanzie = data.garanzie_per_agente || {};
      const gClaude = document.getElementById("garanziaClaude");
      if (gClaude) gClaude.innerHTML = badgeGaranziaHtml(garanzie.claude || "enforced");

      const gCodex = document.getElementById("garanziaCodex");
      if (gCodex) gCodex.innerHTML = badgeGaranziaHtml(garanzie.codex || "prompt_only");

      const gGemini = document.getElementById("garanziaGemini");
      if (gGemini) gGemini.innerHTML = badgeGaranziaHtml(garanzie.gemini || "prompt_only");
    }

    async function cambiaProfiloOperativo() {
      const projSelect = document.getElementById("bachecaProjSelect");
      const progetto_id = (projSelect && projSelect.value) || "orchestratore";
      const profSelect = document.getElementById("profiloSelect");
      const nuovoProfilo = profSelect ? profSelect.value : "standard";

      try {
        const res = await fetch("/api/bacheca/postino/profilo", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ progetto_id: progetto_id, profilo: nuovoProfilo })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Errore cambio profilo");
        }
        const data = await res.json();
        renderizzaProfiloOperativo(data);
        showFeedback(`Profilo impostato: ${nuovoProfilo}`, "success");
      } catch (err) {
        showFeedback(`Errore impostazione profilo: ${err.message}`, "error");
        caricaBacheca();
      }
    }

    async function eseguiRisvegliBacheca(progettoId) {
      try {
        const res = await fetch(`/api/bacheca/risvegli?progetto_id=${encodeURIComponent(progettoId)}`, {
          method: "POST"
        });
        if (!res.ok) throw new Error("risposta non valida");
        const data = await res.json();
        const risvegli = data.risvegli || [];
        if (risvegli.length > 0) {
          const agenti = risvegli.map(r => r.agente).join(", ");
          showFeedback(`${t("auto_wake_sent")}${agenti}`, "success");
        }
      } catch (err) {
        console.warn("Risveglio automatico non riuscito:", err);
      }
    }

    function renderizzaPendingBacheca(pendingPerAgente, claudeSessionId) {
      const box = document.getElementById("bachecaPendingAgenti");
      if (!box) return;
      const pending = pendingPerAgente || {};
      box.innerHTML = "";
      AGENTI_BACHECA_DASHBOARD.forEach(agente => {
        const count = Number(pending[agente.id] || 0);
        const comando = `python bacheca.py prossimo --agente ${agente.id}`;
        const card = document.createElement("div");
        card.className = "bacheca-pending-card";
        let risvegliaBtnHtml = "";
        if (count > 0) {
          const uri = uriRisveglioAgente(agente.id, claudeSessionId);
          const prompt = promptRisveglioAgente(agente.id);
          risvegliaBtnHtml = `<button type="button" class="bacheca-risveglia-btn" data-uri="${escapeHtml(uri)}" data-prompt="${escapeHtml(prompt)}" data-agente="${escapeHtml(agente.id)}" title="${t("btn_wake_title")}">${t("btn_wake")}</button>`;
        }
        card.innerHTML = `
          <div class="bacheca-pending-main">
            <span class="bacheca-pending-count ${count > 0 ? "has-pending" : ""}">${count}</span>
            <div>
              <div><span class="tag-agent ${escapeHtml(agente.id)}">${escapeHtml(agente.label)}</span></div>
              <div style="font-size:0.72rem; color:var(--text-muted); margin-top:0.15rem;">${escapeHtml(t(agente.modoKey))}</div>
            </div>
          </div>
          <div style="display: flex; align-items: center;">
            ${risvegliaBtnHtml}
            <button type="button" class="bacheca-copy-btn" title="${escapeHtml(comando)}">${t("btn_copy_cmd")}</button>
          </div>
        `;
        if (count > 0) {
          card.querySelector(".bacheca-risveglia-btn").addEventListener("click", (e) => {
            const btn = e.currentTarget;
            const uri = btn.getAttribute("data-uri");
            const prompt = btn.getAttribute("data-prompt");
            const agenteId = btn.getAttribute("data-agente");
            apriRisveglioAgente(uri, prompt, agenteId);
          });
        }
        card.querySelector(".bacheca-copy-btn").addEventListener("click", async () => {
          try {
            await copiaTestoNegliAppunti(comando);
            showFeedback(`${t("cmd_copied")}${comando}`, "success");
          } catch (err) {
            showFeedback(`${t("cmd_copy_fail")}${comando}`, "error");
          }
        });
        box.appendChild(card);
      });
    }

    function renderizzaPraticheSospese(pratiche) {
      const box = document.getElementById("bachecaPraticheSospese");
      if (!box) return;
      if (!pratiche || pratiche.length === 0) {
        box.innerHTML = `<div style="color:var(--text-muted); font-size:0.85rem; padding:0.5rem 0;">${t("no_suspended_tasks")}</div>`;
        return;
      }
      box.innerHTML = "";
      pratiche.forEach(p => {
        const card = document.createElement("div");
        card.className = "pratica-card";

        let azioniHtml = "";
        if (p.azioni_per_esito && Object.keys(p.azioni_per_esito).length > 0) {
          azioniHtml = `<div class="pratica-azioni">
            <div style="font-size:0.73rem; color:var(--text-muted); margin-bottom:0.3rem; font-weight:600; text-transform:uppercase;">${t("actions_expected_by_outcome")}</div>`;
          for (const [esito, azione] of Object.entries(p.azioni_per_esito)) {
            let cls = "esito-modifiche";
            if (esito === "approvato") cls = "esito-approvato";
            if (esito === "respinto") cls = "esito-respinto";
            azioniHtml += `<div class="pratica-azione-item">
              <span class="pratica-azione-esito ${cls}">${escapeHtml(esito)}</span>
              <span>${escapeHtml(azione)}</span>
            </div>`;
          }
          azioniHtml += `</div>`;
        }

        let contestoHtml = "";
        if (p.contesto_minimo && p.contesto_minimo.comandi_consentiti && p.contesto_minimo.comandi_consentiti.length > 0) {
          contestoHtml = `<div style="margin-top:0.4rem; font-size:0.75rem; color:var(--text-muted);">
            <b>Comandi:</b> <code>${escapeHtml(p.contesto_minimo.comandi_consentiti.join(", "))}</code>
          </div>`;
        }

        card.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.4rem;">
            <div>
              <span style="font-family:monospace; font-size:0.82rem; color:#93c5fd; font-weight:600;">[Thread ${escapeHtml(p.thread_id.slice(0,8))}]</span>
              <span class="tag-agent ${escapeHtml(p.mittente)}" style="margin-left:0.4rem;">${escapeHtml(p.mittente)}</span>
            </div>
            <span class="pratica-badge-attende">${t("badge_awaits")}${escapeHtml(p.attende || 'umano')}</span>
          </div>
          <div style="font-weight:600; font-size:0.95rem; color:var(--text-main); margin-bottom:0.4rem;">
            🎯 ${escapeHtml(p.oggetto_atteso || 'Verdetto sul checkpoint')}
          </div>
          ${azioniHtml}
          ${contestoHtml}
          <div style="margin-top:0.5rem; font-size:0.75rem; color:var(--text-muted); display:flex; justify-content:space-between; align-items:center;">
            <span>${t("label_human_verdict")}<b>${escapeHtml(p.verdetto_umano || 'non_revisionato')}</b></span>
            <span>${p.timestamp ? formattaOraIt(p.timestamp, true) : ''}</span>
          </div>
        `;
        box.appendChild(card);
      });
    }

    function renderizzaWorkflowStepper(faseCorrente, flussoDichiarato, statoFlusso) {
      if (statoFlusso && (statoFlusso.stato === "incoerente" || statoFlusso.stato === "invalido")) {
        const diag = (statoFlusso.diagnostica && statoFlusso.diagnostica.length > 0)
          ? statoFlusso.diagnostica.join("; ")
          : statoFlusso.stato;
        const cls = statoFlusso.stato === "invalido" ? "invalido" : "incoerente";
        return `<div class="workflow-stepper" title="${escapeHtml(diag)}"><span class="stepper-step ${cls}">⚠ ${escapeHtml(statoFlusso.stato)}: ${escapeHtml(diag)}</span></div>`;
      }

      let passi = [];
      if (flussoDichiarato && Array.isArray(flussoDichiarato.passi) && flussoDichiarato.passi.length > 0) {
        passi = flussoDichiarato.passi.map((p, idx) => {
          let label = p.id;
          if (p.id === "approvazione_umana") label = (linguaCorrente === "it" ? "Umano" : "Human");
          else if (p.id === "azione_irreversibile") label = (linguaCorrente === "it" ? "Azione" : "Action");
          else label = p.id.charAt(0).toUpperCase() + p.id.slice(1);
          return {
            id: p.id,
            label: `${idx + 1}. ${label}`
          };
        });
      } else {
        passi = [
          { id: "compito", label: t("step_task") },
          { id: "gate", label: t("step_gate") },
          { id: "triage", label: t("step_triage") },
          { id: "registrazione", label: t("step_log") },
          { id: "approvazione_umana", label: t("step_human") },
          { id: "azione_irreversibile", label: t("step_action") },
          { id: "chiusura", label: t("step_close") }
        ];
      }

      let trovataAttiva = false;
      return `<div class="workflow-stepper">` + passi.map((p, idx) => {
        let cls = "";
        if (p.id === faseCorrente) {
          cls = "active";
          trovataAttiva = true;
        } else if (!trovataAttiva && faseCorrente !== "compito") {
          cls = "completed";
        }
        const arrow = idx < passi.length - 1 ? `<span class="stepper-arrow">›</span>` : "";
        return `<span class="stepper-step ${cls}" title="${escapeHtml(p.id)}">${escapeHtml(p.label)}</span>${arrow}`;
      }).join("") + `</div>`;
    }

    async function caricaBacheca() {
      const select = document.getElementById("bachecaProjSelect");
      const progetto_id = (select && select.value) || "orchestratore";
      const corpo = document.getElementById("bachecaBody");
      const banner = document.getElementById("bachecaBanner");
      const occupatiBox = document.getElementById("bachecaOccupati");
      if (!corpo) return;
      try {
        const res = await fetch(`/api/bacheca?progetto_id=${encodeURIComponent(progetto_id)}`);
        if (!res.ok) throw new Error("risposta non valida");
        const data = await res.json();

        if (data.errore) {
          corpo.innerHTML = `<tr><td colspan="8" style="text-align:center; color:#f87171;">⚠ ${escapeHtml(data.errore)}</td></tr>`;
          if (banner) banner.innerHTML = "";
          if (occupatiBox) occupatiBox.innerHTML = t("none_locked");
          renderizzaPendingBacheca(data.pending_per_agente, data.claude_session_id);
          renderizzaPraticheSospese([]);
          return;
        }

        renderizzaPendingBacheca(data.pending_per_agente, data.claude_session_id);
        renderizzaPraticheSospese(data.pratiche_sospese);
        renderizzaProfiloOperativo(data);
        await eseguiRisvegliBacheca(progetto_id);
        const thread = data.thread || [];
        const flussi = data.flussi || {};
        const flussoStandard = flussi.compito_standard || null;

        const conflitti = thread.filter(t => t.ultimo_tipo === "segnalazione_conflitto" && t.stato !== "chiuso" && t.stato !== "annullato");
        if (banner) {
          banner.innerHTML = conflitti.length > 0
            ? `<div class="bacheca-banner-conflitto">${t("conflict_banner", { count: conflitti.length, suffix: conflitti.length > 1 ? "i" : "o", suffix2: conflitti.length > 1 ? "i" : "o" })}</div>`
            : "";
        }

        if (thread.length === 0) {
          corpo.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">${t("bacheca_no_threads")}</td></tr>`;
        } else {
          corpo.innerHTML = "";
          thread.forEach(t => {
            const tr = document.createElement("tr");
            tr.className = "bacheca-riga-thread" + (conflitti.includes(t) ? " riga-conflitto" : "");
            const aspetta = (t.aspetta && t.aspetta.length > 0)
              ? t.aspetta.map(a => `<span class="tag-agent ${escapeHtml(a)}">${escapeHtml(a)}</span>`).join(" ")
              : '<span style="color:var(--text-muted);">(nessuno)</span>';
            const stepperHtml = renderizzaWorkflowStepper(t.fase_flusso || "compito", flussoStandard, t.stato_flusso);
            tr.innerHTML = `
              <td title="${escapeHtml(t.thread_id)}">${escapeHtml(t.thread_id.slice(0, 8))}</td>
              <td><span class="status-badge ${escapeHtml(t.stato)}">${escapeHtml(t.stato)}</span></td>
              <td>${stepperHtml}</td>
              <td><span class="tag-agent ${escapeHtml(t.ultimo_mittente)}">${escapeHtml(t.ultimo_mittente)}</span></td>
              <td>${escapeHtml(t.ultimo_tipo)}</td>
              <td>${aspetta}</td>
              <td>${escapeHtml(t.verdetto_umano)}</td>
              <td><button class="btn bacheca-btn-rivivi" style="background: rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.4); color:#c4b5fd; padding:0.3rem 0.6rem; font-size:0.75rem;">${t("btn_relive")}</button></td>
            `;
            tr.addEventListener("click", () => mostraDettaglioThreadBacheca(progetto_id, t.thread_id));
            tr.querySelector(".bacheca-btn-rivivi").addEventListener("click", (ev) => {
              ev.stopPropagation();
              avviaReplayThreadBacheca(progetto_id, t.thread_id);
            });
            corpo.appendChild(tr);
          });
        }

        if (occupatiBox) {
          const occupati = data.occupati || {};
          const fileOccupati = Object.keys(occupati);
          occupatiBox.innerHTML = fileOccupati.length === 0
            ? t("none_locked")
            : fileOccupati.map(f => {
                const info = occupati[f];
                const scadenza = info.scadenza ? formattaOraIt(info.scadenza) : t("lease_no_expiry");
                return `<div>- <b>${escapeHtml(f)}</b>: <span class="tag-agent ${escapeHtml(info.agente)}">${escapeHtml(info.agente)}</span> (${t("lease_expires")} ${scadenza})</div>`;
              }).join("");
        }
      } catch (err) {
        corpo.innerHTML = `<tr><td colspan="8" style="text-align:center; color:#f87171;">Errore bacheca.</td></tr>`;
        renderizzaPendingBacheca({});
        renderizzaPraticheSospese([]);
      }
    }

    async function caricaBachecaFeed() {
      if (!bachecaFeedAttivo) return;
      const select = document.getElementById("bachecaProjSelect");
      const progetto_id = (select && select.value) || "orchestratore";
      const feed = document.getElementById("bachecaFeed");
      if (!feed) return;
      try {
        const res = await fetch(`/api/bacheca/feed?progetto_id=${encodeURIComponent(progetto_id)}&limite=50`);
        if (!res.ok) throw new Error("risposta non valida");
        const data = await res.json();
        const nuovi = (data.messaggi || []).filter(m => !bachecaFeedIdsMostrati.has(m.id_messaggio));
        if (nuovi.length === 0) return;

        const primoGiro = bachecaFeedIdsMostrati.size === 0;
        if (primoGiro) feed.innerHTML = "";

        nuovi.forEach(m => {
          bachecaFeedIdsMostrati.add(m.id_messaggio);
          const badge = `<span class="tag-agent ${escapeHtml(m.mittente)}">${escapeHtml(m.mittente.toUpperCase())}</span>`;
          const destinatari = (m.destinatari || []).map(d => escapeHtml(d)).join(", ");
          const classe = "handoff-msg" + (m.tipo === "segnalazione_conflitto" ? " fail" : m.tipo === "chiusura" ? " success" : " system");
          const riga = document.createElement("div");
          riga.className = classe;
          riga.innerHTML = `<b>${badge} → ${destinatari}</b> [${escapeHtml(formattaOraIt(m.timestamp))}] (${escapeHtml(m.tipo)}): ${escapeHtml(m.testo)}`;
          feed.appendChild(riga);
        });
        feed.scrollTop = feed.scrollHeight;
      } catch (err) {
        // silenzioso
      }
    }

    async function copiaComandoPrompt(cmd) {
      try {
        await copiaTestoNegliAppunti(cmd);
        showFeedback(`${t("cmd_copied")}${cmd}`, "success");
      } catch (err) {
        showFeedback(`${t("cmd_copy_fail")}${cmd}`, "error");
      }
    }

    function renderizzaPianoDichiarato(piano, thread_id) {
      if (!piano || !piano.passi) return "";
      const passiEntries = Object.entries(piano.passi);
      if (passiEntries.length === 0) return "";

      const total = passiEntries.length;
      const completed = passiEntries.filter(([_, p]) => p.stato === "fatto").length;
      const inCorso = passiEntries.filter(([_, p]) => p.stato === "in_corso");
      const perc = total > 0 ? Math.round((completed / total) * 100) : 0;

      // Calcolo collisione informativa dal backend (avviso != blocco)
      const collisioni = piano.collisioni || [];
      let collisioneHtml = "";
      if (collisioni.length > 0) {
        const dettagli = collisioni.map(c => `Passo #${escapeHtml(c.passo_id)} in conflitto (${escapeHtml(c.motivo)}) con Passo #${escapeHtml(c.conflitto_con || '?')}`).join("; ");
        collisioneHtml = `
          <div class="piano-collisione-warning">
            <span style="font-size:1.1rem;">⚠</span>
            <div><b>${t("piano_collision_warn")}</b><div style="font-size:0.75rem; margin-top:0.2rem; opacity:0.9;">${dettagli}</div></div>
          </div>
        `;
      }

      let passiCardsHtml = passiEntries.map(([pid, p]) => {
        const statoCls = p.stato || "non_iniziato";
        const proprietarioHtml = p.proprietario
          ? `<span class="tag-agent ${escapeHtml(p.proprietario)}">${escapeHtml(p.proprietario)}</span>`
          : `<span style="color:var(--text-muted); font-size:0.75rem;">${t("passo_unassigned")}</span>`;

        const writesHtml = (p.write_set && p.write_set.length > 0)
          ? `<div><b>✏️ ${t("passo_writes")}</b> <code>${escapeHtml(p.write_set.join(", "))}</code></div>`
          : "";
        const readsHtml = (p.read_set && p.read_set.length > 0)
          ? `<div><b>👁️ ${t("passo_reads")}</b> <code>${escapeHtml(p.read_set.join(", "))}</code></div>`
          : "";

        const cmdPrendi = `python bacheca.py piano prendi-passo --thread-id ${thread_id} --passo-id ${pid} --agente <tuo_agente>`;
        const cmdHandoff = `python bacheca.py piano proponi-handoff --thread-id ${thread_id} --passo-id ${pid} --a <destinatario> --mittente <tuo_agente>`;
        const cmdFatto = `python bacheca.py piano aggiorna-passo --thread-id ${thread_id} --passo-id ${pid} --stato fatto`;
        const cmdBloccato = `python bacheca.py piano aggiorna-passo --thread-id ${thread_id} --passo-id ${pid} --stato bloccato`;

        return `
          <div class="passo-card ${statoCls}">
            <div class="passo-top">
              <span class="passo-id">#${escapeHtml(pid)}</span>
              <div class="passo-badges">
                ${proprietarioHtml}
                <span class="passo-stato-badge ${statoCls}">${escapeHtml(p.stato)}</span>
              </div>
            </div>
            <div class="passo-desc">${escapeHtml(p.descrizione || "")}</div>
            ${(writesHtml || readsHtml) ? `<div class="passo-sets">${writesHtml}${readsHtml}</div>` : ""}
            <div class="passo-azioni">
              <button type="button" class="btn-passo" title="${escapeHtml(cmdPrendi)}" onclick="copiaComandoPrompt('${escapeHtml(cmdPrendi)}')">${t("btn_take_step")}</button>
              <button type="button" class="btn-passo" title="${escapeHtml(cmdHandoff)}" onclick="copiaComandoPrompt('${escapeHtml(cmdHandoff)}')">${t("btn_handoff_step")}</button>
              <button type="button" class="btn-passo" title="${escapeHtml(cmdFatto)}" onclick="copiaComandoPrompt('${escapeHtml(cmdFatto)}')">${t("btn_done_step")}</button>
              <button type="button" class="btn-passo" title="${escapeHtml(cmdBloccato)}" onclick="copiaComandoPrompt('${escapeHtml(cmdBloccato)}')">${t("btn_block_step")}</button>
            </div>
          </div>
        `;
      }).join("");

      let handoffHtml = "";
      if (piano.handoff_aperti && piano.handoff_aperti.length > 0) {
        const handoffList = piano.handoff_aperti.map(h => {
          const cmdApprova = `python bacheca.py piano approva-handoff --thread-id ${thread_id} --passo-id ${h.passo_id} --mittente <tuo_agente>`;
          return `
            <div class="handoff-item">
              <div>${t("handoff_proposed", { passo: escapeHtml(h.passo_id), da: escapeHtml(h.da || 'nil'), a: escapeHtml(h.a || 'nil'), attore: escapeHtml(h.attore || 'sistema') })}</div>
              <button type="button" class="btn-passo" style="background:rgba(245,158,11,0.2); border-color:rgba(245,158,11,0.4); color:#fbbf24;" title="${escapeHtml(cmdApprova)}" onclick="copiaComandoPrompt('${escapeHtml(cmdApprova)}')">${t("btn_approve_handoff")}</button>
            </div>
          `;
        }).join("");

        handoffHtml = `
          <div class="handoff-box">
            <div style="font-size:0.78rem; font-weight:700; color:#fbbf24; text-transform:uppercase; margin-bottom:0.4rem;">${t("handoff_pending_title")}</div>
            ${handoffList}
          </div>
        `;
      }

      return `
        <div class="piano-widget">
          <div class="piano-header">
            <div class="piano-title">
              <span>🎯</span>
              <span>${t("piano_title")}</span>
              <span style="font-size:0.75rem; font-weight:normal; color:var(--text-muted); font-family:monospace;">(${escapeHtml(piano.piano_id || 'v1')})</span>
            </div>
            <div class="piano-stats">
              <span>${t("piano_progress", { completed, total })}</span>
              <div class="piano-progress-bar">
                <div class="piano-progress-fill" style="width:${perc}%;"></div>
              </div>
              <span style="font-weight:600; color:#93c5fd;">${perc}%</span>
            </div>
          </div>
          ${collisioneHtml}
          <div class="piano-passi-grid">
            ${passiCardsHtml}
          </div>
          ${handoffHtml}
        </div>
      `;
    }

    async function mostraDettaglioThreadBacheca(progetto_id, thread_id) {
      const box = document.getElementById("bachecaDettaglio");
      if (!box) return;
      box.innerHTML = `<div class="handoff-console"><div class="handoff-msg system">${t("thread_loading", { id: escapeHtml(thread_id.slice(0, 8)) })}</div></div>`;
      try {
        const res = await fetch(`/api/bacheca/thread?progetto_id=${encodeURIComponent(progetto_id)}&thread_id=${encodeURIComponent(thread_id)}`);
        if (!res.ok) throw new Error("thread non trovato");
        const data = await res.json();
        const pianoHtml = renderizzaPianoDichiarato(data.piano, thread_id);
        const righe = (data.messaggi || []).map(m => `
          <div class="handoff-msg system">
            <span style="color:var(--text-muted);">[${escapeHtml(formattaOraIt(m.timestamp))}]</span>
            <span class="tag-agent ${escapeHtml(m.mittente)}">${escapeHtml(m.mittente)}</span>
            → ${escapeHtml((m.destinatari || []).join(", "))}
            (${escapeHtml(m.tipo)}): ${escapeHtml(m.testo)}
          </div>
        `).join("");
        const pulsantiRevisione = ["claude", "codex", "gemini"].map(ag => `
          <button type="button" class="btn bacheca-revisione-btn" data-agente="${ag}"
                  data-progetto="${escapeHtml(progetto_id)}" data-thread="${escapeHtml(thread_id)}"
                  style="background: rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.4); color:#c4b5fd; padding:0.3rem 0.7rem; font-size:0.78rem;">
            ${t("revisione_btn", { agente: ag })}
          </button>
        `).join("");
        box.innerHTML = `
          ${pianoHtml}
          <div class="handoff-console">${righe}</div>
          <div style="margin-top:0.7rem; display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
            <span style="font-size:0.78rem; color:var(--text-muted);">${t("revisione_label")}</span>
            ${pulsantiRevisione}
          </div>
          <div id="bachecaRevisioneEsito" style="margin-top:0.4rem; font-size:0.8rem; color:var(--text-muted);"></div>
        `;
        box.querySelectorAll(".bacheca-revisione-btn").forEach(btn => {
          btn.addEventListener("click", () => richiediRevisionePostino(
            btn.dataset.progetto, btn.dataset.agente, btn.dataset.thread
          ));
        });
      } catch (err) {
        box.innerHTML = `<div class="handoff-console"><div class="handoff-msg fail">${t("thread_load_error")}</div></div>`;
      }
    }

    async function richiediRevisionePostino(progetto_id, agente, thread_id) {
      const esito = document.getElementById("bachecaRevisioneEsito");
      if (esito) esito.textContent = t("revisione_in_corso", { agente });
      try {
        const res = await fetch("/api/bacheca/postino/revisione", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ progetto_id, agente, thread_id }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.errore || data.motivo || "richiesta fallita");
        if (esito) {
          const dettaglio = data.motivo ? ` (${escapeHtml(data.motivo)})` : "";
          esito.textContent = `${escapeHtml(data.esito)}${dettaglio}`;
        }
      } catch (err) {
        if (esito) esito.textContent = t("revisione_errore", { messaggio: err.message });
      }
    }

    async function avviaReplayCommit() {
      const elProj = document.getElementById("realProjSelect");
      const progetto_id = (elProj && elProj.value) || "orchestratore";
      const elCommit = document.getElementById("commitSelect");
      const hash = elCommit ? elCommit.value : "";
      const logBox = document.getElementById("handoffLogs");

      if (!hash) {
        showFeedback(t("select_commit_to_play"), "error");
        return;
      }

      fermaSimulazione();
      const elStart = document.getElementById("startSimBtn");
      if (elStart) elStart.style.display = "none";
      const elStop = document.getElementById("stopSimBtn");
      if (elStop) elStop.style.display = "inline-block";

      aggiornaCommitCardSelezionato();

      if (logBox) {
        logBox.innerHTML = `<div class="handoff-msg system">${t("replay_retrieving_events")}<span class="terminal-cursor"></span></div>`;
      }

      let dati;
      try {
        const res = await fetch(`/api/commit/eventi?progetto_id=${encodeURIComponent(progetto_id)}&hash=${encodeURIComponent(hash)}`);
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || "Errore nel recupero eventi");
        }
        dati = await res.json();
      } catch (err) {
        if (logBox) {
          logBox.innerHTML = logBox.innerHTML.replace('<span class="terminal-cursor"></span>', '');
          logBox.innerHTML += `<div class="handoff-msg fail"><b>[Sistema] Errore:</b> ${escapeHtml(err.message)}</div><span class="terminal-cursor"></span>`;
        }
        fermaSimulazione();
        return;
      }

      const eventi = dati.eventi || [];
      if (eventi.length === 0) {
        if (logBox) {
          logBox.innerHTML = `<div class="handoff-msg system">${t("replay_no_events")}</div><span class="terminal-cursor"></span>`;
        }
        fermaSimulazione();
        return;
      }

      if (logBox) {
        logBox.innerHTML = `<div class="handoff-msg system">${t("replay_starting", { count: eventi.length })}<span class="terminal-cursor"></span></div>`;
      }

      let agentePrecedente = "umano";
      let indice = 0;

      function evidenziaLinea(da, a, fallito) {
        if (da === a) return;
        const linea = document.getElementById(`path_${da}_${a}`) || document.getElementById(`path_${a}_${da}`);
        if (linea) {
          linea.classList.add(`active-${da}`);
          if (fallito) linea.classList.add("active-fail");
        }
      }

      function passoSuccessivo() {
        if (logBox) logBox.innerHTML = logBox.innerHTML.replace('<span class="terminal-cursor"></span>', '');

        if (indice >= eventi.length) {
          document.querySelectorAll(".agent-node").forEach(node => node.setAttribute("class", "agent-node"));
          document.querySelectorAll(".handoff-line").forEach(line => line.setAttribute("class", "handoff-line"));
          evidenziaLinea(agentePrecedente, "umano", false);
          const nodoUmano = document.getElementById("node_umano");
          if (nodoUmano) nodoUmano.classList.add("active", "active-success");

          const s = dati.stima_risparmio;
          let riepilogo;
          if (s && s.percentuale_gratis !== null) {
            riepilogo = `
<div class="handoff-msg success" style="font-family: monospace; white-space: pre-wrap; line-height: 1.4; margin-top: 0.8rem;">
<b>${t("replay_complete_header")}</b>
--------------------------------------------
🛡️ <b>${s.percentuale_gratis}%</b> ${t("replay_free_checks")}
   (${s.controlli_locale} ${t("replay_free")} / ${s.controlli_a_pagamento} ${t("replay_paid")})
 💰 ${t("replay_est_savings")}~$${s.risparmio_stimato_usd.toFixed(5)} (rif. ${escapeHtml(s.modello_riferimento)})
--------------------------------------------
</div>`;
          } else {
            riepilogo = `<div class="handoff-msg system">${t("replay_no_savings_checks")}</div>`;
          }
          if (logBox) {
            logBox.innerHTML += riepilogo;
            logBox.innerHTML += `<span class="terminal-cursor"></span>`;
            logBox.scrollTop = logBox.scrollHeight;
          }
          fermaSimulazione();
          return;
        }

        const ev = eventi[indice];
        document.querySelectorAll(".agent-node").forEach(node => node.setAttribute("class", "agent-node"));
        document.querySelectorAll(".handoff-line").forEach(line => line.setAttribute("class", "handoff-line"));

        const fallito = ev.esito_gate === "fallito" || ["fallito", "errore_ambiente", "da_rivedere", "respinto"].includes(ev.stato);

        evidenziaLinea(agentePrecedente, ev.agente, fallito);
        const nodo = document.getElementById(`node_${ev.agente}`);
        if (nodo) {
          nodo.classList.add("active");
          nodo.classList.add(fallito ? "active-fail" : "active-success");
        }
        agentePrecedente = ev.agente;

        const badge = `<span class="tag-agent ${escapeHtml(ev.agente || '')}">${escapeHtml((ev.agente || "?").toUpperCase())}</span>`;
        const msgClass = "handoff-msg" + (fallito ? " fail" : " success");
        if (logBox) {
          logBox.innerHTML += `<div class="${msgClass}"><b>${badge}</b> [${escapeHtml(ev.timestamp.slice(11, 19))}]: ${escapeHtml(ev.note || "")}</div>`;
          logBox.innerHTML += `<span class="terminal-cursor"></span>`;
          logBox.scrollTop = logBox.scrollHeight;
        }

        indice++;
      }

      passoSuccessivo();
      simTimer = setInterval(passoSuccessivo, 1800);
    }

    function _esitoVisivoTipoMessaggio(tipo) {
      if (tipo === "segnalazione_conflitto") return "fail";
      if (tipo === "chiusura") return "success";
      return "neutro";
    }

    async function avviaReplayThreadBacheca(progetto_id, thread_id) {
      const logBox = document.getElementById("handoffLogs");
      const widgetHandoff = document.querySelector(".handoff-container")?.closest(".widget");
      if (widgetHandoff) widgetHandoff.scrollIntoView({ behavior: "smooth", block: "start" });

      fermaSimulazione();
      const elStart = document.getElementById("startSimBtn");
      if (elStart) elStart.style.display = "none";
      const elStop = document.getElementById("stopSimBtn");
      if (elStop) elStop.style.display = "inline-block";
      const elCard = document.getElementById("commitCard");
      if (elCard) elCard.style.display = "none";

      if (logBox) {
        logBox.innerHTML = `<div class="handoff-msg system"><b>[Sistema]</b> Recupero cronologia thread...<span class="terminal-cursor"></span></div>`;
      }

      let dati;
      try {
        const res = await fetch(`/api/bacheca/thread?progetto_id=${encodeURIComponent(progetto_id)}&thread_id=${encodeURIComponent(thread_id)}`);
        if (!res.ok) throw new Error("thread non trovato");
        dati = await res.json();
      } catch (err) {
        if (logBox) {
          logBox.innerHTML = logBox.innerHTML.replace('<span class="terminal-cursor"></span>', '');
          logBox.innerHTML += `<div class="handoff-msg fail"><b>[Sistema] Errore:</b> ${escapeHtml(err.message)}</div><span class="terminal-cursor"></span>`;
        }
        fermaSimulazione();
        return;
      }

      const msgs = dati.messaggi || [];
      if (msgs.length === 0) {
        if (logBox) {
          logBox.innerHTML = `<div class="handoff-msg system">Nessun messaggio in questo thread.</div><span class="terminal-cursor"></span>`;
        }
        fermaSimulazione();
        return;
      }

      if (logBox) {
        logBox.innerHTML = `<div class="handoff-msg system"><b>[Sistema]</b> Rivivo ${msgs.length} messaggi del thread ${escapeHtml(thread_id.slice(0, 8))}...<span class="terminal-cursor"></span></div>`;
      }

      let indiceThread = 0;

      function passoSuccessivoThread() {
        if (logBox) logBox.innerHTML = logBox.innerHTML.replace('<span class="terminal-cursor"></span>', '');

        if (indiceThread >= msgs.length) {
          document.querySelectorAll(".agent-node").forEach(node => node.setAttribute("class", "agent-node"));
          if (logBox) {
            logBox.innerHTML += `<div class="handoff-msg success"><b>${t("thread_replay_completed")}</b></div><span class="terminal-cursor"></span>`;
            logBox.scrollTop = logBox.scrollHeight;
          }
          fermaSimulazione();
          return;
        }

        const m = msgs[indiceThread];
        document.querySelectorAll(".agent-node").forEach(node => node.setAttribute("class", "agent-node"));

        const esito = _esitoVisivoTipoMessaggio(m.tipo);
        const nodo = document.getElementById(`node_${m.mittente}`);
        if (nodo) {
          nodo.classList.add("active");
          if (esito !== "neutro") nodo.classList.add(`active-${esito}`);
        }

        const badgeMittente = `<span class="tag-agent ${escapeHtml(m.mittente)}">${escapeHtml(m.mittente.toUpperCase())}</span>`;
        const destinatari = (m.destinatari || []).map(d => escapeHtml(d)).join(", ");
        const msgClass = "handoff-msg" + (esito !== "neutro" ? ` ${esito}` : " system");
        if (logBox) {
          logBox.innerHTML += `<div class="${msgClass}"><b>${badgeMittente} → ${destinatari}</b> [${escapeHtml(formattaOraIt(m.timestamp, true))}] (${escapeHtml(m.tipo)}): ${escapeHtml(m.testo)}</div>`;
          logBox.innerHTML += `<span class="terminal-cursor"></span>`;
          logBox.scrollTop = logBox.scrollHeight;
        }

        indiceThread++;
      }

      passoSuccessivoThread();
      simTimer = setInterval(passoSuccessivoThread, 1800);
    }
