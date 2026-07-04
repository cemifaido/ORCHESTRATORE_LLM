from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
