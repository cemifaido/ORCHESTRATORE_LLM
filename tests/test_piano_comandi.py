from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import bacheca
import piano_comandi as pc


class PianoComandiTest(unittest.TestCase):
    def _bacheca(self, tmp: str) -> Path:
        return Path(tmp) / "messaggi.jsonl"

    def _crea(self, b: Path, **kw) -> str:
        opts = {"piano_id": "P", "passo_id": "s1", "descrizione": "d", "attore": "umano"}
        opts.update(kw)
        return pc.crea_passo(b, **opts)["thread_id"]

    def _piano(self, b: Path, tid: str) -> dict:
        piano = pc.mostra_piano(b, tid)
        assert piano is not None
        return piano

    def test_prendi_passo_e_secondo_tentativo_fallisce(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = self._bacheca(tmp)
            tid = self._crea(b, write_set=["bacheca.py"])
            self.assertEqual(pc.prendi_passo(b, tid, "s1", "codex")["esito"], "ok")
            secondo = pc.prendi_passo(b, tid, "s1", "gemini")
            self.assertEqual(secondo["esito"], "non_acquisibile")
            piano = self._piano(b, tid)
            self.assertEqual(piano["passi"]["s1"]["proprietario"], "codex")
            self.assertEqual(piano["passi"]["s1"]["versione"], 1)

    def test_prendi_passo_su_thread_senza_piano_o_passo_assente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = self._bacheca(tmp)
            bacheca.aggiungi_messaggio(b, bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="x", thread_id="T",
            ))
            self.assertEqual(pc.prendi_passo(b, "T", "s1", "codex")["esito"], "nessun_piano")
            tid = self._crea(b)
            self.assertEqual(pc.prendi_passo(b, tid, "sX", "codex")["esito"], "passo_assente")

    def test_idempotency_key_replay_non_riscrive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = self._bacheca(tmp)
            tid = self._crea(b)
            uno = pc.prendi_passo(b, tid, "s1", "codex", idempotency_key="k1")
            due = pc.prendi_passo(b, tid, "s1", "codex", idempotency_key="k1")
            self.assertEqual(uno["esito"], "ok")
            self.assertEqual(due["esito"], "gia_applicato")
            righe = b.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(righe), 2)  # crea + prendi, nessun terzo record

    def test_offri_passo_in_corso_propone_handoff_e_approvazione_trasferisce(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = self._bacheca(tmp)
            tid = self._crea(b)
            pc.prendi_passo(b, tid, "s1", "codex")
            self.assertEqual(pc.offri_passo(b, tid, "s1", "codex", "claude")["esito"], "ok")
            piano = self._piano(b, tid)
            self.assertEqual(piano["passi"]["s1"]["proprietario"], "codex")  # proposta, non trasferisce
            self.assertEqual(len(piano["handoff_aperti"]), 1)
            # un terzo non puo' approvare
            self.assertEqual(pc.approva_handoff(b, tid, "s1", "gemini")["esito"], "non_autorizzato")
            # il proprietario si'
            self.assertEqual(pc.approva_handoff(b, tid, "s1", "codex")["esito"], "ok")
            self.assertEqual(self._piano(b, tid)["passi"]["s1"]["proprietario"], "claude")

    def test_offri_passo_non_iniziato_delega_la_presa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = self._bacheca(tmp)
            tid = self._crea(b)
            self.assertEqual(pc.offri_passo(b, tid, "s1", "umano", "gemini")["esito"], "ok")
            piano = self._piano(b, tid)
            self.assertEqual(piano["passi"]["s1"]["proprietario"], "gemini")
            self.assertEqual(piano["passi"]["s1"]["stato"], "in_corso")

    def test_crea_passo_su_thread_esistente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = self._bacheca(tmp)
            tid = self._crea(b, passo_id="s1")
            pc.crea_passo(b, piano_id="P", passo_id="s2", descrizione="secondo",
                          attore="umano", thread_id=tid)
            self.assertEqual(sorted(self._piano(b, tid)["passi"]), ["s1", "s2"])


if __name__ == "__main__":
    unittest.main()
