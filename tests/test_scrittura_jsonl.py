from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import scrittura_jsonl


def _scrivi_da_processo(percorso_str: str, indice: int) -> None:
    """Modulo-level: deve essere picklabile per multiprocessing su Windows
    (spawn), una closure locale non lo sarebbe."""
    scrittura_jsonl.aggiungi_riga_jsonl(Path(percorso_str), {"indice": indice})


class AggiungiRigaJsonlTest(unittest.TestCase):
    def test_scrive_una_riga_json_valida(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"a": 1, "b": "x"})

            righe = percorso.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(righe), 1)
            self.assertEqual(json.loads(righe[0]), {"a": 1, "b": "x"})

    def test_crea_le_cartelle_mancanti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "a" / "b" / "dati.jsonl"
            scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"x": 1})
            self.assertTrue(percorso.exists())

    def test_valida_blocca_la_scrittura_e_non_crea_il_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"

            def valida_sempre_falso(record: dict) -> list[str]:
                return ["campo obbligatorio mancante: x"]

            with self.assertRaises(ValueError):
                scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"a": 1}, valida=valida_sempre_falso)
            self.assertFalse(percorso.exists())

    def test_valida_che_passa_scrive_normalmente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"a": 1}, valida=lambda record: [])
            self.assertTrue(percorso.exists())

    def test_lock_rimosso_dopo_la_scrittura(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"a": 1})
            self.assertFalse(scrittura_jsonl._percorso_lock(percorso).exists())

    def test_transazione_jsonl_calcola_sotto_lock_e_none_non_scrive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"n": 0})

            def calcola() -> dict:
                # legge lo stato corrente DENTRO la transazione
                righe = percorso.read_text(encoding="utf-8").splitlines()
                return {"n": len(righe)}

            self.assertEqual(scrittura_jsonl.transazione_jsonl(percorso, calcola), {"n": 1})
            self.assertEqual(scrittura_jsonl.transazione_jsonl(percorso, lambda: None), None)
            self.assertEqual(len(percorso.read_text(encoding="utf-8").splitlines()), 2)
            self.assertFalse(scrittura_jsonl._percorso_lock(percorso).exists())

    def test_lock_abbandonato_viene_rimosso_dopo_il_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            percorso_lock = scrittura_jsonl._percorso_lock(percorso)
            percorso_lock.parent.mkdir(parents=True, exist_ok=True)
            percorso_lock.write_text("99999999", encoding="ascii")
            # Invecchia artificialmente il lock oltre il timeout, simulando un
            # processo morto senza pulire (kill -9 durante la scrittura).
            vecchio = time.time() - 100
            os.utime(percorso_lock, (vecchio, vecchio))

            scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"a": 1}, timeout_lock_secondi=1.0)

            self.assertTrue(percorso.exists())
            self.assertFalse(percorso_lock.exists())

    def test_lock_vecchio_di_un_pid_vivo_non_viene_rimosso(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            percorso_lock = scrittura_jsonl._percorso_lock(percorso)
            percorso_lock.write_text(str(os.getpid()), encoding="ascii")
            vecchio = time.time() - 100
            os.utime(percorso_lock, (vecchio, vecchio))

            with self.assertRaises(TimeoutError):
                scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"a": 1}, timeout_lock_secondi=0.05)

    def test_lock_attivo_fa_scadere_il_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            percorso_lock = scrittura_jsonl._percorso_lock(percorso)
            percorso_lock.parent.mkdir(parents=True, exist_ok=True)
            percorso_lock.touch()  # lock "fresco": non deve essere rimosso

            with self.assertRaises(TimeoutError):
                scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"a": 1}, timeout_lock_secondi=0.2)

    def test_scritture_concorrenti_non_perdono_ne_corrompono_righe(self) -> None:
        """Guardrail (contratto propedeutico a D2, stesso principio di H5 in
        postino.py, revisione sicurezza v3, 2026-08-25): N scrittori
        concorrenti devono produrre N righe valide, non un file corrotto o
        una riga persa per interleaving."""
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            n_thread = 20

            def scrivi(indice: int) -> None:
                scrittura_jsonl.aggiungi_riga_jsonl(percorso, {"indice": indice})

            thread = [threading.Thread(target=scrivi, args=(i,)) for i in range(n_thread)]
            for t in thread:
                t.start()
            for t in thread:
                t.join()

            righe = percorso.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(righe), n_thread)
            indici = sorted(json.loads(riga)["indice"] for riga in righe)
            self.assertEqual(indici, list(range(n_thread)))

    def test_scritture_concorrenti_multiprocesso_non_perdono_ne_corrompono_righe(self) -> None:
        """Guardrail (revisione Codex, 2026-08-26): il requisito reale e'
        multi-processo, non solo multi-thread nello stesso processo - thread
        diversi condividono lo stesso spazio di indirizzamento e lo stesso
        gestore di file descriptor, quindi non esercitano davvero la
        visibilita' cross-processo di os.O_CREAT | os.O_EXCL sul filesystem
        (il vero confine che serve proteggere: due CLI separate, es. due
        `registro.py aggiungi` lanciati nello stesso momento)."""
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "dati.jsonl"
            n_processi = 8

            processi = [
                multiprocessing.Process(target=_scrivi_da_processo, args=(str(percorso), i))
                for i in range(n_processi)
            ]
            for processo in processi:
                processo.start()
            for processo in processi:
                processo.join(timeout=30)
                self.assertEqual(processo.exitcode, 0)

            righe = percorso.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(righe), n_processi)
            indici = sorted(json.loads(riga)["indice"] for riga in righe)
            self.assertEqual(indici, list(range(n_processi)))


if __name__ == "__main__":
    unittest.main()
