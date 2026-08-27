from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import bacheca
import bacheca_comandi
import bacheca_proiezioni
import bacheca_sintesi
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


class AgentiValidiUnicaFonteTest(unittest.TestCase):
    """D8 (revisione architetturale v3): AGENTI_VALIDI era duplicato alla
    lettera in bacheca.py e bacheca_comandi.py - ora entrambi lo re-esportano
    da bacheca_proiezioni.py, unica fonte. Questo test copre il rischio
    residuo: che quella fonte diverga in silenzio dagli enum equivalenti
    negli schema JSON (mittente/destinatari in messaggio.v2, agente in
    evento.v1) - nessuno dei tre puo' "importare" gli altri, quindi la
    garanzia e' un confronto esplicito, non l'assenza di duplicazione."""

    def setUp(self) -> None:
        radice = Path(__file__).resolve().parent.parent
        self.schema_messaggio = json.loads((radice / "schema" / "messaggio.v2.json").read_text(encoding="utf-8"))
        self.schema_evento = json.loads((radice / "schema" / "evento.v1.json").read_text(encoding="utf-8"))

    def test_bacheca_e_bacheca_comandi_ri_esportano_la_stessa_istanza(self) -> None:
        self.assertIs(bacheca.AGENTI_VALIDI, bacheca_proiezioni.AGENTI_VALIDI)
        self.assertIs(bacheca_comandi.AGENTI_VALIDI, bacheca_proiezioni.AGENTI_VALIDI)

    def test_coerente_con_enum_mittente_schema_messaggio_v2(self) -> None:
        enum_schema = self.schema_messaggio["properties"]["mittente"]["enum"]
        self.assertEqual(set(bacheca.AGENTI_VALIDI), set(enum_schema))

    def test_coerente_con_enum_agente_schema_evento_v1(self) -> None:
        enum_schema = self.schema_evento["properties"]["agente"]["enum"]
        self.assertEqual(set(bacheca.AGENTI_VALIDI), set(enum_schema))


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

    # -- protocollo "passo" (decisione congiunta umano/Codex/Gemini, 2026-08-27) -

    def test_marker_intento_riconosce_passo_e_passo_e_chiudo(self) -> None:
        self.assertEqual(bacheca_proiezioni.marker_intento("tutto ok\n- passo"), "apri")
        self.assertEqual(bacheca_proiezioni.marker_intento("tutto ok\n- passo e chiudo"), "chiudi")
        self.assertIsNone(bacheca_proiezioni.marker_intento("il prossimo passo e' fare X"))
        self.assertIsNone(bacheca_proiezioni.marker_intento("nessun marker qui"))
        self.assertIsNone(bacheca_proiezioni.marker_intento(""))

    def test_marker_intento_solo_ultima_riga_non_dentro_il_corpo(self) -> None:
        """Un 'passo' in mezzo alla prosa non deve mai fare match."""
        self.assertIsNone(bacheca_proiezioni.marker_intento("- passo e chiudo qui non ci arrivo\naltro testo"))
        self.assertEqual(bacheca_proiezioni.marker_intento("riga in mezzo con - passo\n- passo e chiudo"), "chiudi")

    def test_marker_passo_riapre_pendenza_anche_su_tipo_risposta(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["gemini"], tipo="richiesta", testo="Domanda iniziale",
        )
        risposta_con_rilancio = bacheca.costruisci_messaggio(
            mittente="gemini", destinatari=["umano"], tipo="risposta",
            testo="Ecco la risposta, ma mi serve conferma.\n- passo",
            thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, risposta_con_rilancio]
        # senza il marker questo sarebbe 'resolved' (tipo=risposta non riapre nulla)
        self.assertEqual(bacheca.stato_per_destinatario(messaggi, richiesta["thread_id"], "umano"), "pending")

    def test_marker_passo_e_chiudo_forza_chiusura_anche_su_richiesta_aperta(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["codex"], tipo="richiesta", testo="Fai X",
        )
        chiusura_informale = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["codex"], tipo="richiesta",
            testo="Anzi lascia stare, non serve piu'.\n- passo e chiudo",
            thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, chiusura_informale]
        # senza il marker resterebbe 'pending' (tipo=richiesta riapre sempre)
        self.assertEqual(bacheca.stato_per_destinatario(messaggi, richiesta["thread_id"], "codex"), "resolved")

    def test_senza_marker_comportamento_invariato(self) -> None:
        """Nessuna regressione: in assenza di marker vale solo TIPI_APERTURA."""
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude", "codex"], tipo="richiesta", testo="Criticate X",
        )
        risposta_claude = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="risposta",
            testo="fatto", thread_id=richiesta["thread_id"],
        )
        messaggi = [richiesta, risposta_claude]
        self.assertEqual(bacheca.destinatari_pendenti(messaggi, richiesta["thread_id"]), ["codex"])

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
    def test_sintetizza_thread_delimita_il_contenuto_non_fidato(self, mock_completamento: MagicMock) -> None:
        """Guardrail di sicurezza (revisione esterna, 2026-08-25, M4): il testo del
        thread deve arrivare al modello racchiuso fra delimitatori espliciti, non
        semplicemente concatenato al prompt."""
        mock_completamento.return_value = (
            _risposta_con_testo('{"sintesi": "ok", "conflitto": null}'), _misurazione_finta(),
        )
        richiesta = self.messaggio_valido()
        bacheca.sintetizza_thread([richiesta], richiesta["thread_id"])

        messaggi_inviati = mock_completamento.call_args.kwargs["messaggi"]
        ultimo_turno_utente = messaggi_inviati[-1]["content"]
        self.assertIn("<<<INIZIO_THREAD>>>", ultimo_turno_utente)
        self.assertIn("<<<FINE_THREAD>>>", ultimo_turno_utente)
        self.assertIn(richiesta["testo"], ultimo_turno_utente)

    def test_formatta_thread_per_dispatcher_tronca_oltre_il_limite(self) -> None:
        richiesta = self.messaggio_valido()
        richiesta["testo"] = "x" * (bacheca.LIMITE_CARATTERI_THREAD_PROMPT + 500)
        testo = bacheca._formatta_thread_per_dispatcher([richiesta])
        self.assertLessEqual(len(testo), bacheca.LIMITE_CARATTERI_THREAD_PROMPT + len("\n...[thread troncato]...") + 1)
        self.assertIn("[thread troncato]", testo)

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


