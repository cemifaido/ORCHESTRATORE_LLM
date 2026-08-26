from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import interfaccia
import bacheca
import registro


class IntegraProgettoTest(unittest.TestCase):
    def test_integra_progetto_funziona_indipendentemente_dalla_cwd(self) -> None:
        """integra_progetto deve leggere schema/config dell'orchestratore dalla propria
        posizione reale (RADICE), non dalla cartella da cui e' stato lanciato il processo:
        altrimenti, lanciato con una cwd diversa, fallisce silenziosamente (skip copia)."""
        cwd_originale = os.getcwd()
        with tempfile.TemporaryDirectory() as cwd_estranea, tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            os.chdir(cwd_estranea)
            try:
                interfaccia.integra_progetto(dest_path)
            finally:
                os.chdir(cwd_originale)

            self.assertTrue((dest_path / "schema" / "evento.v1.json").exists())
            self.assertTrue((dest_path / "config" / "comandi.esempio.json").exists())

    def test_integra_progetto_non_copia_piu_script_orchestratore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)

            for script in ["registro.py", "sentinella.py", "genera_cruscotto.py"]:
                self.assertFalse((dest_path / script).exists())
            self.assertFalse((dest_path / "requirements-orchestratore.txt").exists())

    def test_integra_progetto_aggiorna_gitignore_del_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)

            gitignore_path = dest_path / ".gitignore"
            self.assertTrue(gitignore_path.exists())
            contenuto = gitignore_path.read_text(encoding="utf-8")
            for regola in ["dati_locali/orchestrazione/", "config/comandi.json", "schema/evento.v1.json"]:
                self.assertIn(regola, contenuto)
            for regola_rimossa in ["registro.py", "sentinella.py", "genera_cruscotto.py"]:
                self.assertNotIn(regola_rimossa, contenuto)

    def test_integra_progetto_scrive_istruzioni_sincronizzazione_multi_agente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)

            for nome_file, agente in [("CLAUDE.md", "claude"), ("GEMINI.md", "gemini"), ("AGENTS.md", "codex")]:
                percorso = dest_path / nome_file
                self.assertTrue(percorso.exists(), f"{nome_file} non scritto")
                contenuto = percorso.read_text(encoding="utf-8")
                self.assertIn(f"--agente {agente}", contenuto)
                self.assertIn("--triage-locale", contenuto)
                self.assertIn(str(interfaccia.RADICE), contenuto)

    def test_integra_progetto_non_sovrascrive_istruzioni_personalizzate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            (dest_path / "CLAUDE.md").write_text("personalizzato dall'utente", encoding="utf-8")

            interfaccia.integra_progetto(dest_path)

            self.assertEqual((dest_path / "CLAUDE.md").read_text(encoding="utf-8"), "personalizzato dall'utente")

    def test_integra_progetto_aggiunge_istruzioni_agenti_al_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)

            contenuto = (dest_path / ".gitignore").read_text(encoding="utf-8")
            for regola in ["CLAUDE.md", "GEMINI.md", "AGENTS.md"]:
                self.assertIn(regola, contenuto)

    def test_integra_progetto_non_duplica_regole_gitignore_se_rieseguito(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)
            interfaccia.integra_progetto(dest_path)

            contenuto = (dest_path / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(contenuto.count("config/comandi.json"), 1)

    def test_integra_progetto_preserva_regole_gitignore_preesistenti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            (dest_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

            interfaccia.integra_progetto(dest_path)

            contenuto = (dest_path / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("node_modules/", contenuto)
            self.assertIn("config/comandi.json", contenuto)


class InterpretaOutputSentinellaTest(unittest.TestCase):
    def test_decodifica_json_indentato_multi_riga(self) -> None:
        blob = (
            '{\n'
            '  "esito": "superato",\n'
            '  "codice": 0,\n'
            '  "latenza_ms": 12,\n'
            '  "output": "ok",\n'
            '  "evento": {"esito_gate": "superato"}\n'
            '}\n'
        )
        dati = interfaccia.interpreta_output_sentinella(blob)
        self.assertEqual(dati["esito"], "superato")
        self.assertEqual(dati["evento"]["esito_gate"], "superato")

    def test_fallback_su_output_non_json_include_stderr(self) -> None:
        dati = interfaccia.interpreta_output_sentinella("traceback boom", "errore reale")
        self.assertEqual(dati["output"], "traceback boom")
        self.assertEqual(dati["stderr"], "errore reale")


class EseguiSentinellaTest(unittest.TestCase):
    def test_esegue_comando_nel_progetto_target_senza_copie_di_script(self) -> None:
        """Il progetto target ha solo config/comandi.json, nessuna copia di sentinella.py
        o registro.py: la dashboard deve comunque riuscire a lanciare il comando usando
        lo script centrale, con cwd e --registro puntati al progetto target."""
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            comandi_path = p_path / "config" / "comandi.json"
            comandi_path.parent.mkdir(parents=True, exist_ok=True)
            comandi_path.write_text(json.dumps({
                "versione_schema": 1,
                "comandi": {
                    "prova": {
                        "cartella": ".",
                        "argomenti": ["python", "-c", "print('ok-target')"],
                        "timeout_secondi": 10,
                        "limite_output_caratteri": 1000,
                    }
                }
            }), encoding="utf-8")

            progetti = [{"id": "target", "nome": "Target", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.esegui_sentinella(
                    interfaccia.SentinellaInput(progetto_id="target", comando="prova")
                )

            self.assertEqual(risultato["status"], "success")
            self.assertEqual(risultato["dati"]["esito"], "superato")
            self.assertIn("triage", risultato["dati"])
            self.assertIn("ok-target", risultato["dati"]["output"])

            self.assertFalse((p_path / "sentinella.py").exists())
            self.assertFalse((p_path / "registro.py").exists())

            eventi_path = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
            self.assertTrue(eventi_path.exists())


class StatoApiPaginazioneTest(unittest.TestCase):
    def _progetto_con_n_eventi(self, tmp: str, n: int) -> list[dict]:
        p_path = Path(tmp)
        registro_dir = p_path / "dati_locali" / "orchestrazione"
        registro_dir.mkdir(parents=True, exist_ok=True)
        percorso_eventi = registro_dir / "eventi.jsonl"
        base = {
            "versione_schema": 1,
            "agente": "locale",
            "tipo_compito": "monitoraggio",
            "stato": "passato",
            "esito_gate": "superato",
            "verdetto_umano": "non_revisionato",
            "costo_stimato_usd": 0.0,
            "origine_costo": "stimato",
            "latenza_ms": 0,
            "regole_incluse": [],
            "file_modificati": [],
            "note": "",
            "metadati": {},
        }
        for i in range(n):
            evento = dict(base)
            evento["id_evento"] = f"evt-{i:03d}"
            evento["id_compito"] = f"task-{i:03d}"
            evento["timestamp"] = f"2026-07-04T00:{i // 60:02d}:{i % 60:02d}Z"
            registro.aggiungi_evento(percorso_eventi, evento)
        return [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]

    def test_pagina_predefinita_contiene_50_eventi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti = self._progetto_con_n_eventi(tmp, 120)
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                stato = interfaccia.get_stato()

            self.assertEqual(len(stato["eventi"]), 50)
            self.assertEqual(stato["paginazione"]["pagina"], 1)
            self.assertEqual(stato["paginazione"]["pagine_totali"], 3)
            self.assertEqual(stato["paginazione"]["eventi_totali"], 120)

    def test_seconda_pagina_restituisce_eventi_successivi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti = self._progetto_con_n_eventi(tmp, 120)
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                pagina1 = interfaccia.get_stato(pagina=1, per_pagina=50)
                pagina2 = interfaccia.get_stato(pagina=2, per_pagina=50)

            id_pagina1 = {ev["id_evento"] for ev in pagina1["eventi"]}
            id_pagina2 = {ev["id_evento"] for ev in pagina2["eventi"]}
            self.assertEqual(len(id_pagina2), 50)
            self.assertEqual(id_pagina1 & id_pagina2, set())

    def test_pagina_oltre_il_totale_si_clampa_all_ultima(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti = self._progetto_con_n_eventi(tmp, 120)
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                stato = interfaccia.get_stato(pagina=999, per_pagina=50)

            self.assertEqual(stato["paginazione"]["pagina"], 3)
            self.assertEqual(len(stato["eventi"]), 20)

    def test_aggregati_calcolati_su_tutti_gli_eventi_non_solo_sulla_pagina(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti = self._progetto_con_n_eventi(tmp, 120)
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                stato = interfaccia.get_stato(pagina=1, per_pagina=50)

            self.assertEqual(stato["globali"]["eventi_totali"], 120)
            self.assertEqual(stato["agente_stats"]["locale"]["esecuzioni"], 120)


class StatoApiTest(unittest.TestCase):
    def test_get_stato_riporta_errore_se_registro_e_corrotto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            # Scrive un file di log corrotto (non JSON)
            registro_dir = p_path / "dati_locali" / "orchestrazione"
            registro_dir.mkdir(parents=True, exist_ok=True)
            (registro_dir / "eventi.jsonl").write_text("corrupted line {bad json}", encoding="utf-8")

            progetti = [{"id": "corrupted_proj", "nome": "Corrotto", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                stato = interfaccia.get_stato()

            self.assertIn("corrupted_proj", stato["progetto_stats"])
            stat_proj = stato["progetto_stats"]["corrupted_proj"]
            self.assertIn("errore", stat_proj)
            self.assertIn("registro corrotto", stat_proj["errore"])


class BachecaFeedApiTest(unittest.TestCase):
    def _progetto_con_n_messaggi(self, tmp: str, n: int) -> list[dict]:
        p_path = Path(tmp)
        percorso_messaggi = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
        for i in range(n):
            messaggio = bacheca.costruisci_messaggio(
                mittente="umano",
                destinatari=["codex"],
                tipo="richiesta",
                testo=f"messaggio {i}",
            )
            messaggio["timestamp"] = f"2026-07-05T00:{i // 60:02d}:{i % 60:02d}Z"
            bacheca.aggiungi_messaggio(percorso_messaggi, messaggio)
        return [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]

    def test_feed_clampa_limite_minimo_a_un_messaggio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti = self._progetto_con_n_messaggi(tmp, 3)
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.bacheca_feed_progetto(progetto_id="test_proj", limite=0)

            self.assertEqual(len(risultato["messaggi"]), 1)
            self.assertEqual(risultato["messaggi"][0]["testo"], "messaggio 2")

    def test_feed_clampa_limite_massimo_a_duecento_messaggi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti = self._progetto_con_n_messaggi(tmp, 250)
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.bacheca_feed_progetto(progetto_id="test_proj", limite=1000)

            self.assertEqual(len(risultato["messaggi"]), 200)
            self.assertEqual(risultato["messaggi"][0]["testo"], "messaggio 50")


class BachecaApiTest(unittest.TestCase):
    def _progetto_con_richiesta(self, tmp: str, agente: str = "codex", testo: str = "serve una review") -> tuple[list[dict], dict]:
        p_path = Path(tmp)
        percorso_messaggi = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano",
            destinatari=[agente],
            tipo="richiesta",
            testo=testo,
        )
        bacheca.aggiungi_messaggio(percorso_messaggi, richiesta)
        return [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}], richiesta

    def test_bacheca_riporta_pending_per_agente_operativo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            percorso_messaggi = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
            richiesta_multi = bacheca.costruisci_messaggio(
                mittente="umano",
                destinatari=["codex", "gemini"],
                tipo="richiesta",
                testo="rivedete questa modifica",
            )
            bacheca.aggiungi_messaggio(percorso_messaggi, richiesta_multi)
            risposta_codex = bacheca.costruisci_messaggio(
                mittente="codex",
                destinatari=["umano"],
                tipo="risposta",
                testo="review completata",
                thread_id=richiesta_multi["thread_id"],
                correla_a=richiesta_multi["id_messaggio"],
            )
            bacheca.aggiungi_messaggio(percorso_messaggi, risposta_codex)
            domanda_claude = bacheca.costruisci_messaggio(
                mittente="umano",
                destinatari=["claude"],
                tipo="domanda",
                testo="serve una proposta",
            )
            bacheca.aggiungi_messaggio(percorso_messaggi, domanda_claude)

            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")

            self.assertEqual(risultato["pending_per_agente"], {"claude": 1, "codex": 0, "gemini": 1})

    def test_bacheca_get_non_esegue_side_effect_di_risveglio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti, _richiesta = self._progetto_con_richiesta(tmp, agente="codex")
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti), \
                 patch.object(interfaccia, "_esegui_risveglio_os") as risveglio:
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")

            self.assertEqual(risultato["pending_per_agente"]["codex"], 1)
            risveglio.assert_not_called()

    def test_risvegli_prima_scansione_crea_baseline_senza_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti, richiesta = self._progetto_con_richiesta(tmp, agente="codex")
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti), \
                 patch.object(interfaccia, "_esegui_risveglio_os") as risveglio:
                risultato = interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            self.assertEqual(risultato["risvegli"], [])
            risveglio.assert_not_called()
            stato_path = Path(tmp) / "dati_locali" / "orchestrazione" / "risvegli_notificati.json"
            stato = json.loads(stato_path.read_text(encoding="utf-8"))
            self.assertIn(richiesta["id_messaggio"], stato["notificati"]["codex"])

    def test_risvegli_notifica_solo_nuovi_messaggi_una_volta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti, _richiesta = self._progetto_con_richiesta(tmp, agente="codex", testo="vecchio")
            p_path = Path(tmp)
            percorso_messaggi = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            nuova = bacheca.costruisci_messaggio(
                mittente="umano",
                destinatari=["codex"],
                tipo="richiesta",
                testo="nuovo",
            )
            bacheca.aggiungi_messaggio(percorso_messaggi, nuova)

            with patch.object(interfaccia, "leggi_progetti", return_value=progetti), \
                 patch.object(interfaccia, "_genera_prompt_risveglio_con_llm", return_value="prompt dinamico"):
                primo = interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")
                secondo = interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            self.assertEqual(len(primo["risvegli"]), 1)
            self.assertEqual(primo["risvegli"][0]["agente"], "codex")
            self.assertEqual(primo["risvegli"][0]["id_messaggio"], nuova["id_messaggio"])
            self.assertEqual(primo["risvegli"][0]["status"], "test")
            self.assertEqual(secondo["risvegli"], [])

    def test_risveglio_claude_senza_sessione_viva_apre_nuova_chat_con_prompt(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano",
            destinatari=["claude"],
            tipo="richiesta",
            testo="esegui i test",
        )
        with patch.object(interfaccia, "_genera_prompt_risveglio_con_llm", return_value="Prompt dinamico per Claude"):
            risultato = interfaccia._esegui_risveglio_os("claude", [richiesta], claude_session_id=None)

        self.assertEqual(risultato["status"], "test")
        self.assertEqual(risultato["modalita"], "nuova_chat")
        self.assertIn("Prompt%20dinamico%20per%20Claude", risultato["uri"])

    def test_risveglio_claude_con_sessione_viva_non_apre_nuova_chat(self) -> None:
        # L'estensione non inietta mai un prompt in una sessione già aperta e un
        # /open fuori finestra creerebbe una chat parallela: con una sessione viva
        # il risveglio deve limitarsi a portare l'IDE in primo piano.
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano",
            destinatari=["claude"],
            tipo="richiesta",
            testo="esegui i test",
        )
        with patch.object(interfaccia, "_genera_prompt_risveglio_con_llm", return_value="Prompt dinamico per Claude"):
            risultato = interfaccia._esegui_risveglio_os("claude", [richiesta], claude_session_id="sessione123")

        self.assertEqual(risultato["status"], "test")
        self.assertEqual(risultato["modalita"], "focus_sessione_attiva")
        self.assertEqual(risultato["uri"], "antigravity-ide://")
        self.assertNotIn("prompt=", risultato["uri"])
        self.assertNotIn("session=", risultato["uri"])

    def test_trova_ultima_sessione_claude_ignora_processi_morti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            progetto = home / "progetto"
            progetto.mkdir()
            dir_sessioni = home / ".claude" / "sessions"
            dir_sessioni.mkdir(parents=True)
            # Sessione più recente ma con processo morto: non va scelta.
            (dir_sessioni / "morta.json").write_text(json.dumps({
                "pid": 111, "sessionId": "sessione-morta",
                "cwd": str(progetto), "startedAt": 2000,
            }), encoding="utf-8")
            (dir_sessioni / "viva.json").write_text(json.dumps({
                "pid": 222, "sessionId": "sessione-viva",
                "cwd": str(progetto), "startedAt": 1000,
            }), encoding="utf-8")

            with patch.object(interfaccia.Path, "home", return_value=home), \
                 patch.object(interfaccia, "_pid_vivo", side_effect=lambda pid: pid == 222):
                trovata = interfaccia._trova_ultima_sessione_claude(progetto)

            self.assertEqual(trovata, "sessione-viva")

    def test_pid_vivo_su_pid_non_valido(self) -> None:
        self.assertFalse(interfaccia._pid_vivo(None))
        self.assertFalse(interfaccia._pid_vivo(0))
        self.assertFalse(interfaccia._pid_vivo(-5))

    def test_pid_vivo_riconosce_processo_corrente(self) -> None:
        self.assertTrue(interfaccia._pid_vivo(os.getpid()))


class FlussiDichiaratiApiTest(unittest.TestCase):
    def test_leggi_flussi_dichiarati_carica_flussi_json(self) -> None:
        flussi = interfaccia.leggi_flussi_dichiarati()
        self.assertIn("compito_standard", flussi)
        self.assertEqual(flussi["compito_standard"]["id_flusso"], "compito_standard")

    def test_bacheca_riporta_pratiche_sospese_e_fase_flusso(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            percorso_messaggi = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
            percorso_registro = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
            chk = bacheca.costruisci_messaggio(
                mittente="claude",
                destinatari=["gemini", "codex", "umano"],
                tipo="checkpoint",
                testo="test checkpoint",
                thread_id="t1",
                ripresa={
                    "attende": "umano",
                    "oggetto_atteso": "verdetto commit",
                    "azioni_per_esito": {"approvato": "commit", "respinto": "restore", "modifiche_richieste": "fix"},
                    "contesto_minimo": {"thread_id": "t1", "riferimenti": [], "comandi_consentiti": ["git status"]}
                }
            )
            bacheca.aggiungi_messaggio(percorso_messaggi, chk)
            ev = {
                "versione_schema": 1,
                "id_evento": "evt-t1",
                "timestamp": "2026-08-26T10:00:00Z",
                "id_compito": "t1",
                "agente": "claude",
                "tipo_compito": "servizi",
                "stato": "passato",
                "esito_gate": "superato",
                "verdetto_umano": "non_revisionato",
                "costo_stimato_usd": 0.0,
                "origine_costo": "stimato",
                "latenza_ms": 0,
                "regole_incluse": ["sessione_interattiva"],
                "note": "sviluppo e test",
                "file_modificati": ["a.py"],
                "thread_id": "t1",
                "metadati": {},
            }
            registro.aggiungi_evento(percorso_registro, ev)

            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")

            self.assertEqual(len(risultato["pratiche_sospese"]), 1)
            self.assertEqual(risultato["pratiche_sospese"][0]["oggetto_atteso"], "verdetto commit")
            self.assertEqual(risultato["thread"][0]["fase_flusso"], "approvazione_umana")
            self.assertEqual(risultato["thread"][0]["stato_flusso"]["stato"], "attivo")
            self.assertEqual(risultato["thread"][0]["stato_flusso"]["fase"], "approvazione_umana")
            self.assertIn("file_modificati", risultato["thread"][0]["stato_flusso"]["prove"])

    def test_bacheca_thread_senza_eventi_parte_da_compito(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            percorso_messaggi = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
            msg = bacheca.costruisci_messaggio(
                mittente="claude",
                destinatari=["gemini", "codex", "umano"],
                tipo="richiesta",
                testo="richiesta iniziale",
                thread_id="t2",
            )
            bacheca.aggiungi_messaggio(percorso_messaggi, msg)

            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")

            self.assertEqual(risultato["thread"][0]["fase_flusso"], "compito")
            self.assertEqual(risultato["thread"][0]["stato_flusso"]["stato"], "attivo")

    def test_bacheca_thread_chiuso_senza_prerequisiti_e_incoerente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            percorso_messaggi = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
            msg = bacheca.costruisci_messaggio(
                mittente="claude",
                destinatari=["gemini", "codex", "umano"],
                tipo="chiusura",
                testo="chiudo subito senza prove",
                thread_id="t3",
            )
            bacheca.aggiungi_messaggio(percorso_messaggi, msg)

            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")

            self.assertIsNone(risultato["thread"][0]["fase_flusso"])
            self.assertEqual(risultato["thread"][0]["stato_flusso"]["stato"], "incoerente")
            self.assertTrue(len(risultato["thread"][0]["stato_flusso"]["diagnostica"]) > 0)

    def test_adapter_calcola_fase_flusso_diretto(self) -> None:
        # Senza eventi -> fase 'compito'
        fase = interfaccia._calcola_fase_flusso([], "t_test")
        self.assertEqual(fase, "compito")

        # Con chiusura senza prove -> None (fail-safe)
        chiusura_msg = [{"thread_id": "t_test", "tipo": "chiusura"}]
        fase_incoerente = interfaccia._calcola_fase_flusso(chiusura_msg, "t_test")
        self.assertIsNone(fase_incoerente)

    def test_bacheca_espone_flussi_dichiarati_e_passi_coerenti(self) -> None:
        flussi = interfaccia.leggi_flussi_dichiarati()
        self.assertIn("compito_standard", flussi)
        passi_ids = [p["id"] for p in flussi["compito_standard"].get("passi", [])]
        self.assertIn("compito", passi_ids)
        self.assertIn("approvazione_umana", passi_ids)
        self.assertIn("chiusura", passi_ids)


class PostinoAutomaticoTest(unittest.TestCase):
    def test_postino_attivo_e_imposta_postino(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            # Default alla prima consegna o cartella nuova: SPENTO (False, fail-closed)
            self.assertFalse(interfaccia.postino_attivo(p_path))

            # Imposta attivo -> crea POSTINO_ATTIVO
            stato = interfaccia.imposta_postino(p_path, attivo=True)
            self.assertTrue(stato)
            self.assertTrue(interfaccia.postino_attivo(p_path))

            # Imposta disattivo -> rimuove POSTINO_ATTIVO
            stato = interfaccia.imposta_postino(p_path, attivo=False)
            self.assertFalse(stato)
            self.assertFalse(interfaccia.postino_attivo(p_path))

    def test_bacheca_riporta_postino_attivo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")
                self.assertIn("postino_attivo", risultato)
                self.assertFalse(risultato["postino_attivo"])

                interfaccia.imposta_postino(p_path, attivo=True)
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")
                self.assertTrue(risultato["postino_attivo"])


class PostinoHeadlessTest(unittest.TestCase):
    """Sotto-interruttore del dispatch headless (claude -p / codex exec reali):
    opt-in separato dal postino di base, sempre inerte se il postino di base e'
    spento, mai chiamate reali ai provider - postino.dispatch va sempre mockato."""

    def _progetto_con_richiesta(self, tmp: str, agente: str = "codex") -> tuple[list[dict], dict]:
        p_path = Path(tmp)
        percorso_messaggi = p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=[agente], tipo="richiesta", testo="rispondi",
        )
        bacheca.aggiungi_messaggio(percorso_messaggi, richiesta)
        return [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}], richiesta

    def test_postino_headless_attivo_e_imposta_postino_headless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            self.assertFalse(interfaccia.postino_headless_attivo(p_path))

            stato = interfaccia.imposta_postino_headless(p_path, attivo=True)
            self.assertTrue(stato)
            self.assertTrue(interfaccia.postino_headless_attivo(p_path))

            stato = interfaccia.imposta_postino_headless(p_path, attivo=False)
            self.assertFalse(stato)
            self.assertFalse(interfaccia.postino_headless_attivo(p_path))

    def test_headless_indipendente_dal_flag_postino_di_base_su_disco(self) -> None:
        """I due flag sono due file distinti: accendere l'uno non tocca l'altro."""
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            interfaccia.imposta_postino_headless(p_path, attivo=True)
            self.assertFalse(interfaccia.postino_attivo(p_path))
            self.assertTrue(interfaccia.postino_headless_attivo(p_path))

    def test_bacheca_riporta_postino_headless_attivo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")
                self.assertIn("postino_headless_attivo", risultato)
                self.assertFalse(risultato["postino_headless_attivo"])

                interfaccia.imposta_postino_headless(p_path, attivo=True)
                risultato = interfaccia.bacheca_progetto(progetto_id="test_proj")
                self.assertTrue(risultato["postino_headless_attivo"])

    def test_endpoint_toggle_headless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                payload = interfaccia.PostinoHeadlessToggleInput(progetto_id="test_proj", attivo=True)
                risultato = interfaccia.toggle_postino_headless(payload)
                self.assertEqual(risultato, {"progetto_id": "test_proj", "postino_headless_attivo": True})
                self.assertTrue(interfaccia.postino_headless_attivo(p_path))

    def test_risveglio_usa_dispatch_headless_solo_con_entrambi_i_toggle_e_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti, richiesta = self._progetto_con_richiesta(tmp, agente="codex")
            p_path = Path(tmp)
            interfaccia.imposta_postino(p_path, attivo=True)
            interfaccia.imposta_postino_headless(p_path, attivo=True)

            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")  # baseline
                nuova = bacheca.costruisci_messaggio(
                    mittente="umano", destinatari=["codex"], tipo="richiesta", testo="nuovo",
                )
                bacheca.aggiungi_messaggio(
                    p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl", nuova
                )
                with patch.object(
                    interfaccia.postino, "dispatch",
                    return_value={"esito": "inviato", "codice": 0},
                ) as dispatch_mock, patch.object(interfaccia, "_esegui_risveglio_os") as risveglio_os:
                    risultato = interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            dispatch_mock.assert_called_once_with(p_path, "codex", nuova["thread_id"])
            risveglio_os.assert_not_called()
            self.assertEqual(risultato["risvegli"][0]["status"], "headless")
            self.assertEqual(risultato["risvegli"][0]["codice"], 0)

    def test_risveglio_headless_bloccato_da_policy_non_apre_comunque_finestra(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti, richiesta = self._progetto_con_richiesta(tmp, agente="codex")
            p_path = Path(tmp)
            interfaccia.imposta_postino(p_path, attivo=True)
            interfaccia.imposta_postino_headless(p_path, attivo=True)

            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")
                nuova = bacheca.costruisci_messaggio(
                    mittente="umano", destinatari=["codex"], tipo="richiesta", testo="nuovo",
                )
                bacheca.aggiungi_messaggio(
                    p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl", nuova
                )
                with patch.object(
                    interfaccia.postino, "dispatch",
                    return_value={"esito": "bloccato", "motivo": "debounce"},
                ), patch.object(interfaccia, "_esegui_risveglio_os") as risveglio_os:
                    risultato = interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            risveglio_os.assert_not_called()
            self.assertEqual(risultato["risvegli"][0]["status"], "bloccato")
            self.assertEqual(risultato["risvegli"][0]["motivo"], "debounce")

    def test_risveglio_deep_link_prenota_prima_dell_azione_os(self) -> None:
        """Guardrail (trovato da Codex in modalita' revisione, 2026-08-26): la
        prenotazione (registra_canale) deve avvenire PRIMA dell'azione OS, non
        dopo - altrimenti due richieste concorrenti passano entrambe il
        pre-check ed eseguono entrambe l'azione OS, anche se il tetto ne
        permette solo una. Se la prenotazione e' bloccata, l'azione OS non
        deve mai partire."""
        with tempfile.TemporaryDirectory() as tmp:
            progetti, richiesta = self._progetto_con_richiesta(tmp, agente="gemini")
            p_path = Path(tmp)
            interfaccia.imposta_postino(p_path, attivo=True)

            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")
                nuova = bacheca.costruisci_messaggio(
                    mittente="umano", destinatari=["gemini"], tipo="richiesta", testo="nuovo",
                )
                bacheca.aggiungi_messaggio(
                    p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl", nuova
                )
                with (
                    patch.object(
                        interfaccia.postino, "registra_canale",
                        return_value={"esito": "bloccato", "motivo": "tetto_thread"},
                    ) as registra_mock,
                    patch.object(interfaccia, "_esegui_risveglio_os") as risveglio_os,
                ):
                    risultato = interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            registra_mock.assert_called_once()
            risveglio_os.assert_not_called()
            self.assertEqual(risultato["risvegli"][0]["status"], "bloccato")
            self.assertEqual(risultato["risvegli"][0]["motivo"], "tetto_thread")

    def test_risveglio_deep_link_esegue_azione_os_dopo_prenotazione_riuscita(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti, richiesta = self._progetto_con_richiesta(tmp, agente="gemini")
            p_path = Path(tmp)
            interfaccia.imposta_postino(p_path, attivo=True)

            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")
                nuova = bacheca.costruisci_messaggio(
                    mittente="umano", destinatari=["gemini"], tipo="richiesta", testo="nuovo",
                )
                bacheca.aggiungi_messaggio(
                    p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl", nuova
                )
                with (
                    patch.object(
                        interfaccia.postino, "registra_canale",
                        return_value={"esito": "registrato", "canale": "deep_link"},
                    ) as registra_mock,
                    patch.object(
                        interfaccia, "_esegui_risveglio_os",
                        return_value={"status": "eseguito", "modalita": "nuova_chat"},
                    ) as risveglio_os,
                ):
                    interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            registra_mock.assert_called_once()
            risveglio_os.assert_called_once()

    def test_risveglio_headless_usa_gemini_capability_ora_supportata(self) -> None:
        """Gemini e' in postino.COMANDI dal 2026-08-25 (agy con
        --dangerously-skip-permissions, verificato dal vivo su Windows/WSL):
        va sul dispatch headless come claude/codex, non piu' sempre a finestra."""
        with tempfile.TemporaryDirectory() as tmp:
            progetti, richiesta = self._progetto_con_richiesta(tmp, agente="gemini")
            p_path = Path(tmp)
            interfaccia.imposta_postino(p_path, attivo=True)
            interfaccia.imposta_postino_headless(p_path, attivo=True)

            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")  # baseline
                nuova = bacheca.costruisci_messaggio(
                    mittente="umano", destinatari=["gemini"], tipo="richiesta", testo="nuovo",
                )
                bacheca.aggiungi_messaggio(
                    p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl", nuova
                )
                with patch.object(
                    interfaccia.postino, "dispatch",
                    return_value={"esito": "inviato", "codice": 0},
                ) as dispatch_mock, patch.object(interfaccia, "_esegui_risveglio_os") as risveglio_os:
                    interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            dispatch_mock.assert_called_once_with(p_path, "gemini", nuova["thread_id"])
            risveglio_os.assert_not_called()

    def test_risveglio_headless_ignora_capability_non_supportata(self) -> None:
        """Un agente non in postino.COMANDI resta sempre sul percorso a
        finestra, qualunque sia lo stato del toggle headless - patchando
        COMANDI direttamente cosi' il test resta valido indipendentemente
        da quali capability sono davvero configurate in futuro (oggi
        claude/codex/gemini sono tutte supportate, nessun agente reale
        monitorato dalla dashboard resterebbe fuori)."""
        with tempfile.TemporaryDirectory() as tmp:
            progetti, richiesta = self._progetto_con_richiesta(tmp, agente="codex")
            p_path = Path(tmp)
            interfaccia.imposta_postino(p_path, attivo=True)
            interfaccia.imposta_postino_headless(p_path, attivo=True)

            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")  # baseline
                nuova = bacheca.costruisci_messaggio(
                    mittente="umano", destinatari=["codex"], tipo="richiesta", testo="nuovo",
                )
                bacheca.aggiungi_messaggio(
                    p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl", nuova
                )
                with patch.object(interfaccia.postino, "COMANDI", {}), \
                     patch.object(interfaccia.postino, "dispatch") as dispatch_mock, \
                     patch.object(interfaccia, "_esegui_risveglio_os", return_value={"status": "test"}) as risveglio_os:
                    interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            dispatch_mock.assert_not_called()
            risveglio_os.assert_called_once()

    def test_risveglio_ignora_dispatch_headless_se_postino_base_spento(self) -> None:
        """Il toggle headless da solo non basta: senza il postino di base acceso
        resta inerte (nessuna chiamata reale, nessun risveglio automatico)."""
        with tempfile.TemporaryDirectory() as tmp:
            progetti, richiesta = self._progetto_con_richiesta(tmp, agente="codex")
            p_path = Path(tmp)
            interfaccia.imposta_postino_headless(p_path, attivo=True)  # base resta spento

            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")  # baseline
                nuova = bacheca.costruisci_messaggio(
                    mittente="umano", destinatari=["codex"], tipo="richiesta", testo="nuovo",
                )
                bacheca.aggiungi_messaggio(
                    p_path / "dati_locali" / "orchestrazione" / "messaggi.jsonl", nuova
                )
                with patch.object(interfaccia.postino, "dispatch") as dispatch_mock, \
                     patch.object(interfaccia, "_esegui_risveglio_os", return_value={"status": "test"}) as risveglio_os:
                    interfaccia.esegui_risvegli_bacheca(progetto_id="test_proj")

            dispatch_mock.assert_not_called()
            risveglio_os.assert_called_once()


    def test_api_commit_lista_con_interazioni(self) -> None:
        """Verifica che /api/commit/lista ritorni la lista dei commit con il campo interazioni."""
        from fastapi.testclient import TestClient
        client = TestClient(interfaccia.app)
        res = client.get("/api/commit/lista?progetto_id=orchestratore&limite=3")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("commit", data)
        self.assertGreaterEqual(len(data["commit"]), 1)
        for c in data["commit"]:
            self.assertIn("hash", c)
            self.assertIn("data", c)
            self.assertIn("autore", c)
            self.assertIn("messaggio", c)
            self.assertIn("interazioni", c)
            self.assertIsInstance(c["interazioni"], int)


class PostinoRevisioneEndpointTest(unittest.TestCase):
    """Pulsante 'chiedi una revisione' della bacheca (docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md
    #modalita-revisione): sempre modo='revisione' esplicito, mai il default
    'routine' del watcher automatico - postino.dispatch va sempre mockato."""

    def test_richiede_dispatch_in_modalita_revisione(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            interfaccia.imposta_postino_headless(p_path, attivo=True)
            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with (
                patch.object(interfaccia, "leggi_progetti", return_value=progetti),
                patch.object(interfaccia.postino, "dispatch", return_value={"esito": "inviato"}) as dispatch_mock,
            ):
                payload = interfaccia.PostinoRevisioneInput(
                    progetto_id="test_proj", agente="codex", thread_id="t-1",
                )
                risultato = interfaccia.richiedi_revisione_postino(payload)

        self.assertEqual(risultato, {"esito": "inviato"})
        dispatch_mock.assert_called_once_with(p_path, "codex", "t-1", modo="revisione")

    def test_bloccato_senza_dispatch_headless_attivo(self) -> None:
        """Guardrail di sicurezza (revisione esterna v3, 2026-08-25, NEW-2):
        senza il toggle 'Dispatch Headless' esplicitamente acceso, il pulsante
        non deve mai lanciare un processo reale, qualunque sia lo stato del
        postino di base."""
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with (
                patch.object(interfaccia, "leggi_progetti", return_value=progetti),
                patch.object(interfaccia.postino, "dispatch") as dispatch_mock,
            ):
                payload = interfaccia.PostinoRevisioneInput(
                    progetto_id="test_proj", agente="codex", thread_id="t-1",
                )
                risultato = interfaccia.richiedi_revisione_postino(payload)

        self.assertEqual(risultato, {"esito": "bloccato", "motivo": "dispatch_headless_disattivato"})
        dispatch_mock.assert_not_called()

    def test_rifiuta_agente_non_valido(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            progetti = [{"id": "test_proj", "nome": "Test", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                payload = interfaccia.PostinoRevisioneInput(
                    progetto_id="test_proj", agente="locale", thread_id="t-1",
                )
                with self.assertRaises(interfaccia.HTTPException) as ctx:
                    interfaccia.richiedi_revisione_postino(payload)
        self.assertEqual(ctx.exception.status_code, 400)


class InterfacciaI18nTest(unittest.TestCase):
    def test_interfaccia_html_contiene_selettore_lingua_e_dizionari_i18n(self) -> None:
        """Verifica che interfaccia.html/static/interfaccia.js contengano lo
        switcher lingua IT/EN e il dizionario i18n. HTML e JS separati dal
        2026-08-25 (revisione di sicurezza, L5 - monolite spezzato in file
        statici), quindi le asserzioni sono divise di conseguenza."""
        self.assertTrue(interfaccia.PERCORSO_HTML.exists())
        html = interfaccia.PERCORSO_HTML.read_text(encoding="utf-8")
        self.assertIn("lang-switcher", html)
        self.assertIn("langItBtn", html)
        self.assertIn("langEnBtn", html)
        self.assertIn("impostaLingua", html)
        self.assertIn("header_title", html)
        self.assertIn("Orchestratore LLM", html)

        js = (interfaccia.RADICE / "static" / "interfaccia.js").read_text(encoding="utf-8")
        self.assertIn("const I18N =", js)
        self.assertIn("header_title", js)
        self.assertIn("LLM Orchestrator", js)

    def test_readme_bilingue_presente(self) -> None:
        """Verifica che README.md e README_EN.md siano coerenti e collegati tra loro."""
        readme_it = interfaccia.RADICE / "README.md"
        readme_en = interfaccia.RADICE / "README_EN.md"
        self.assertTrue(readme_it.exists())
        self.assertTrue(readme_en.exists())
        self.assertIn("README_EN.md", readme_it.read_text(encoding="utf-8"))
        self.assertIn("README.md", readme_en.read_text(encoding="utf-8"))


class AutenticazioneBindEspostoTest(unittest.TestCase):
    """Guardrail di sicurezza (revisione esterna, 2026-08-25): un bind
    non-loopback senza chiave condivisa non deve mai esporre le route che
    mutano stato — vedi commento in interfaccia.py accanto al middleware."""

    def test_bind_e_loopback_riconosce_gli_indirizzi_locali(self) -> None:
        self.assertTrue(interfaccia._bind_e_loopback("127.0.0.1"))
        self.assertTrue(interfaccia._bind_e_loopback("localhost"))
        self.assertTrue(interfaccia._bind_e_loopback("::1"))
        self.assertFalse(interfaccia._bind_e_loopback("0.0.0.0"))
        self.assertFalse(interfaccia._bind_e_loopback("192.168.1.10"))

    def test_bind_loopback_non_richiede_alcuna_chiave(self) -> None:
        from fastapi.testclient import TestClient

        with patch.object(interfaccia, "HOST_DASHBOARD", "127.0.0.1"):
            client = TestClient(interfaccia.app)
            res = client.get("/")
        self.assertEqual(res.status_code, 200)

    def test_bind_esposto_rifiuta_senza_chiave_corretta(self) -> None:
        from fastapi.testclient import TestClient

        with (
            patch.object(interfaccia, "HOST_DASHBOARD", "0.0.0.0"),
            patch.object(interfaccia, "CHIAVE_API_DASHBOARD", "segreta"),
        ):
            client = TestClient(interfaccia.app)
            senza_chiave = client.get("/")
            chiave_sbagliata = client.get("/", headers={"X-Orchestratore-Key": "no"})
            chiave_giusta = client.get("/", headers={"X-Orchestratore-Key": "segreta"})
        self.assertEqual(senza_chiave.status_code, 401)
        self.assertEqual(chiave_sbagliata.status_code, 401)
        self.assertEqual(chiave_giusta.status_code, 200)


class GeneraPromptRisveglioLLMTest(unittest.TestCase):
    """Guardrail di sicurezza (revisione esterna, 2026-08-25, M4): la cronologia
    del thread e' contenuto non fidato che finisce nel prompt e il "prompt"
    generato in risposta finisce copiato negli appunti dell'utente - deve
    arrivare al modello racchiuso fra delimitatori espliciti."""

    @patch("adattatori.litellm.completamento_locale")
    def test_delimita_il_contenuto_non_fidato(self, mock_completamento: MagicMock) -> None:
        from adattatori import litellm as litellm_mod

        mock_completamento.return_value = (
            '{"agente": "claude", "prompt": "vai"}',
            litellm_mod.MisurazioneLiteLLM(
                modello="x", provider="locale", costo_usd=0.0,
                token_prompt=1, token_completion=1, token_totali=2,
            ),
        )
        cronologia = [
            {"mittente": "codex", "destinatari": ["claude"], "tipo": "richiesta", "testo": "fai qualcosa"}
        ]

        interfaccia._genera_prompt_risveglio_con_llm("claude", cronologia)

        messaggi_inviati = mock_completamento.call_args.kwargs["messaggi"]
        contenuto = messaggi_inviati[-1]["content"]
        self.assertIn("<<<INIZIO_CRONOLOGIA>>>", contenuto)
        self.assertIn("<<<FINE_CRONOLOGIA>>>", contenuto)
        self.assertIn("fai qualcosa", contenuto)


if __name__ == "__main__":
    unittest.main()


