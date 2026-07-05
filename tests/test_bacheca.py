from __future__ import annotations

import argparse
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import bacheca
from adattatori.litellm import MisurazioneLiteLLM


def _risposta_con_testo(testo: str) -> MagicMock:
    risposta = MagicMock()
    risposta.choices = [MagicMock()]
    risposta.choices[0].message.content = testo
    return risposta


def _misurazione_finta(token_totali: int = 400) -> MisurazioneLiteLLM:
    return MisurazioneLiteLLM(
        modello="qwen2.5-7b-instruct-q3_k_m.gguf", provider="locale", costo_usd=0.0,
        token_prompt=300, token_completion=token_totali - 300, token_totali=token_totali,
    )


class BachecaTest(unittest.TestCase):
    def messaggio_valido(self, **override) -> dict:
        base = bacheca.costruisci_messaggio(
            mittente="claude",
            destinatari=["codex"],
            tipo="richiesta",
            testo="Rivedi X",
        )
        base.update(override)
        return base

    # -- validazione schema ------------------------------------------------

    def test_valida_rifiuta_campi_extra(self) -> None:
        messaggio = self.messaggio_valido()
        messaggio["campo_non_previsto"] = True
        errori = bacheca.valida_messaggio(messaggio)
        self.assertTrue(any("campi non previsti" in errore for errore in errori))

    def test_valida_rifiuta_ttl_minuti_fuori_da_presa_in_carico(self) -> None:
        messaggio = self.messaggio_valido(tipo="richiesta", ttl_minuti=30)
        errori = bacheca.valida_messaggio(messaggio)
        self.assertTrue(errori, "ttl_minuti valorizzato su un tipo diverso da presa_in_carico deve fallire")

    def test_valida_accetta_ttl_minuti_su_presa_in_carico(self) -> None:
        messaggio = self.messaggio_valido(tipo="presa_in_carico", ttl_minuti=30)
        self.assertEqual(bacheca.valida_messaggio(messaggio), [])

    def test_valida_accetta_segnalazione_conflitto(self) -> None:
        messaggio = self.messaggio_valido(tipo="segnalazione_conflitto", destinatari=["umano"])
        self.assertEqual(bacheca.valida_messaggio(messaggio), [])

    # -- append-only ---------------------------------------------------------

    def test_aggiungi_e_leggi_messaggio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            bacheca.aggiungi_messaggio(percorso, self.messaggio_valido())
            messaggi = bacheca.leggi_messaggi(percorso)
            self.assertEqual(len(messaggi), 1)
            self.assertEqual(messaggi[0]["mittente"], "claude")

    def test_leggi_messaggi_su_file_assente_ritorna_vuoto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "non_esiste.jsonl"
            self.assertEqual(bacheca.leggi_messaggi(percorso), [])

    # -- stato globale derivato (event-sourcing) -----------------------------

    def test_stato_thread_aperto_su_richiesta_senza_seguito(self) -> None:
        m = self.messaggio_valido()
        self.assertEqual(bacheca.stato_thread([m], m["thread_id"]), "aperto")

    def test_stato_thread_chiuso_su_ultima_chiusura(self) -> None:
        richiesta = self.messaggio_valido()
        chiusura = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="chiusura",
            testo="ok", thread_id=richiesta["thread_id"],
        )
        stato = bacheca.stato_thread([richiesta, chiusura], richiesta["thread_id"])
        self.assertEqual(stato, "chiuso")

    def test_stato_thread_inesistente(self) -> None:
        self.assertEqual(bacheca.stato_thread([], "non-esiste"), "inesistente")

    # -- stato per destinatario: il caso ambiguo segnalato in revisione -----

    def test_stato_per_destinatario_thread_multiplo_solo_uno_risponde(self) -> None:
        """destinatari=[claude, codex]: se risponde solo claude, il thread e'
        globalmente 'risposto' ma codex deve restare 'pending' (RFC §3.3)."""
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude", "codex"], tipo="richiesta", testo="Criticate X",
        )
        risposta_claude = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="risposta",
            testo="fatto", thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, risposta_claude]

        self.assertEqual(bacheca.stato_thread(messaggi, richiesta["thread_id"]), "risposto")
        self.assertEqual(bacheca.stato_per_destinatario(messaggi, richiesta["thread_id"], "claude"), "resolved")
        self.assertEqual(bacheca.stato_per_destinatario(messaggi, richiesta["thread_id"], "codex"), "pending")

    def test_destinatari_pendenti_riflette_stato_per_destinatario(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude", "codex"], tipo="richiesta", testo="Criticate X",
        )
        risposta_claude = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="risposta",
            testo="fatto", thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, risposta_claude]
        self.assertEqual(bacheca.destinatari_pendenti(messaggi, richiesta["thread_id"]), ["codex"])

    def test_messaggi_aperti_per_agente_pending(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude", "codex"], tipo="richiesta", testo="Criticate X",
        )
        risposta_claude = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="risposta",
            testo="fatto", thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, risposta_claude]
        self.assertEqual(len(bacheca.messaggi_aperti_per(messaggi, "codex")), 1)
        self.assertEqual(bacheca.messaggi_aperti_per(messaggi, "claude"), [])

    def test_thread_chiuso_risolve_tutti_i_destinatari_pendenti(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude", "codex"], tipo="richiesta", testo="Criticate X",
        )
        chiusura = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude", "codex"], tipo="chiusura",
            testo="non serve piu'", thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, chiusura]
        self.assertEqual(bacheca.stato_per_destinatario(messaggi, richiesta["thread_id"], "codex"), "resolved")
        self.assertEqual(bacheca.destinatari_pendenti(messaggi, richiesta["thread_id"]), [])

    # -- verdetto_umano proiettato, non letto dal singolo record -------------

    def test_verdetto_umano_corrente_non_si_perde_con_messaggio_operativo_successivo(self) -> None:
        richiesta = self.messaggio_valido()
        approvazione = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="chiusura",
            testo="approvato", thread_id=richiesta["thread_id"], verdetto_umano="approvato",
        )
        # un messaggio operativo successivo con verdetto default non deve mascherare l'approvazione
        sintesi_successiva = bacheca.costruisci_messaggio(
            mittente="locale", destinatari=["umano"], tipo="sintesi",
            testo="riepilogo", thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, approvazione, sintesi_successiva]
        self.assertEqual(bacheca.verdetto_umano_corrente(messaggi, richiesta["thread_id"]), "approvato")

    def test_verdetto_umano_corrente_default_se_mai_revisionato(self) -> None:
        richiesta = self.messaggio_valido()
        self.assertEqual(bacheca.verdetto_umano_corrente([richiesta], richiesta["thread_id"]), "non_revisionato")

    # -- normalizzazione agente (correzione di parsing nota, RFC §3.4) -------

    def test_normalizza_agente_case_insensitive(self) -> None:
        self.assertEqual(bacheca.normalizza_agente("Gemini"), "gemini")

    def test_normalizza_agente_rifiuta_valore_sconosciuto(self) -> None:
        with self.assertRaises(ValueError):
            bacheca.normalizza_agente("chatgpt")

    # -- comando_aggiungi eredita thread_id da correla_a (bug reale corretto) --

    def test_comando_aggiungi_eredita_thread_id_da_correla_a(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            originale = self.messaggio_valido()
            bacheca.aggiungi_messaggio(percorso, originale)

            args = argparse.Namespace(
                bacheca=str(percorso),
                mittente="claude",
                destinatari="codex",
                tipo="sintesi",
                testo="rettifica",
                thread_id="",
                file_modificati="",
                riferimenti="",
                correla_a=originale["id_messaggio"],
                ttl_minuti=None,
                verdetto_umano="non_revisionato",
            )
            with redirect_stdout(io.StringIO()):
                bacheca.comando_aggiungi(args)

            messaggi = bacheca.leggi_messaggi(percorso)
            self.assertEqual(len(messaggi), 2)
            self.assertEqual(messaggi[1]["thread_id"], originale["thread_id"])

    def test_comando_aggiungi_senza_correla_a_apre_thread_nuovo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            args = argparse.Namespace(
                bacheca=str(percorso),
                mittente="claude",
                destinatari="codex",
                tipo="richiesta",
                testo="nuovo thread",
                thread_id="",
                file_modificati="",
                riferimenti="",
                correla_a="",
                ttl_minuti=None,
                verdetto_umano="non_revisionato",
            )
            with redirect_stdout(io.StringIO()):
                bacheca.comando_aggiungi(args)

            messaggi = bacheca.leggi_messaggi(percorso)
            self.assertEqual(messaggi[0]["thread_id"], messaggi[0]["id_messaggio"])

    def test_comando_aggiungi_rifiuta_correla_a_inesistente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            args = argparse.Namespace(
                bacheca=str(percorso),
                mittente="claude",
                destinatari="codex",
                tipo="sintesi",
                testo="rettifica",
                thread_id="",
                file_modificati="",
                riferimenti="",
                correla_a="messaggio-inesistente",
                ttl_minuti=None,
                verdetto_umano="non_revisionato",
            )
            with self.assertRaises(ValueError):
                bacheca.comando_aggiungi(args)

    # -- file_occupati: coordinamento cooperativo su file in carico --------

    def test_file_occupati_vuoto_senza_prese_in_carico(self) -> None:
        self.assertEqual(bacheca.file_occupati([self.messaggio_valido()]), {})

    def test_file_occupati_registra_file_in_carico(self) -> None:
        richiesta = self.messaggio_valido()
        presa = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["claude"], tipo="presa_in_carico",
            testo="ci lavoro io", thread_id=richiesta["thread_id"],
            file_modificati=["bacheca.py"], ttl_minuti=60,
        )
        occupati = bacheca.file_occupati([richiesta, presa])
        self.assertIn("bacheca.py", occupati)
        self.assertEqual(occupati["bacheca.py"]["agente"], "codex")

    def test_file_occupati_esclude_lease_scaduto(self) -> None:
        richiesta = self.messaggio_valido()
        presa = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["claude"], tipo="presa_in_carico",
            testo="ci lavoro io", thread_id=richiesta["thread_id"],
            file_modificati=["bacheca.py"], ttl_minuti=60,
        )
        adesso_futuro = bacheca._a_utc(presa["timestamp"]) + timedelta(hours=2)
        occupati = bacheca.file_occupati([richiesta, presa], adesso=adesso_futuro)
        self.assertEqual(occupati, {})

    def test_file_occupati_rilasciato_da_una_risposta(self) -> None:
        richiesta = self.messaggio_valido()
        presa = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["claude"], tipo="presa_in_carico",
            testo="ci lavoro io", thread_id=richiesta["thread_id"],
            file_modificati=["bacheca.py"], ttl_minuti=60,
        )
        risposta = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["claude"], tipo="risposta",
            testo="fatto", thread_id=richiesta["thread_id"],
        )
        occupati = bacheca.file_occupati([richiesta, presa, risposta])
        self.assertEqual(occupati, {})

    def test_comando_prendi_blocca_su_collisione_senza_forza(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["codex", "claude"], tipo="richiesta", testo="Sistema X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            args_codex = argparse.Namespace(
                bacheca=str(percorso), thread_id=richiesta["thread_id"], agente="codex",
                destinatari="", ttl_minuti=60, testo="", file_modificati="bacheca.py", forza=False,
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(bacheca.comando_prendi(args_codex), 0)

            args_claude = argparse.Namespace(
                bacheca=str(percorso), thread_id=richiesta["thread_id"], agente="claude",
                destinatari="", ttl_minuti=60, testo="", file_modificati="bacheca.py", forza=False,
            )
            with redirect_stdout(io.StringIO()):
                esito = bacheca.comando_prendi(args_claude)
            self.assertEqual(esito, 1, "deve bloccare: bacheca.py e' gia' in carico a codex")

    def test_comando_prendi_procede_con_forza_e_registra_il_conflitto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["codex", "claude"], tipo="richiesta", testo="Sistema X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            args_codex = argparse.Namespace(
                bacheca=str(percorso), thread_id=richiesta["thread_id"], agente="codex",
                destinatari="", ttl_minuti=60, testo="", file_modificati="bacheca.py", forza=False,
            )
            with redirect_stdout(io.StringIO()):
                bacheca.comando_prendi(args_codex)

            args_claude = argparse.Namespace(
                bacheca=str(percorso), thread_id=richiesta["thread_id"], agente="claude",
                destinatari="", ttl_minuti=60, testo="", file_modificati="bacheca.py", forza=True,
            )
            with redirect_stdout(io.StringIO()):
                esito = bacheca.comando_prendi(args_claude)
            self.assertEqual(esito, 0)

            messaggi = bacheca.leggi_messaggi(percorso)
            ultimo = messaggi[-1]
            self.assertTrue(ultimo["metadati"]["forzato_su_conflitto"])
            self.assertIn("bacheca.py", ultimo["metadati"]["occupato_da"])

    def test_comando_prendi_rifiuta_thread_inesistente_anche_con_destinatari(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            args = argparse.Namespace(
                bacheca=str(percorso), thread_id="thread-inesistente", agente="codex",
                destinatari="umano", ttl_minuti=60, testo="", file_modificati="", forza=False,
            )
            with self.assertRaises(ValueError):
                bacheca.comando_prendi(args)

    # -- checkpoint: non cambia lo stato globale, ma rende pending i destinatari --

    def test_checkpoint_non_cambia_stato_globale_thread_preso_in_carico(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["codex"], tipo="richiesta", testo="Sistema X",
        )
        presa = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["umano"], tipo="presa_in_carico",
            testo="ci lavoro", thread_id=richiesta["thread_id"],
            file_modificati=["bacheca.py"], ttl_minuti=60,
        )
        checkpoint = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["umano"], tipo="checkpoint",
            testo="CHECKPOINT: a meta' strada", thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, presa, checkpoint]
        self.assertEqual(bacheca.stato_thread(messaggi, richiesta["thread_id"]), "preso_in_carico")

    def test_stato_per_destinatario_usa_ordine_non_timestamp_a_parita_di_secondo(self) -> None:
        """Regressione: adesso_utc() ha precisione al secondo, quindi due messaggi
        scritti nello stesso secondo hanno timestamp IDENTICI. Un confronto ">" fra
        stringhe uguali e' sempre falso e sbaglierebbe verso 'resolved' anche
        quando il secondo messaggio (per ordine reale di scrittura) dovrebbe
        rendere 'pending' il destinatario."""
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["codex"], tipo="richiesta", testo="Sistema X",
        )
        presa = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["umano"], tipo="presa_in_carico",
            testo="ci lavoro", thread_id=richiesta["thread_id"],
        )
        checkpoint = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["umano"], tipo="checkpoint",
            testo="CHECKPOINT", thread_id=richiesta["thread_id"],
        )
        # Forza timestamp identici (stesso secondo), indipendentemente da quanto
        # veloce gira la macchina che esegue il test.
        stesso_timestamp = richiesta["timestamp"]
        presa["timestamp"] = stesso_timestamp
        checkpoint["timestamp"] = stesso_timestamp
        messaggi = [richiesta, presa, checkpoint]
        self.assertEqual(bacheca.stato_per_destinatario(messaggi, richiesta["thread_id"], "umano"), "pending")

    def test_checkpoint_rende_pending_i_propri_destinatari(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["codex"], tipo="richiesta", testo="Sistema X",
        )
        presa = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["umano"], tipo="presa_in_carico",
            testo="ci lavoro", thread_id=richiesta["thread_id"], ttl_minuti=60,
        )
        checkpoint = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["umano"], tipo="checkpoint",
            testo="CHECKPOINT", thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, presa, checkpoint]
        self.assertEqual(bacheca.stato_per_destinatario(messaggi, richiesta["thread_id"], "umano"), "pending")

    def test_file_occupati_ignora_checkpoint_successivo_alla_presa_in_carico(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["codex"], tipo="richiesta", testo="Sistema X",
        )
        presa = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["umano"], tipo="presa_in_carico",
            testo="ci lavoro", thread_id=richiesta["thread_id"],
            file_modificati=["bacheca.py"], ttl_minuti=60,
        )
        checkpoint = bacheca.costruisci_messaggio(
            mittente="codex", destinatari=["umano"], tipo="checkpoint",
            testo="CHECKPOINT", thread_id=richiesta["thread_id"],
        )
        occupati = bacheca.file_occupati([richiesta, presa, checkpoint])
        self.assertIn("bacheca.py", occupati)
        self.assertEqual(occupati["bacheca.py"]["agente"], "codex")

    def test_comando_checkpoint_scrive_template_e_non_chiude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["codex"], tipo="richiesta", testo="Sistema X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            args = argparse.Namespace(
                bacheca=str(percorso), thread_id=richiesta["thread_id"], agente="codex",
                destinatari="", obiettivo="Sistema X", stato_attuale="meta' fatto",
                file_modificati="bacheca.py", manca="test", test="non eseguiti",
                rischi="nessuno", prossimo_passo="finire i test",
            )
            with redirect_stdout(io.StringIO()):
                esito = bacheca.comando_checkpoint(args)
            self.assertEqual(esito, 0)
            messaggi = bacheca.leggi_messaggi(percorso)
            self.assertEqual(messaggi[-1]["tipo"], "checkpoint")
            self.assertIn("Obiettivo: Sistema X", messaggi[-1]["testo"])
            self.assertEqual(bacheca.stato_thread(messaggi, richiesta["thread_id"]), "aperto")

    def test_comando_checkpoint_rifiuta_thread_inesistente_anche_con_destinatari(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            args = argparse.Namespace(
                bacheca=str(percorso), thread_id="thread-inesistente", agente="codex",
                destinatari="umano", obiettivo="", stato_attuale="", file_modificati="",
                manca="", test="", rischi="", prossimo_passo="",
            )
            with self.assertRaises(ValueError):
                bacheca.comando_checkpoint(args)

    def test_comando_chiudi_rifiuta_thread_inesistente_anche_con_destinatari(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            args = argparse.Namespace(
                bacheca=str(percorso), thread_id="thread-inesistente", mittente="codex",
                destinatari="umano", testo="chiudo",
            )
            with self.assertRaises(ValueError):
                bacheca.comando_chiudi(args)

    # -- ripresa / emergenza -------------------------------------------------

    def test_comando_ripresa_senza_thread_aperti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            args = argparse.Namespace(bacheca=str(percorso))
            buf = io.StringIO()
            with redirect_stdout(buf):
                esito = bacheca.comando_ripresa(args)
            self.assertEqual(esito, 0)
            self.assertIn("Nessun thread aperto", buf.getvalue())

    def test_comando_ripresa_elenca_thread_ancora_aperto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["codex"], tipo="richiesta", testo="Sistema X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            args = argparse.Namespace(bacheca=str(percorso))
            buf = io.StringIO()
            with redirect_stdout(buf):
                bacheca.comando_ripresa(args)
            self.assertIn(richiesta["thread_id"][:8], buf.getvalue())

    def test_comando_emergenza_scrive_checkpoint_e_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            args = argparse.Namespace(bacheca=str(percorso), testo="sto spegnendo il portatile")
            with redirect_stdout(io.StringIO()):
                esito = bacheca.comando_emergenza(args)
            self.assertEqual(esito, 0)

            messaggi = bacheca.leggi_messaggi(percorso)
            self.assertEqual(len(messaggi), 1)
            self.assertEqual(messaggi[0]["tipo"], "checkpoint")
            self.assertEqual(messaggi[0]["mittente"], "umano")
            self.assertTrue(messaggi[0]["metadati"]["emergenza"])

            snapshot = Path(tmp) / "ultimo_checkpoint_emergenza.txt"
            self.assertTrue(snapshot.exists())
            self.assertIn("sto spegnendo il portatile", snapshot.read_text(encoding="utf-8"))

    # -- sintetizza: unico comando che chiama il modello locale --------------

    @patch("bacheca.litellm.completamento_locale")
    def test_sintetizza_thread_senza_conflitto(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (
            _risposta_con_testo('{"sintesi": "Claude chiede a Codex una review.", "conflitto": null}'),
            _misurazione_finta(),
        )
        richiesta = self.messaggio_valido()
        risultato = bacheca.sintetizza_thread([richiesta], richiesta["thread_id"])
        self.assertTrue(risultato["ok"])
        self.assertEqual(risultato["sintesi"], "Claude chiede a Codex una review.")
        self.assertIsNone(risultato["conflitto"])
        self.assertEqual(risultato["token_totali"], 400)

    @patch("bacheca.litellm.completamento_locale")
    def test_sintetizza_thread_rileva_conflitto(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (
            _risposta_con_testo('{"sintesi": "Esiti opposti sullo stesso test.", "conflitto": "Claude dice passa, Codex dice fallisce."}'),
            _misurazione_finta(),
        )
        richiesta = self.messaggio_valido()
        risultato = bacheca.sintetizza_thread([richiesta], richiesta["thread_id"])
        self.assertTrue(risultato["ok"])
        self.assertEqual(risultato["conflitto"], "Claude dice passa, Codex dice fallisce.")

    @patch("bacheca.litellm.completamento_locale")
    def test_sintetizza_thread_tratta_stringa_null_come_nessun_conflitto(self, mock_completamento: MagicMock) -> None:
        """Correzione di parsing nota (RFC §3.4): il modello a volte restituisce la
        stringa "null" invece del null JSON vero."""
        mock_completamento.return_value = (
            _risposta_con_testo('{"sintesi": "Tutto ok.", "conflitto": "null"}'),
            _misurazione_finta(),
        )
        richiesta = self.messaggio_valido()
        risultato = bacheca.sintetizza_thread([richiesta], richiesta["thread_id"])
        self.assertIsNone(risultato["conflitto"])

    @patch("bacheca.litellm.completamento_locale")
    def test_sintetizza_thread_modello_non_raggiungibile(self, mock_completamento: MagicMock) -> None:
        mock_completamento.side_effect = ConnectionError("server non risponde")
        richiesta = self.messaggio_valido()
        risultato = bacheca.sintetizza_thread([richiesta], richiesta["thread_id"])
        self.assertFalse(risultato["ok"])
        self.assertIn("non raggiungibile", risultato["errore"])

    @patch("bacheca.litellm.completamento_locale")
    def test_sintetizza_thread_risposta_non_json_non_crasha(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (_risposta_con_testo("non sono json"), _misurazione_finta())
        richiesta = self.messaggio_valido()
        risultato = bacheca.sintetizza_thread([richiesta], richiesta["thread_id"])
        self.assertFalse(risultato["ok"])
        self.assertIn("non interpretabile", risultato["errore"])

    @patch("bacheca.litellm.completamento_locale")
    def test_comando_sintetizza_scrive_segnalazione_conflitto(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (
            _risposta_con_testo('{"sintesi": "Esiti opposti.", "conflitto": "Claude vs Codex sullo stesso test."}'),
            _misurazione_finta(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude", "codex"], tipo="richiesta", testo="Sistema X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            args = argparse.Namespace(bacheca=str(percorso), thread_id=richiesta["thread_id"], modello="")
            with redirect_stdout(io.StringIO()):
                esito = bacheca.comando_sintetizza(args)
            self.assertEqual(esito, 0)

            messaggi = bacheca.leggi_messaggi(percorso)
            ultimo = messaggi[-1]
            self.assertEqual(ultimo["tipo"], "segnalazione_conflitto")
            self.assertEqual(ultimo["mittente"], "locale")
            self.assertIn("umano", ultimo["destinatari"])
            self.assertEqual(ultimo["metadati"]["fonte"], "locale")

    @patch("bacheca.litellm.completamento_locale")
    def test_comando_sintetizza_scrive_sintesi_senza_conflitto(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (
            _risposta_con_testo('{"sintesi": "Tutto in ordine.", "conflitto": null}'),
            _misurazione_finta(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Sistema X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            args = argparse.Namespace(bacheca=str(percorso), thread_id=richiesta["thread_id"], modello="")
            with redirect_stdout(io.StringIO()):
                esito = bacheca.comando_sintetizza(args)
            self.assertEqual(esito, 0)

            messaggi = bacheca.leggi_messaggi(percorso)
            ultimo = messaggi[-1]
            self.assertEqual(ultimo["tipo"], "sintesi")
            self.assertEqual(ultimo["mittente"], "locale")

    def test_comando_sintetizza_thread_inesistente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            args = argparse.Namespace(bacheca=str(percorso), thread_id="non-esiste", modello="")
            with redirect_stdout(io.StringIO()):
                esito = bacheca.comando_sintetizza(args)
            self.assertEqual(esito, 1)
            self.assertEqual(bacheca.leggi_messaggi(percorso), [])

    @patch("bacheca.litellm.completamento_locale")
    def test_comando_sintetizza_non_scrive_nulla_se_modello_non_raggiungibile(self, mock_completamento: MagicMock) -> None:
        mock_completamento.side_effect = ConnectionError("server non risponde")
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Sistema X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            args = argparse.Namespace(bacheca=str(percorso), thread_id=richiesta["thread_id"], modello="")
            with redirect_stdout(io.StringIO()):
                esito = bacheca.comando_sintetizza(args)
            self.assertEqual(esito, 1)
            self.assertEqual(len(bacheca.leggi_messaggi(percorso)), 1)  # solo la richiesta originale

    # -- leggi_messaggi_progetto: lettura difensiva per la dashboard --------

    def test_leggi_messaggi_progetto_senza_bacheca(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            messaggi, errore = bacheca.leggi_messaggi_progetto(Path(tmp))
            self.assertEqual(messaggi, [])
            self.assertIsNone(errore)

    def test_leggi_messaggi_progetto_normale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso_progetto = Path(tmp)
            percorso_messaggi = percorso_progetto / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
            bacheca.aggiungi_messaggio(percorso_messaggi, self.messaggio_valido())
            messaggi, errore = bacheca.leggi_messaggi_progetto(percorso_progetto)
            self.assertEqual(len(messaggi), 1)
            self.assertIsNone(errore)

    def test_leggi_messaggi_progetto_bacheca_corrotta_segnala_errore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso_progetto = Path(tmp)
            percorso_messaggi = percorso_progetto / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
            percorso_messaggi.parent.mkdir(parents=True, exist_ok=True)
            percorso_messaggi.write_text("questa non e' una riga json valida\n", encoding="utf-8")
            messaggi, errore = bacheca.leggi_messaggi_progetto(percorso_progetto)
            self.assertEqual(messaggi, [])
            assert errore is not None
            self.assertIn("corrotta", errore)


if __name__ == "__main__":
    unittest.main()
