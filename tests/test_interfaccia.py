from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import interfaccia


class IntegraProgettoTest(unittest.TestCase):
    def test_integra_progetto_aggiorna_gitignore_del_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)

            gitignore_path = dest_path / ".gitignore"
            self.assertTrue(gitignore_path.exists())
            contenuto = gitignore_path.read_text(encoding="utf-8")
            for regola in ["registro.py", "sentinella.py", "genera_cruscotto.py", "config/comandi.json",
                           "requirements-orchestratore.txt"]:
                self.assertIn(regola, contenuto)

    def test_integra_progetto_scrive_manifest_dipendenze_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)

            manifest = dest_path / "requirements-orchestratore.txt"
            self.assertTrue(manifest.exists())
            contenuto = manifest.read_text(encoding="utf-8")
            self.assertIn("jsonschema", contenuto)

    def test_integra_progetto_non_duplica_regole_gitignore_se_rieseguito(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)
            interfaccia.integra_progetto(dest_path)

            contenuto = (dest_path / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(contenuto.count("registro.py"), 1)

    def test_integra_progetto_preserva_regole_gitignore_preesistenti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            (dest_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

            interfaccia.integra_progetto(dest_path)

            contenuto = (dest_path / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("node_modules/", contenuto)
            self.assertIn("registro.py", contenuto)


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


if __name__ == "__main__":
    unittest.main()
