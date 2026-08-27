from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import utility.installa_hook


class InstallaHookTest(unittest.TestCase):
    def test_scrivi_hook_genera_pre_commit_corretto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            radice_progetto = Path("/finto/percorso/orchestratore")
            hook_file = tmp_path / "pre-commit"

            # Eseguiamo la scrittura dell'hook
            utility.installa_hook.scrivi_hook(radice_progetto, hook_file)

            self.assertTrue(hook_file.exists())
            contenuto = hook_file.read_text(encoding="utf-8")

            # Verifichiamo lo shebang e il percorso assoluto iniettato
            self.assertTrue(contenuto.startswith("#!/usr/bin/env python"))
            self.assertIn('Path(r"' + str(radice_progetto) + '")', contenuto)
            self.assertIn('"controllo_lint"', contenuto)
            self.assertIn('"controllo_tipi"', contenuto)
            self.assertIn('"controllo_complessita"', contenuto)
            self.assertIn('BRANCH_PROTETTI = {"main", "master"}', contenuto)

    def test_hook_reale_blocca_su_main_e_non_su_branch_feature(self) -> None:
        """Non solo il testo generato: esegue davvero l'hook dentro un repo
        git temporaneo, su main e su un branch feature, per provare il
        comportamento e non solo la presenza della stringa nel sorgente."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            subprocess.run(["git", "init", "-q", "-b", "main", str(radice)], check=True)
            subprocess.run(["git", "config", "user.email", "test@test.it"], cwd=str(radice), check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=str(radice), check=True)
            (radice / "seed.txt").write_text("seed", encoding="utf-8")
            subprocess.run(["git", "add", "seed.txt"], cwd=str(radice), check=True)
            subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=str(radice), check=True)

            hook_file = radice / "pre-commit-test.py"
            utility.installa_hook.scrivi_hook(radice, hook_file)

            esito_main = subprocess.run(
                [sys.executable, str(hook_file)], cwd=str(radice), text=True, capture_output=True,
            )
            self.assertEqual(esito_main.returncode, 1)
            self.assertIn("[BLOCCATO]", esito_main.stdout)

            subprocess.run(["git", "checkout", "-q", "-b", "una-feature"], cwd=str(radice), check=True)
            esito_feature = subprocess.run(
                [sys.executable, str(hook_file)], cwd=str(radice), text=True, capture_output=True,
            )
            self.assertNotIn("[BLOCCATO]", esito_feature.stdout)


if __name__ == "__main__":
    unittest.main()
