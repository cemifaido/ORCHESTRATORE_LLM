from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import consegne_risveglio as cr


class ConsegneRisveglioTest(unittest.TestCase):
    def _radice(self, tmp: str) -> Path:
        r = Path(tmp)
        (r / "dati_locali" / "orchestrazione").mkdir(parents=True)
        return r

    def test_legacy_notificati_vale_attenzione_richiamata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            s = cr.stato_coppia(r, [], "claude", "m1", notificati={"claude": ["m1"]})
            self.assertEqual(s["stato"], cr.ATTENZIONE_RICHIAMATA)

    def test_coppia_sconosciuta_e_in_attesa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            self.assertEqual(cr.stato_coppia(r, [], "claude", "ignoto")["stato"], cr.IN_ATTESA)

    def test_progressione_attenzione_hook_preso(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            cr.registra_transizione(r, agente="codex", id_messaggio="m2",
                                    stato=cr.ATTENZIONE_RICHIAMATA, origine="watcher", canale="os_wake")
            self.assertEqual(cr.stato_coppia(r, [], "codex", "m2")["stato"], cr.ATTENZIONE_RICHIAMATA)
            cr.registra_contesto_hook(r, [("codex", "m2", "t2")])
            self.assertEqual(cr.stato_coppia(r, [], "codex", "m2")["stato"], cr.ACQUISITO_DA_HOOK)
            msgs = [{"mittente": "codex", "correla_a": "m2", "id_messaggio": "x", "thread_id": "t2"}]
            self.assertEqual(cr.stato_coppia(r, msgs, "codex", "m2")["stato"], cr.PRESO_IN_CARICO)

    def test_chiuso_senza_consegna_porta_il_motivo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            cr.registra_transizione(r, agente="gemini", id_messaggio="m3",
                                    stato=cr.CHIUSO_SENZA_CONSEGNA, origine="watcher",
                                    motivo="budget_giornaliero")
            s = cr.stato_coppia(r, [], "gemini", "m3")
            self.assertEqual(s["stato"], cr.CHIUSO_SENZA_CONSEGNA)
            self.assertEqual(s["motivo"], "budget_giornaliero")

    def test_prova_esterna_scavalca_la_rinuncia_del_watcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            cr.registra_transizione(r, agente="gemini", id_messaggio="m3",
                                    stato=cr.CHIUSO_SENZA_CONSEGNA, origine="watcher", motivo="tetto_thread")
            cr.registra_contesto_hook(r, [("gemini", "m3", "t3")])
            self.assertEqual(cr.stato_coppia(r, [], "gemini", "m3")["stato"], cr.ACQUISITO_DA_HOOK)
            msgs = [{"mittente": "gemini", "correla_a": "m3", "id_messaggio": "y", "thread_id": "t3"}]
            self.assertEqual(cr.stato_coppia(r, msgs, "gemini", "m3")["stato"], cr.PRESO_IN_CARICO)

    def test_transizioni_monotone_non_retrocedono(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            cr.registra_transizione(r, agente="claude", id_messaggio="m4",
                                    stato=cr.PRESO_IN_CARICO, origine="watcher_dispatch")
            cr.registra_transizione(r, agente="claude", id_messaggio="m4",
                                    stato=cr.ATTENZIONE_RICHIAMATA, origine="watcher")
            self.assertEqual(cr.stato_coppia(r, [], "claude", "m4")["stato"], cr.PRESO_IN_CARICO)

    def test_registra_contesto_hook_deduplica(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            self.assertEqual(cr.registra_contesto_hook(r, [("codex", "m2", "t2")]), 1)
            self.assertEqual(cr.registra_contesto_hook(r, [("codex", "m2", "t2")]), 0)

    def test_stato_non_valido_non_scrive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            self.assertIsNone(cr.registra_transizione(
                r, agente="claude", id_messaggio="m", stato="inventato", origine="x"))
            self.assertFalse(cr.percorso_log(r).exists())

    def test_reset_umano_azzera_il_log_precedente_ma_non_la_prova_bacheca(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            cr.registra_transizione(r, agente="codex", id_messaggio="m1",
                                    stato=cr.CHIUSO_SENZA_CONSEGNA, origine="watcher", motivo="tetto_thread")
            cr.registra_contesto_hook(r, [("codex", "m1", "t1")])
            cr.registra_reset(r, agente="codex", id_messaggio="m1", motivo="umano")
            # reset scollega da log precedente, notificati e hook
            s = cr.stato_coppia(r, [], "codex", "m1", notificati={"codex": ["m1"]})
            self.assertEqual(s["stato"], cr.IN_ATTESA)
            # una nuova attivita' dopo il reset conta
            cr.registra_transizione(r, agente="codex", id_messaggio="m1",
                                    stato=cr.ATTENZIONE_RICHIAMATA, origine="watcher")
            self.assertEqual(cr.stato_coppia(r, [], "codex", "m1")["stato"], cr.ATTENZIONE_RICHIAMATA)
            # ma se l'agente aveva davvero risposto, la prova di bacheca resta
            msgs = [{"mittente": "codex", "correla_a": "m1", "id_messaggio": "x", "thread_id": "t1"}]
            self.assertEqual(cr.stato_coppia(r, msgs, "codex", "m1")["stato"], cr.PRESO_IN_CARICO)

    def test_rigenera_notificati_dal_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            cr.registra_transizione(r, agente="codex", id_messaggio="a",
                                    stato=cr.ATTENZIONE_RICHIAMATA, origine="watcher")
            cr.registra_transizione(r, agente="gemini", id_messaggio="b",
                                    stato=cr.PRESO_IN_CARICO, origine="watcher_dispatch")
            cr.registra_reset(r, agente="codex", id_messaggio="a")  # torna in_attesa -> escluso
            nuovo = cr.rigenera_notificati(r, [])
            self.assertEqual(nuovo, {"gemini": ["b"]})

    def test_proietta_elenca_tutte_le_coppie_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = self._radice(tmp)
            cr.registra_transizione(r, agente="codex", id_messaggio="a",
                                    stato=cr.ATTENZIONE_RICHIAMATA, origine="watcher")
            cr.registra_contesto_hook(r, [("gemini", "b", "tb")])
            proiezione = cr.proietta(r, [], notificati={"claude": ["c"]})
            self.assertEqual(
                {v["stato"] for v in proiezione.values()},
                {cr.ATTENZIONE_RICHIAMATA, cr.ACQUISITO_DA_HOOK},
            )
            self.assertEqual(set(proiezione), {"codex:a", "gemini:b", "claude:c"})


if __name__ == "__main__":
    unittest.main()
