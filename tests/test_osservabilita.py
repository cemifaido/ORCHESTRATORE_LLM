from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

import osservabilita


class LogEventoTest(unittest.TestCase):
    def test_scrive_una_riga_json_su_stderr_con_i_campi_base(self) -> None:
        with patch("sys.stderr", new_callable=io.StringIO) as stderr_finto:
            osservabilita.log_evento("modulo_test", "warning", "qualcosa non va")

        riga = json.loads(stderr_finto.getvalue().strip())
        self.assertEqual(riga["modulo"], "modulo_test")
        self.assertEqual(riga["livello"], "warning")
        self.assertEqual(riga["messaggio"], "qualcosa non va")
        self.assertIn("timestamp", riga)

    def test_contesto_extra_passa_nella_riga(self) -> None:
        with patch("sys.stderr", new_callable=io.StringIO) as stderr_finto:
            osservabilita.log_evento(
                "modulo_test", "info", "evento correlato",
                thread_id="t1", id_compito="c1", progetto_id="p1",
            )

        riga = json.loads(stderr_finto.getvalue().strip())
        self.assertEqual(riga["thread_id"], "t1")
        self.assertEqual(riga["id_compito"], "c1")
        self.assertEqual(riga["progetto_id"], "p1")

    def test_contesto_non_puo_sovrascrivere_timestamp(self) -> None:
        """Guardrail (revisione Codex, 2026-08-26): timestamp e' l'unico
        campo riservato senza un parametro posizionale a proteggerlo (modulo/
        livello/messaggio sono gia' parametri con nome: Python stesso rifiuta
        con TypeError un doppio valore per loro, prima ancora di entrare nella
        funzione). Senza il controllo esplicito, **contesto (spacchettato dopo
        i campi base) sovrascriverebbe timestamp in silenzio."""
        with self.assertRaises(ValueError):
            osservabilita.log_evento("m", "info", "msg", timestamp="2000-01-01T00:00:00Z")

    def test_contesto_con_modulo_o_livello_e_un_errore_di_chiamata_python(self) -> None:
        """modulo/livello/messaggio sono parametri con nome: passarli anche
        dentro **contesto e' un TypeError di Python, non arriva al controllo
        di CAMPI_RISERVATI - documentato qui perche' non e' ovvio a prima
        vista, non e' un buco nella protezione."""
        with self.assertRaises(TypeError):
            osservabilita.log_evento("modulo_vero", "info", "msg", modulo="modulo_falso")  # type: ignore[misc]
        with self.assertRaises(TypeError):
            osservabilita.log_evento("m", "info", "msg", livello="error")  # type: ignore[misc]

    def test_una_riga_per_chiamata(self) -> None:
        with patch("sys.stderr", new_callable=io.StringIO) as stderr_finto:
            osservabilita.log_evento("m", "info", "uno")
            osservabilita.log_evento("m", "info", "due")

        righe = stderr_finto.getvalue().strip().splitlines()
        self.assertEqual(len(righe), 2)
        self.assertEqual(json.loads(righe[0])["messaggio"], "uno")
        self.assertEqual(json.loads(righe[1])["messaggio"], "due")


if __name__ == "__main__":
    unittest.main()
