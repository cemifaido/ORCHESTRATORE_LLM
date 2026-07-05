from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
