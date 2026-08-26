from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import setup_wizard as sw


class DiagnosticaAmbienteTest(unittest.TestCase):
    def test_diagnostica_rileva_python_corretto(self) -> None:
        diag = sw.diagnostica_ambiente()
        self.assertTrue(diag["python_ok"])
        self.assertIn("python_versione", diag)

    @patch("shutil.which")
    def test_diagnostica_rileva_cli_presenti(self, mock_which: MagicMock) -> None:
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ("claude", "git") else None
        diag = sw.diagnostica_ambiente()
        self.assertTrue(diag["claude_presente"])
        self.assertTrue(diag["git_presente"])
        self.assertFalse(diag["codex_presente"])


class GeneraFileEnvTest(unittest.TestCase):
    def test_genera_env_con_parametri_personalizzati(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_env = Path(tmp) / ".env"
            config = {
                "host": "0.0.0.0",
                "porta": 9000,
                "agenti_abilitati": ["claude", "gemini"],
                "llm_locale_abilitato": False,
                "porta_llama": 8080,
                "script_avvio_llama": "custom_llama.ps1",
                "modello_gguf": "custom_model.gguf",
                "postino_attivo": True,
                "postino_headless": True,
            }
            sw.genera_file_env(config, percorso_env=file_env)
            contenuto = file_env.read_text(encoding="utf-8")
            self.assertIn("ORCHESTRATORE_HOST=0.0.0.0", contenuto)
            self.assertIn("ORCHESTRATORE_PORTA=9000", contenuto)
            self.assertIn("AGENTI_ABILITATI=claude,gemini", contenuto)
            self.assertIn("LLM_LOCALE_ABILITATO=false", contenuto)
            self.assertIn("PORTA_LLAMA=8080", contenuto)
            self.assertIn("POSTINO_HEADLESS_DEFAULT=true", contenuto)


class InizializzaProgettiTest(unittest.TestCase):
    def test_crea_progetti_json_se_assente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_proj = Path(tmp) / "progetti.json"
            with patch.object(sw, "FILE_PROGETTI", file_proj), \
                 patch.object(sw, "DIR_DATI_LOCALI", Path(tmp)):
                sw.inizializza_progetti(radice_orchestratore=Path(tmp))
                self.assertTrue(file_proj.exists())
                data = json.loads(file_proj.read_text(encoding="utf-8"))
                self.assertTrue(any(p.get("id") == "orchestratore" for p in data["progetti"]))


class InizializzaConfigAgentiTest(unittest.TestCase):
    def test_genera_config_claude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            risultati = sw.inizializza_config_agenti(["claude"], radice_progetto=radice)
            self.assertIn("claude", risultati)
            file_claude = radice / ".claude" / "settings.json"
            self.assertTrue(file_claude.exists())
            data = json.loads(file_claude.read_text(encoding="utf-8"))
            self.assertIn("hooks", data)
            self.assertIn("SessionStart", data["hooks"])

    def test_genera_config_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            risultati = sw.inizializza_config_agenti(["codex"], radice_progetto=radice)
            self.assertIn("codex", risultati)
            file_codex = radice / ".codex" / "hooks.json"
            self.assertTrue(file_codex.exists())
            data = json.loads(file_codex.read_text(encoding="utf-8"))
            self.assertIn("hooks", data)
            self.assertIn("UserPromptSubmit", data["hooks"])

    def test_genera_config_gemini(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            risultati = sw.inizializza_config_agenti(["gemini"], radice_progetto=radice)
            self.assertIn("gemini", risultati)
            file_agents = radice / ".agents" / "hooks.json"
            file_gemini = radice / ".gemini" / "settings.json"
            self.assertTrue(file_agents.exists())
            self.assertTrue(file_gemini.exists())
            data_agents = json.loads(file_agents.read_text(encoding="utf-8"))
            self.assertIn("bacheca-gemini", data_agents)

    def test_non_sovrascrive_senza_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            file_claude = radice / ".claude" / "settings.json"
            file_claude.parent.mkdir(parents=True, exist_ok=True)
            file_claude.write_text('{"personalizzato": true}', encoding="utf-8")

            sw.inizializza_config_agenti(["claude"], radice_progetto=radice, sovrascrivi=False)
            self.assertEqual(file_claude.read_text(encoding="utf-8"), '{"personalizzato": true}')

            sw.inizializza_config_agenti(["claude"], radice_progetto=radice, sovrascrivi=True)
            self.assertIn("hooks", json.loads(file_claude.read_text(encoding="utf-8")))

    def test_template_generici_validi_e_senza_dati_locali(self) -> None:
        dir_templates = sw.RADICE / "config" / "templates_hook"
        self.assertTrue(dir_templates.exists())
        template_files = list(dir_templates.glob("*.json"))
        self.assertGreater(len(template_files), 0)

        for tf in template_files:
            contenuto = tf.read_text(encoding="utf-8")
            # Validità sintattica JSON
            data = json.loads(contenuto)
            self.assertIsInstance(data, dict)
            # Nessun path assoluto proprietario o locale
            self.assertNotIn("D:\\", contenuto)
            self.assertNotIn("C:\\Users\\", contenuto)
            self.assertNotIn("/home/", contenuto)
            self.assertNotIn("/Users/", contenuto)


class ModalitaAutomaticaTest(unittest.TestCase):
    def test_esegui_wizard_auto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_env = Path(tmp) / ".env"
            file_proj = Path(tmp) / "progetti.json"
            with patch.object(sw, "FILE_ENV", file_env), \
                 patch.object(sw, "FILE_PROGETTI", file_proj), \
                 patch.object(sw, "DIR_DATI_LOCALI", Path(tmp)), \
                 patch.object(sw, "RADICE", Path(tmp)), \
                 patch.object(sw, "installa_hook_git", return_value=True):
                # Assicuriamoci che la cartella templates_hook esista nella radice mock
                (Path(tmp) / "config" / "templates_hook").mkdir(parents=True, exist_ok=True)
                for tf in (sw.RADICE / "config" / "templates_hook").glob("*.json"):
                    (Path(tmp) / "config" / "templates_hook" / tf.name).write_text(tf.read_text(encoding="utf-8"), encoding="utf-8")

                codice = sw.esegui_wizard(auto=True, salta_pip=True)
                self.assertEqual(codice, 0)
                self.assertTrue(file_env.exists())
                self.assertTrue(file_proj.exists())


if __name__ == "__main__":
    unittest.main()

