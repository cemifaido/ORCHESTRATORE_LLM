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


class ValutaDispatchPianoTest(unittest.TestCase):
    """S14.3 slice b: il gancio che dashboard_risvegli consulta prima del dispatch."""

    def _msg(self, piano: dict, *, ts: str, thread: str = "T") -> dict:
        return {"thread_id": thread, "timestamp": ts, "mittente": "umano",
                "destinatari": ["codex"], "piano": piano}

    def _crea(self, passo_id: str, *, write_set: list[str], ts: str) -> dict:
        return self._msg({
            "azione": "crea_passo", "piano_id": "P", "passo_id": passo_id,
            "attore": "umano", "campi": {"descrizione": passo_id, "write_set": write_set},
        }, ts=ts)

    def _prendi(self, passo_id: str, attore: str, *, ts: str) -> dict:
        return self._msg({
            "azione": "aggiorna_passo", "piano_id": "P", "passo_id": passo_id,
            "attore": attore, "precondizione": {"versione": 0, "stato": "non_iniziato"},
            "campi": {"proprietario": attore, "stato": "in_corso"},
        }, ts=ts)

    def test_nessun_piano_quando_il_thread_non_ne_ha(self) -> None:
        msgs = [{"thread_id": "T", "timestamp": "1", "mittente": "umano",
                 "destinatari": ["codex"], "testo": "x"}]
        self.assertEqual(po.valuta_dispatch_piano(msgs, "T", "codex")["esito"], "nessun_piano")

    def test_nessun_passo_se_agente_non_possiede_niente_in_corso(self) -> None:
        msgs = [self._crea("s1", write_set=["postino.py"], ts="1"),
                self._prendi("s1", "gemini", ts="2")]
        self.assertEqual(po.valuta_dispatch_piano(msgs, "T", "codex")["esito"], "nessun_passo")

    def test_consentito_se_i_passi_in_corso_sono_disgiunti(self) -> None:
        msgs = [
            self._crea("s1", write_set=["postino.py"], ts="1"),
            self._crea("s2", write_set=["static/app.js"], ts="2"),
            self._prendi("s1", "codex", ts="3"),
            self._prendi("s2", "gemini", ts="4"),
        ]
        self.assertEqual(po.valuta_dispatch_piano(msgs, "T", "codex")["esito"], "consentito")

    def test_bloccato_se_il_passo_dell_agente_collide_con_quello_di_un_altro(self) -> None:
        msgs = [
            self._crea("s1", write_set=["bacheca.py"], ts="1"),
            self._crea("s2", write_set=["bacheca.py"], ts="2"),
            self._prendi("s1", "codex", ts="3"),
            self._prendi("s2", "gemini", ts="4"),
        ]
        r = po.valuta_dispatch_piano(msgs, "T", "codex")
        self.assertEqual(r["esito"], "bloccato")
        self.assertEqual(r["passo_candidato"], "s1")
        self.assertEqual(r["passo"], "s2")
        self.assertEqual(r["proprietario"], "gemini")

    def test_un_passo_non_collide_con_se_stesso(self) -> None:
        msgs = [self._crea("s1", write_set=["postino.py"], ts="1"),
                self._prendi("s1", "codex", ts="2")]
        self.assertEqual(po.valuta_dispatch_piano(msgs, "T", "codex")["esito"], "consentito")


if __name__ == "__main__":
    unittest.main()