class BachecaCliContractTest(unittest.TestCase):
    """Caratterizzazione del confine che il refactoring D2 deve conservare.

    I consumatori interni usano bacheca.py anche come libreria; la CLI e' inoltre
    chiamata dagli hook. Questi test fissano il contratto della facade prima che
    le responsabilita' vengano estratte in moduli dedicati.
    """

    def _esegui(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            esito = bacheca.main(argv)
        return esito, stdout.getvalue(), stderr.getvalue()

    def test_facade_mantiene_l_api_usata_dai_consumatori(self) -> None:
        # Inventario minimo delle funzioni oggi chiamate da interfaccia.py,
        # postino.py, orchestratore_brainstorming.py e dai loro test. Durante
        # l'estrazione possono diventare re-export, ma non sparire senza una
        # migrazione esplicita di tutti i chiamanti.
        nomi_pubblici = (
            "costruisci_messaggio", "aggiungi_messaggio", "leggi_messaggi",
            "leggi_messaggi_progetto", "stato_thread", "stato_per_destinatario",
            "destinatari_pendenti", "verdetto_umano_corrente",
            "checkpoint_ripristinabile_attivo", "riprese_pronte", "file_occupati",
            "messaggi_aperti_per", "sintetizza_thread", "main",
        )
        for nome in nomi_pubblici:
            self.assertTrue(callable(getattr(bacheca, nome, None)), nome)
        # interfaccia.py lo usa oggi; il lotto B potra' renderlo pubblico con un
        # nome migliore, ma fino ad allora deve restare un alias funzionante.
        self.assertTrue(callable(getattr(bacheca, "_messaggi_del_thread", None)))

    def test_facade_reesporta_le_proiezioni_pure_estratte(self) -> None:
        alias = {
            "_messaggi_del_thread": "messaggi_del_thread",
            "partecipanti_thread": "partecipanti_thread",
            "_ultimo_rilevante": "ultimo_rilevante",
            "stato_thread": "stato_thread",
            "stato_per_destinatario": "stato_per_destinatario",
            "destinatari_pendenti": "destinatari_pendenti",
            "verdetto_umano_corrente": "verdetto_umano_corrente",
            "checkpoint_ripristinabile_attivo": "checkpoint_ripristinabile_attivo",
            "riprese_pronte": "riprese_pronte",
            "_a_utc": "a_utc",
            "file_occupati": "file_occupati",
            "messaggi_aperti_per": "messaggi_aperti_per",
        }
        for nome_facade, nome_modulo in alias.items():
            self.assertIs(getattr(bacheca, nome_facade), getattr(bacheca_proiezioni, nome_modulo))

    def test_facade_reesporta_i_casi_uso_cli_estratti(self) -> None:
        nomi = (
            "comando_aggiungi", "comando_chiedi", "comando_prossimo",
            "comando_rispondi", "comando_prendi", "comando_occupati",
            "comando_checkpoint", "comando_ripresa", "comando_emergenza",
            "comando_sintetizza", "comando_chiudi", "comando_approva",
            "comando_respingi", "comando_stato", "comando_thread",
            "comando_riepilogo", "comando_valida",
        )
        for nome in nomi:
            self.assertIs(getattr(bacheca, nome), getattr(bacheca_comandi, nome))

    def test_facade_reesporta_il_confine_sintesi_estratto(self) -> None:
        self.assertIs(bacheca.sintetizza_thread, bacheca_sintesi.sintetizza_thread)
        self.assertIs(bacheca._formatta_thread_per_dispatcher, bacheca_sintesi.formatta_thread)
        self.assertIs(bacheca._delimita_thread_non_fidato, bacheca_sintesi.delimita_thread_non_fidato)

    def test_cli_rispondi_preserva_thread_e_destinatari_di_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude", "codex"],
                tipo="richiesta", testo="Rivedete il piano",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)

            esito, stdout, stderr = self._esegui([
                "--bacheca", str(percorso), "rispondi",
                "--correla-a", richiesta["id_messaggio"],
                "--mittente", "codex", "--testo", "Piano rivisto",
            ])

            self.assertEqual(esito, 0)
            self.assertEqual(stderr, "")
            risposta = json.loads(stdout)
            self.assertEqual(risposta["tipo"], "risposta")
            self.assertEqual(risposta["thread_id"], richiesta["thread_id"])
            self.assertEqual(risposta["correla_a"], richiesta["id_messaggio"])
            self.assertEqual(risposta["destinatari"], ["claude", "umano"])
            self.assertEqual(bacheca.leggi_messaggi(percorso)[-1], risposta)

    def test_cli_prossimo_hook_mantiene_evento_e_contesto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["codex"],
                tipo="richiesta", testo="Controlla la facciata",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)

            esito, stdout, stderr = self._esegui([
                "--bacheca", str(percorso), "prossimo", "--agente", "codex",
                "--formato", "hook", "--evento", "UserPromptSubmit",
            ])

            self.assertEqual(esito, 0)
            self.assertEqual(stderr, "")
            output = json.loads(stdout)
            hook = output["hookSpecificOutput"]
            self.assertEqual(hook["hookEventName"], "UserPromptSubmit")
            self.assertIn("Controlla la facciata", hook["additionalContext"])
            self.assertIn("Profilo operativo standard", hook["additionalContext"])

    def test_cli_prossimo_hook_antigravity_preinvocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["gemini"],
                tipo="richiesta", testo="Controlla hook antigravity",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)

            esito, stdout, stderr = self._esegui([
                "--bacheca", str(percorso), "prossimo", "--agente", "gemini",
                "--formato", "hook", "--evento", "PreInvocation",
            ])

            self.assertEqual(esito, 0)
            self.assertEqual(stderr, "")
            output = json.loads(stdout)
            self.assertIn("injectSteps", output)
            self.assertIn("Controlla hook antigravity", output["injectSteps"][0]["ephemeralMessage"])

    def test_cli_rispondi_su_correlazione_inesistente_non_scrive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            esito, stdout, stderr = self._esegui([
                "--bacheca", str(percorso), "rispondi", "--correla-a", "assente",
                "--mittente", "codex", "--testo", "non deve essere scritto",
            ])
            self.assertEqual(esito, 2)
            self.assertEqual(stdout, "")
            self.assertIn("nessun messaggio", stderr)
            self.assertEqual(bacheca.leggi_messaggi(percorso), [])


