from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import profili_operativi


class ProfiliOperativiTest(unittest.TestCase):
    def test_assente_o_corrotto_fallisce_su_standard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            self.assertEqual(profili_operativi.carica(radice)["profilo"], "standard")
            percorso = profili_operativi.percorso_profilo(radice)
            percorso.parent.mkdir(parents=True)
            percorso.write_text("{rotto", encoding="utf-8")
            self.assertEqual(profili_operativi.carica(radice)["profilo"], "standard")

    def test_imposta_e_carica_sono_isolate_per_radice(self) -> None:
        with tempfile.TemporaryDirectory() as primo, tempfile.TemporaryDirectory() as secondo:
            salvato = profili_operativi.imposta(Path(primo), "brainstorming", revisione="r-1")
            self.assertEqual(salvato["profilo"], "brainstorming")
            self.assertEqual(profili_operativi.carica(Path(primo))["revisione"], "r-1")
            self.assertEqual(profili_operativi.carica(Path(secondo))["profilo"], "standard")

    def test_valore_sconosciuto_e_rifiutato_e_il_file_non_valido_fallisce_chiuso(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            with self.assertRaises(ValueError):
                profili_operativi.imposta(radice, "turbo")
            percorso = profili_operativi.percorso_profilo(radice)
            percorso.parent.mkdir(parents=True)
            percorso.write_text(json.dumps({"versione_schema": 1, "profilo": "turbo"}), encoding="utf-8")
            self.assertEqual(profili_operativi.carica(radice)["profilo"], "standard")

    def test_garanzie_e_dispatch_esprimono_lo_stato_reale_corrente(self) -> None:
        brainstorming = profili_operativi.imposta(Path(tempfile.mkdtemp()), "brainstorming")
        super_profilo = {**brainstorming, "profilo": "super"}
        smodata_profilo = {**brainstorming, "profilo": "smodata"}
        self.assertTrue(profili_operativi.dispatch_abilitato(brainstorming))
        self.assertTrue(profili_operativi.dispatch_abilitato(super_profilo))
        self.assertTrue(profili_operativi.dispatch_abilitato(smodata_profilo))
        self.assertEqual(profili_operativi.garanzie(brainstorming)["codex"], "prompt_only")
        for profilo in (super_profilo, smodata_profilo):
            with self.subTest(profilo=profilo["profilo"]):
                self.assertEqual(profili_operativi.garanzie(profilo)["claude"], "enforced")
                self.assertEqual(profili_operativi.garanzie(profilo)["codex"], "prompt_only")
                self.assertEqual(profili_operativi.garanzie(profilo)["gemini"], "prompt_only")

    def test_istruzione_hook_usa_il_profilo_della_radice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            profili_operativi.imposta(radice, "brainstorming")
            profilo = profili_operativi.carica(radice)
            self.assertIn("rispondi in bacheca", profili_operativi.istruzione_interattiva(profilo))
