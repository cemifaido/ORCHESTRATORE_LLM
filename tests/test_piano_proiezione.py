from __future__ import annotations

import unittest

import bacheca
import bacheca_proiezioni as bp


def _msg(thread_id: str, piano: dict) -> dict:
    return bacheca.costruisci_messaggio(
        mittente="umano", destinatari=["claude"], tipo="richiesta", testo="x",
        thread_id=thread_id, piano=piano,
    )


def _crea(pid: str, **campi) -> dict:
    return {"azione": "crea_passo", "piano_id": "P", "passo_id": pid, "campi": campi}


def _aggiorna(pid: str, pre: dict, **campi) -> dict:
    return {"azione": "aggiorna_passo", "piano_id": "P", "passo_id": pid,
            "precondizione": pre, "campi": campi}


class DerivaPianoTest(unittest.TestCase):
    def test_thread_senza_piano_ritorna_none(self) -> None:
        msgs = [bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="richiesta", testo="x", thread_id="T",
        )]
        self.assertIsNone(bp.deriva_piano(msgs, "T"))

    def test_crea_e_aggiorna_con_precondizione_giusta(self) -> None:
        msgs = [
            _msg("T", _crea("s1", descrizione="modello", write_set=["bacheca.py"])),
            _msg("T", _aggiorna("s1", {"versione": 0, "stato": "non_iniziato"},
                                proprietario="codex", stato="in_corso")),
        ]
        piano = bp.deriva_piano(msgs, "T")
        assert piano is not None
        s1 = piano["passi"]["s1"]
        self.assertEqual((s1["proprietario"], s1["stato"], s1["versione"]), ("codex", "in_corso", 1))
        self.assertEqual([p["id"] for p in bp.passi_in_corso(piano)], ["s1"])

    def test_precondizione_sbagliata_e_race_persa_ignorata(self) -> None:
        msgs = [
            _msg("T", _crea("s1", descrizione="d")),
            _msg("T", _aggiorna("s1", {"versione": 0}, proprietario="codex", stato="in_corso")),
            # secondo agente con precondizione ormai stantia (versione 0, ma ora e' 1)
            _msg("T", _aggiorna("s1", {"versione": 0}, proprietario="gemini")),
        ]
        piano = bp.deriva_piano(msgs, "T")
        assert piano is not None
        self.assertEqual(piano["passi"]["s1"]["proprietario"], "codex")
        self.assertEqual(piano["passi"]["s1"]["versione"], 1)

    def test_crea_passo_su_id_esistente_ignorato(self) -> None:
        msgs = [
            _msg("T", _crea("s1", descrizione="prima")),
            _msg("T", _crea("s1", descrizione="seconda", proprietario="gemini")),
        ]
        piano = bp.deriva_piano(msgs, "T")
        assert piano is not None
        self.assertEqual(piano["passi"]["s1"]["descrizione"], "prima")
        self.assertIsNone(piano["passi"]["s1"]["proprietario"])

    def test_handoff_solo_con_approvazione_esplicita(self) -> None:
        msgs = [
            _msg("T", _crea("s1", descrizione="d")),
            _msg("T", _aggiorna("s1", {"versione": 0}, proprietario="codex", stato="in_corso")),
            _msg("T", {"azione": "proponi_handoff", "piano_id": "P", "passo_id": "s1",
                       "precondizione": {"versione": 1}, "campi": {"proprietario": "claude"}}),
        ]
        piano = bp.deriva_piano(msgs, "T")
        assert piano is not None
        self.assertEqual(piano["passi"]["s1"]["proprietario"], "codex")  # proposta non trasferisce
        self.assertEqual(len(piano["handoff_aperti"]), 1)

        msgs.append(_msg("T", {"azione": "approva_handoff", "piano_id": "P", "passo_id": "s1",
                               "precondizione": {"versione": 1}}))
        piano = bp.deriva_piano(msgs, "T")
        assert piano is not None
        self.assertEqual(piano["passi"]["s1"]["proprietario"], "claude")
        self.assertEqual(piano["handoff_aperti"], [])

    def test_eventi_di_un_altro_piano_id_sono_rumore(self) -> None:
        msgs = [
            _msg("T", _crea("s1", descrizione="buono")),
            _msg("T", {"azione": "crea_passo", "piano_id": "ALTRO", "passo_id": "sx",
                       "campi": {"descrizione": "estraneo"}}),
        ]
        piano = bp.deriva_piano(msgs, "T")
        assert piano is not None
        self.assertEqual(list(piano["passi"]), ["s1"])


if __name__ == "__main__":
    unittest.main()