class RipresaV2Test(unittest.TestCase):
    """Checkpoint ripristinabile, schema messaggio.v2 (docs/RFC_MESSAGGIO_V2_RIPRESA.md)."""

    def ripresa_valida(self, **override) -> dict:
        base = {
            "attende": "umano",
            "oggetto_atteso": "verdetto umano sul commit di bacheca.py",
            "azioni_per_esito": {
                "approvato": "eseguire il commit e registrare l'evento",
                "respinto": "scartare le modifiche e riaprire il thread",
                "modifiche_richieste": "applicare le modifiche chieste e richiedere verdetto",
            },
            "contesto_minimo": {
                "thread_id": "da-sovrascrivere",
                "riferimenti": [],
                "comandi_consentiti": ["git commit", "python registro.py aggiungi"],
            },
        }
        base.update(override)
        return base

    def checkpoint_v2(self, thread_id: str, mittente: str = "claude", **override_ripresa) -> dict:
        ripresa = self.ripresa_valida(**override_ripresa)
        ripresa["contesto_minimo"] = dict(ripresa["contesto_minimo"], thread_id=thread_id)
        return bacheca.costruisci_messaggio(
            mittente=mittente, destinatari=["umano"], tipo="checkpoint",
            testo="CHECKPOINT sospeso in attesa di verdetto", thread_id=thread_id,
            ripresa=ripresa,
        )

    # -- costruzione e validazione per versione ------------------------------

    def test_costruisci_con_ripresa_produce_versione_2(self) -> None:
        m = self.checkpoint_v2("t-1")
        self.assertEqual(m["versione_schema"], 2)
        self.assertEqual(bacheca.valida_messaggio(m), [])

    def test_costruisci_senza_ripresa_resta_versione_1_senza_chiave(self) -> None:
        m = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["codex"], tipo="richiesta", testo="Rivedi X",
        )
        self.assertEqual(m["versione_schema"], 1)
        self.assertNotIn("ripresa", m)
        self.assertEqual(bacheca.valida_messaggio(m), [])

    def test_valida_rifiuta_versione_sconosciuta(self) -> None:
        m = self.checkpoint_v2("t-1")
        m["versione_schema"] = 3
        errori = bacheca.valida_messaggio(m)
        self.assertTrue(any("versione_schema non supportata" in e for e in errori))

    def test_valida_v1_rifiuta_chiave_ripresa(self) -> None:
        m = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="checkpoint", testo="cp",
        )
        m["ripresa"] = self.ripresa_valida()
        self.assertTrue(bacheca.valida_messaggio(m), "un v1 con 'ripresa' deve fallire, la v1 e' congelata")

    def test_valida_v2_rifiuta_ripresa_su_tipo_non_checkpoint(self) -> None:
        m = self.checkpoint_v2("t-1")
        m["tipo"] = "richiesta"
        self.assertTrue(bacheca.valida_messaggio(m))

    def test_valida_v2_rifiuta_attende_umano_senza_tutti_gli_esiti(self) -> None:
        m = self.checkpoint_v2(
            "t-1",
            azioni_per_esito={"approvato": "commit", "respinto": "scarta"},  # manca modifiche_richieste
        )
        self.assertTrue(bacheca.valida_messaggio(m))

    def test_valida_v2_rifiuta_ripresa_senza_contesto_minimo(self) -> None:
        m = self.checkpoint_v2("t-1")
        del m["ripresa"]["contesto_minimo"]
        self.assertTrue(bacheca.valida_messaggio(m))

    def test_valida_v2_accetta_attende_gate_con_esiti_liberi(self) -> None:
        m = self.checkpoint_v2(
            "t-1", attende="gate",
            oggetto_atteso="esito di sentinella.py test_servizi",
            azioni_per_esito={"superato": "procedi col commit", "fallito": "leggi l'output del gate"},
        )
        self.assertEqual(bacheca.valida_messaggio(m), [])

    def test_leggi_messaggi_misti_v1_e_v2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            bacheca.aggiungi_messaggio(percorso, self.checkpoint_v2(richiesta["thread_id"]))
            messaggi = bacheca.leggi_messaggi(percorso)
            self.assertEqual([m["versione_schema"] for m in messaggi], [1, 2])

    # -- checkpoint attivo: risolto/sostituito -------------------------------

    def test_checkpoint_attivo_e_ultimo_non_risolto(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
        )
        tid = richiesta["thread_id"]
        primo = self.checkpoint_v2(tid)
        secondo = self.checkpoint_v2(tid, oggetto_atteso="verdetto sul secondo lotto")
        messaggi = [richiesta, primo, secondo]
        attivo = bacheca.checkpoint_ripristinabile_attivo(messaggi, tid)
        assert attivo is not None
        self.assertEqual(attivo["id_messaggio"], secondo["id_messaggio"], "il piu' recente sostituisce il precedente")

    def test_checkpoint_attivo_risolto_da_chiusura(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
        )
        tid = richiesta["thread_id"]
        chiusura = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="chiusura", testo="ok",
            thread_id=tid, verdetto_umano="approvato",
        )
        messaggi = [richiesta, self.checkpoint_v2(tid), chiusura]
        self.assertIsNone(bacheca.checkpoint_ripristinabile_attivo(messaggi, tid))

    # -- approva/respingi espongono il prossimo passo ------------------------

    def test_approva_stampa_prossimo_passo_dell_ultimo_checkpoint_attivo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Posso committare?",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            bacheca.aggiungi_messaggio(percorso, self.checkpoint_v2(richiesta["thread_id"]))
            buf = io.StringIO()
            with redirect_stdout(buf):
                esito = bacheca.main([
                    "--bacheca", str(percorso), "approva",
                    "--thread-id", richiesta["thread_id"], "--testo", "vai",
                ])
            self.assertEqual(esito, 0)
            uscita = buf.getvalue()
            self.assertIn("eseguire il commit e registrare l'evento", uscita)
            self.assertIn("NON fidato", uscita)
            self.assertNotIn("scartare le modifiche", uscita, "deve esporre solo l'azione dell'esito ricevuto")

    def test_respingi_espone_azione_del_proprio_esito(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Posso committare?",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            bacheca.aggiungi_messaggio(percorso, self.checkpoint_v2(richiesta["thread_id"]))
            buf = io.StringIO()
            with redirect_stdout(buf):
                bacheca.main([
                    "--bacheca", str(percorso), "respingi",
                    "--thread-id", richiesta["thread_id"], "--testo", "no",
                ])
            self.assertIn("scartare le modifiche e riaprire il thread", buf.getvalue())

    def test_approva_senza_checkpoint_ripristinabile_non_stampa_ripresa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Posso committare?",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            buf = io.StringIO()
            with redirect_stdout(buf):
                bacheca.main([
                    "--bacheca", str(percorso), "approva",
                    "--thread-id", richiesta["thread_id"], "--testo", "vai",
                ])
            self.assertNotIn("RIPRESA", buf.getvalue())

    # -- riprese pronte: verdetto arrivato, agente non ancora attivo ---------

    def test_riprese_pronte_dopo_verdetto_poi_sparisce_quando_l_agente_scrive(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Posso committare?",
        )
        tid = richiesta["thread_id"]
        checkpoint = self.checkpoint_v2(tid)
        chiusura = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="chiusura", testo="vai",
            thread_id=tid, verdetto_umano="approvato",
        )
        messaggi = [richiesta, checkpoint, chiusura]
        pronte = bacheca.riprese_pronte(messaggi, "claude")
        self.assertEqual(len(pronte), 1)
        self.assertEqual(pronte[0]["verdetto"], "approvato")
        self.assertEqual(pronte[0]["azione"], "eseguire il commit e registrare l'evento")
        self.assertEqual(bacheca.riprese_pronte(messaggi, "codex"), [], "solo chi ha sospeso riprende")

        presa_atto = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="risposta",
            testo="commit eseguito", thread_id=tid,
        )
        self.assertEqual(bacheca.riprese_pronte(messaggi + [presa_atto], "claude"), [])

    def test_riprese_pronte_ignora_attende_gate_anche_con_verdetto_umano(self) -> None:
        """Rilievo Codex (seconda revisione): un verdetto umano non risolve
        un'attesa di gate/agente - per quelle il checkpoint resta descrittivo."""
        richiesta = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Fai X",
        )
        tid = richiesta["thread_id"]
        checkpoint_gate = self.checkpoint_v2(
            tid, attende="gate",
            oggetto_atteso="esito di sentinella.py test_servizi",
            azioni_per_esito={"superato": "procedi", "fallito": "leggi l'output"},
        )
        chiusura = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="chiusura", testo="vai",
            thread_id=tid, verdetto_umano="approvato",
        )
        messaggi = [richiesta, checkpoint_gate, chiusura]
        self.assertEqual(bacheca.riprese_pronte(messaggi, "claude"), [])

    def test_riprese_pronte_ignora_attende_agente_anche_con_verdetto_umano(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Fai X",
        )
        tid = richiesta["thread_id"]
        checkpoint_agente = self.checkpoint_v2(
            tid, attende="agente",
            oggetto_atteso="risposta di codex sulla revisione",
            azioni_per_esito={"risposto": "integra la revisione"},
        )
        chiusura = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="chiusura", testo="vai",
            thread_id=tid, verdetto_umano="approvato",
        )
        self.assertEqual(bacheca.riprese_pronte([richiesta, checkpoint_agente, chiusura], "claude"), [])

    def test_approva_non_stampa_ripresa_per_attende_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Fai X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            checkpoint_gate = self.checkpoint_v2(
                richiesta["thread_id"], attende="gate",
                oggetto_atteso="esito di sentinella.py test_servizi",
                azioni_per_esito={"superato": "procedi", "fallito": "leggi l'output"},
            )
            bacheca.aggiungi_messaggio(percorso, checkpoint_gate)
            buf = io.StringIO()
            with redirect_stdout(buf):
                esito = bacheca.main([
                    "--bacheca", str(percorso), "approva",
                    "--thread-id", richiesta["thread_id"], "--testo", "vai",
                ])
            self.assertEqual(esito, 0)
            self.assertNotIn("RIPRESA", buf.getvalue())

    def test_riprese_pronte_ignora_chiusura_senza_verdetto(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Posso committare?",
        )
        tid = richiesta["thread_id"]
        chiusura = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="chiusura", testo="chiudo e basta",
            thread_id=tid,
        )
        messaggi = [richiesta, self.checkpoint_v2(tid), chiusura]
        self.assertEqual(bacheca.riprese_pronte(messaggi, "claude"), [])

    def test_formato_hook_include_riprese_pronte(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Posso committare?",
        )
        tid = richiesta["thread_id"]
        chiusura = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="chiusura", testo="vai",
            thread_id=tid, verdetto_umano="approvato",
        )
        messaggi = [richiesta, self.checkpoint_v2(tid), chiusura]
        testo = bacheca._formatta_per_hook([], bacheca.riprese_pronte(messaggi, "claude"))
        self.assertIn("Riprese pronte", testo)
        self.assertIn("eseguire il commit e registrare l'evento", testo)
        self.assertIn("mai eseguire in automatico", testo)

    def test_comando_ripresa_elenca_riprese_anche_senza_thread_aperti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="claude", destinatari=["umano"], tipo="richiesta", testo="Posso committare?",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            bacheca.aggiungi_messaggio(percorso, self.checkpoint_v2(richiesta["thread_id"]))
            chiusura = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="chiusura", testo="vai",
                thread_id=richiesta["thread_id"], verdetto_umano="approvato",
            )
            bacheca.aggiungi_messaggio(percorso, chiusura)
            buf = io.StringIO()
            with redirect_stdout(buf):
                esito = bacheca.comando_ripresa(argparse.Namespace(bacheca=str(percorso)))
            self.assertEqual(esito, 0)
            self.assertIn("Riprese pronte", buf.getvalue())

    # -- comando checkpoint con flag di ripresa ------------------------------

    def test_comando_checkpoint_con_attende_scrive_v2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            buf = io.StringIO()
            with redirect_stdout(buf):
                esito = bacheca.main([
                    "--bacheca", str(percorso), "checkpoint",
                    "--thread-id", richiesta["thread_id"], "--agente", "claude",
                    "--obiettivo", "Fai X", "--attende", "umano",
                    "--oggetto-atteso", "verdetto sul lavoro X",
                    "--se-approvato", "committa",
                    "--se-respinto", "scarta",
                    "--se-modifiche-richieste", "correggi e richiedi",
                ])
            self.assertEqual(esito, 0)
            ultimo = bacheca.leggi_messaggi(percorso)[-1]
            self.assertEqual(ultimo["versione_schema"], 2)
            self.assertEqual(ultimo["ripresa"]["attende"], "umano")
            self.assertEqual(ultimo["ripresa"]["contesto_minimo"]["thread_id"], richiesta["thread_id"])

    def test_comando_checkpoint_attende_umano_senza_tutti_gli_esiti_fallisce(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            buf_err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(buf_err):
                esito = bacheca.main([
                    "--bacheca", str(percorso), "checkpoint",
                    "--thread-id", richiesta["thread_id"], "--agente", "claude",
                    "--attende", "umano", "--oggetto-atteso", "verdetto",
                    "--se-approvato", "committa",
                ])
            self.assertEqual(esito, 2)
            self.assertEqual(len(bacheca.leggi_messaggi(percorso)), 1, "niente append se lo schema rifiuta")

    # -- valida: controlli cross-record --------------------------------------

    def test_valida_cross_record_thread_incoerente(self) -> None:
        richiesta = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
        )
        checkpoint = self.checkpoint_v2(richiesta["thread_id"])
        checkpoint["ripresa"]["contesto_minimo"]["thread_id"] = "un-altro-thread"
        errori = bacheca.errori_cross_record([richiesta, checkpoint], Path("."))
        self.assertTrue(any("thread" in e for e in errori))

    def test_valida_cross_record_riferimento_inesistente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
            )
            checkpoint = self.checkpoint_v2(richiesta["thread_id"])
            checkpoint["ripresa"]["contesto_minimo"]["riferimenti"] = ["file_che_non_esiste.md"]
            errori = bacheca.errori_cross_record([richiesta, checkpoint], Path(tmp))
            self.assertTrue(any("file_che_non_esiste.md" in e for e in errori))

    def test_valida_cross_record_accetta_file_url_e_id_bacheca(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "doc.md").write_text("x", encoding="utf-8")
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
            )
            checkpoint = self.checkpoint_v2(richiesta["thread_id"])
            checkpoint["ripresa"]["contesto_minimo"]["riferimenti"] = [
                "doc.md", "https://esempio.invalid/pagina", richiesta["id_messaggio"],
            ]
            self.assertEqual(bacheca.errori_cross_record([richiesta, checkpoint], Path(tmp)), [])

    def test_comando_valida_fallisce_su_cross_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "messaggi.jsonl"
            richiesta = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta", testo="Fai X",
            )
            bacheca.aggiungi_messaggio(percorso, richiesta)
            checkpoint = self.checkpoint_v2(richiesta["thread_id"])
            checkpoint["ripresa"]["contesto_minimo"]["riferimenti"] = ["file_che_non_esiste.md"]
            bacheca.aggiungi_messaggio(percorso, checkpoint)
            buf_err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(buf_err):
                esito = bacheca.main(["--bacheca", str(percorso), "valida"])
            self.assertEqual(esito, 1)
            self.assertIn("cross-record", buf_err.getvalue())


if __name__ == "__main__":
    unittest.main()
