from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import note_codice


class NoteCodiceTest(unittest.TestCase):
    def _radice(self, tmp: str) -> Path:
        r = Path(tmp)
        (r / "dati_locali" / "orchestrazione").mkdir(parents=True)
        return r

    def test_aggiungi_e_leggi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            (r / "mod.py").write_text("uno\ndue\ntre\nquattro\n", encoding="utf-8")
            nota = note_codice.aggiungi_nota(
                r, "mod.py", 2, 3, "gotcha su due/tre", "umano", simbolo="mod.py::f",
            )
            self.assertEqual(nota["ancora"]["percorso"], "mod.py")
            self.assertRegex(nota["ancora"]["hash_blocco"], r"^[0-9a-f]{40}$")
            note = note_codice.leggi_note(r)
            self.assertEqual(len(note), 1)
            self.assertEqual(note[0]["testo"], "gotcha su due/tre")

    def test_stato_segue_il_blocco(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            f = r / "mod.py"
            f.write_text("a\nb\nc\nd\n", encoding="utf-8")
            nota = note_codice.aggiungi_nota(r, "mod.py", 2, 3, "nota", "claude")
            self.assertEqual(note_codice.stato_nota(r, nota), note_codice.STATO_ATTIVA)
            f.write_text("a\nB!\nc\nd\n", encoding="utf-8")
            self.assertEqual(note_codice.stato_nota(r, nota), note_codice.STATO_DA_RIVEDERE)
            f.unlink()
            self.assertEqual(note_codice.stato_nota(r, nota), note_codice.STATO_ORFANA)

    def test_aggiornamento_stesso_id_vince_l_ultimo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            (r / "m.py").write_text("x\ny\nz\n", encoding="utf-8")
            note_codice.aggiungi_nota(r, "m.py", 1, 1, "vecchia", "umano", id_nota="n1")
            note_codice.aggiungi_nota(r, "m.py", 2, 2, "nuova", "umano", id_nota="n1")
            note = note_codice.leggi_note(r)
            self.assertEqual(len(note), 1)
            self.assertEqual(note[0]["testo"], "nuova")
            self.assertEqual(note[0]["ancora"]["riga_inizio"], 2)

    def test_rifiuta_ancora_a_righe_inesistenti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            (r / "m.py").write_text("una riga sola\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                note_codice.aggiungi_nota(r, "m.py", 5, 9, "nota", "umano")
            with self.assertRaises(ValueError):
                note_codice.aggiungi_nota(r, "assente.py", 1, 1, "nota", "umano")

    def test_rifiuta_percorso_non_sicuro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            for cattivo in ("/etc/passwd", "..\\x", "a/../b", "C:\\x"):
                with self.assertRaises(ValueError):
                    note_codice.aggiungi_nota(r, cattivo, 1, 1, "n", "umano")

    def test_contesto_hook_filtra_per_percorsi_ed_etichetta_lo_stato(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            (r / "a.py").write_text("aa\nbb\n", encoding="utf-8")
            (r / "b.py").write_text("cc\ndd\n", encoding="utf-8")
            note_codice.aggiungi_nota(r, "a.py", 1, 1, "nota A", "umano")
            nb = note_codice.aggiungi_nota(r, "b.py", 1, 1, "nota B", "umano")
            (r / "b.py").write_text("CC!\ndd\n", encoding="utf-8")

            solo_a = note_codice.contesto_hook(r, percorsi={"a.py"})
            self.assertIn("nota A", solo_a)
            self.assertNotIn("nota B", solo_a)

            tutte = note_codice.contesto_hook(r)
            self.assertIn("nota A", tutte)
            self.assertIn("[DA_RIVEDERE]", tutte)
            self.assertIn("non istruzioni", tutte)

            self.assertEqual(note_codice.contesto_hook(r, percorsi={"nessuno.py"}), "")
            _ = nb

    def test_riga_letta_da_disco_non_valida_solleva(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            note_codice.percorso_note(r).write_text('{"non": "una nota"}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                note_codice.leggi_note(r)


if __name__ == "__main__":
    unittest.main()
