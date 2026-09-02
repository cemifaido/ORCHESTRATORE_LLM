from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

import bacheca
import bacheca_scritture as bs


class BachecaScrittureTest(unittest.TestCase):
    def _bacheca_con_thread(self, tmp: str) -> tuple[Path, dict]:
        percorso = Path(tmp) / "messaggi.jsonl"
        req = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="richiesta",
            testo="fai X", thread_id="T",
        )
        bacheca.aggiungi_messaggio(percorso, req)
        return percorso, req

    def test_rispondi_scrive_e_idempotenza_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._bacheca_con_thread(tmp)
            r1 = bs.rispondi(p, thread_id="T", mittente="claude", testo="fatto", idempotency_key="k")
            self.assertEqual(r1["esito"], "ok")
            r2 = bs.rispondi(p, thread_id="T", mittente="claude", testo="fatto", idempotency_key="k")
            self.assertEqual(r2["esito"], "gia_applicato")
            self.assertEqual(r2["id_messaggio"], r1["messaggio"]["id_messaggio"])
            self.assertEqual(len(p.read_text(encoding="utf-8").splitlines()), 2)  # niente doppione

    def test_rispondi_stessa_chiave_payload_diverso_e_conflitto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._bacheca_con_thread(tmp)
            bs.rispondi(p, thread_id="T", mittente="claude", testo="A", idempotency_key="k")
            r = bs.rispondi(p, thread_id="T", mittente="claude", testo="B", idempotency_key="k")
            self.assertEqual(r["esito"], "conflitto")
            self.assertEqual(len(p.read_text(encoding="utf-8").splitlines()), 2)

    def test_idempotenza_e_per_mittente(self) -> None:
        """La stessa chiave usata da due agenti diversi non collide."""
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._bacheca_con_thread(tmp)
            self.assertEqual(bs.rispondi(p, thread_id="T", mittente="claude", testo="x", idempotency_key="k")["esito"], "ok")
            self.assertEqual(bs.rispondi(p, thread_id="T", mittente="codex", testo="y", idempotency_key="k")["esito"], "ok")

    def test_rispondi_thread_inesistente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._bacheca_con_thread(tmp)
            self.assertEqual(
                bs.rispondi(p, thread_id="NOPE", mittente="claude", testo="x")["esito"],
                "thread_inesistente",
            )

    def test_prendi_con_correla_a_e_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p, req = self._bacheca_con_thread(tmp)
            r = bs.prendi(p, thread_id="T", agente="codex", correla_a=req["id_messaggio"], idempotency_key="p")
            self.assertEqual(r["esito"], "ok")
            self.assertEqual(r["messaggio"]["tipo"], "presa_in_carico")
            self.assertEqual(r["messaggio"]["correla_a"], req["id_messaggio"])
            self.assertEqual(bs.prendi(p, thread_id="T", agente="codex", correla_a=req["id_messaggio"], idempotency_key="p")["esito"], "gia_applicato")

    def test_prendi_correla_a_inesistente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._bacheca_con_thread(tmp)
            self.assertEqual(
                bs.prendi(p, thread_id="T", agente="codex", correla_a="fantasma")["esito"],
                "correla_a_inesistente",
            )

    def test_senza_chiave_ogni_chiamata_e_nuova(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._bacheca_con_thread(tmp)
            bs.rispondi(p, thread_id="T", mittente="claude", testo="uguale")
            bs.rispondi(p, thread_id="T", mittente="claude", testo="uguale")
            self.assertEqual(len(p.read_text(encoding="utf-8").splitlines()), 3)  # due risposte

    def test_retry_concorrenti_stessa_chiave_scrivono_una_volta_sola(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._bacheca_con_thread(tmp)
            esiti: list[str] = []

            def prova() -> None:
                esiti.append(bs.rispondi(p, thread_id="T", mittente="claude", testo="race", idempotency_key="k")["esito"])

            fili = [threading.Thread(target=prova) for _ in range(12)]
            for f in fili:
                f.start()
            for f in fili:
                f.join()

            self.assertEqual(esiti.count("ok"), 1)
            self.assertEqual(esiti.count("gia_applicato"), 11)
            self.assertEqual(len(p.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
