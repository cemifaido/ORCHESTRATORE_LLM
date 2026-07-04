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
            for regola in ["registro.py", "sentinella.py", "genera_cruscotto.py", "config/comandi.json"]:
                self.assertIn(regola, contenuto)

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


if __name__ == "__main__":
    unittest.main()
