from __future__ import annotations

import unittest

import piano_overlap as po


class NormalizzaSetTest(unittest.TestCase):
    def test_normalizza_posix_e_case_fold(self) -> None:
        self.assertEqual(
            po.normalizza_set(["Src\\App.PY", "docs//Guida.md"]),
            ["docs/guida.md", "src/app.py"],
        )

    def test_rifiuta_non_deterministici(self) -> None:
        for cattivo in (
            ["/etc/passwd"], ["C:/x"], ["//share/x"], ["a/../b"], ["."], [".."],
            [""], ["  "], ["src/{a,b}.py"], ["src/!(x).py"], ["$HOME/x"], "non-una-lista",
            [123],
        ):
            self.assertIsNone(po.normalizza_set(cattivo), cattivo)

    def test_glob_portabili_ammessi(self) -> None:
        self.assertEqual(
            po.normalizza_set(["tests/**", "src/*.py", "a/b?.txt"]),
            ["a/b?.txt", "src/*.py", "tests/**"],
        )


class IntersecaTest(unittest.TestCase):
    def test_disgiunti_per_prefisso_letterale(self) -> None:
        self.assertEqual(po.interseca(["docs/**"], ["tests/**"]), po.DISGIUNTO)
        self.assertEqual(po.interseca(["src/a.py"], ["src/b.py"]), po.DISGIUNTO)

    def test_indeterminato_quando_il_wildcard_arriva_prima_del_mismatch(self) -> None:
        self.assertEqual(po.interseca(["docs/**"], ["docs/api.md"]), po.OVERLAP_O_INDETERMINATO)
        self.assertEqual(po.interseca(["*/x.py"], ["src/x.py"]), po.OVERLAP_O_INDETERMINATO)
        self.assertEqual(po.interseca(["a"], ["a/b"]), po.OVERLAP_O_INDETERMINATO)
        self.assertEqual(po.interseca(["postino.py"], ["postino.py"]), po.OVERLAP_O_INDETERMINATO)


class ValutaCollisioneTest(unittest.TestCase):
    def _passo(self, **kw) -> dict:
        base = {"id": "s", "proprietario": "codex", "stato": "in_corso", "write_set": [], "read_set": []}
        base.update(kw)
        return base

    def test_consentito_se_write_set_disgiunti(self) -> None:
        cand = self._passo(id="c", write_set=["static/interfaccia.js"])
        attivi = [self._passo(id="a", write_set=["postino.py"])]
        self.assertEqual(po.valuta_collisione(cand, attivi)["esito"], "consentito")

    def test_bloccato_write_x_write(self) -> None:
        cand = self._passo(id="c", write_set=["postino.py"])
        attivi = [self._passo(id="a", write_set=["postino.py", "bacheca.py"])]
        r = po.valuta_collisione(cand, attivi)
        self.assertEqual((r["esito"], r["motivo"], r["passo"]), ("bloccato", "write_x_write", "a"))

    def test_bloccato_write_x_read_ma_non_read_x_read(self) -> None:
        # candidato scrive cio' che l'attivo legge -> blocco
        cand = self._passo(id="c", write_set=["schema/messaggio.v1.json"])
        attivi = [self._passo(id="a", write_set=["bacheca.py"], read_set=["schema/messaggio.v1.json"])]
        self.assertEqual(po.valuta_collisione(cand, attivi)["motivo"], "write_x_read")
        # entrambi leggono lo stesso file, nessuno lo scrive -> consentito
        cand2 = self._passo(id="c", write_set=["dashboard_risvegli.py"], read_set=["schema/messaggio.v1.json"])
        attivi2 = [self._passo(id="a", write_set=["bacheca.py"], read_set=["schema/messaggio.v1.json"])]
        self.assertEqual(po.valuta_collisione(cand2, attivi2)["esito"], "consentito")

    def test_write_set_candidato_ambiguo_e_non_dispatchabile(self) -> None:
        cand = self._passo(id="c", write_set=["src/{a,b}.py"])
        self.assertEqual(po.valuta_collisione(cand, [])["esito"], "non_dispatchabile")

    def test_write_set_di_un_passo_attivo_ambiguo_e_non_dispatchabile(self) -> None:
        cand = self._passo(id="c", write_set=["x.py"])
        attivi = [self._passo(id="a", write_set=["$GEN/x"])]
        r = po.valuta_collisione(cand, attivi)
        self.assertEqual((r["esito"], r["passo"]), ("non_dispatchabile", "a"))


if __name__ == "__main__":
    unittest.main()
