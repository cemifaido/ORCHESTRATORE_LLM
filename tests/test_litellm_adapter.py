from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock, patch

from adattatori import litellm


class RispostaFinta:
    def __init__(self) -> None:
        self.usage = {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
        }
        self.response_cost = 0.0012


class LiteLLMAdapterTest(unittest.TestCase):
    def evento(self) -> dict:
        return {
            "versione_schema": 1,
            "id_evento": "evt",
            "timestamp": "2026-07-03T20:00:00Z",
            "id_compito": "task",
            "agente": "locale",
            "tipo_compito": "monitoraggio",
            "stato": "passato",
            "esito_gate": "superato",
            "verdetto_umano": "non_revisionato",
            "costo_stimato_usd": 0.0,
            "origine_costo": "stimato",
            "latenza_ms": 1,
            "regole_incluse": [],
            "file_modificati": [],
            "note": "",
            "metadati": {},
        }

    def test_estrai_misurazione_da_risposta(self) -> None:
        misurazione = litellm.estrai_misurazione(RispostaFinta(), modello="openai/gpt-test")
        self.assertEqual(misurazione.provider, "openai")
        self.assertEqual(misurazione.token_prompt, 10)
        self.assertEqual(misurazione.token_completion, 4)
        self.assertEqual(misurazione.token_totali, 14)
        self.assertEqual(misurazione.costo_usd, 0.0012)

    def test_arricchisci_evento_non_modifica_originale(self) -> None:
        evento = self.evento()
        originale = copy.deepcopy(evento)
        misurazione = litellm.MisurazioneLiteLLM(
            modello="ollama/qwen2.5",
            provider="ollama",
            costo_usd=0.0,
            token_prompt=5,
            token_completion=3,
            token_totali=8,
        )
        arricchito = litellm.arricchisci_evento(evento, misurazione)

        self.assertEqual(evento, originale)
        self.assertEqual(arricchito["origine_costo"], "misurato")
        self.assertEqual(arricchito["metadati"]["litellm"]["provider"], "ollama")
        self.assertEqual(arricchito["metadati"]["litellm"]["token_totali"], 8)

    def test_costo_assente_lascia_origine_stimata(self) -> None:
        evento = self.evento()
        misurazione = litellm.MisurazioneLiteLLM(
            modello="modello-senza-prezzo",
            provider=None,
            costo_usd=None,
            token_prompt=None,
            token_completion=None,
            token_totali=None,
        )
        arricchito = litellm.arricchisci_evento(evento, misurazione)
        self.assertEqual(arricchito["origine_costo"], "stimato")
        self.assertIsNone(arricchito["metadati"]["litellm"]["costo_usd"])

    def test_testo_da_risposta_oggetto_modelresponse(self) -> None:
        risposta = MagicMock()
        risposta.choices = [MagicMock()]
        risposta.choices[0].message.content = "ciao dal modello"
        self.assertEqual(litellm.testo_da_risposta(risposta), "ciao dal modello")

    def test_testo_da_risposta_stringa(self) -> None:
        self.assertEqual(litellm.testo_da_risposta("gia' una stringa"), "gia' una stringa")

    def test_testo_da_risposta_dict(self) -> None:
        risposta = {"choices": [{"message": {"content": "ciao dal dict"}}]}
        self.assertEqual(litellm.testo_da_risposta(risposta), "ciao dal dict")

    def test_testo_da_risposta_forma_inattesa_torna_stringa_vuota(self) -> None:
        """Una forma inattesa (es. None, un numero, un dict senza le chiavi giuste) non
        deve far crashare il chiamante: chi usa questa funzione (triage locale,
        parsing risposte) tratta "" come "nessun contenuto interpretabile", non come eccezione."""
        self.assertEqual(litellm.testo_da_risposta(None), "")
        self.assertEqual(litellm.testo_da_risposta(42), "")
        self.assertEqual(litellm.testo_da_risposta({"choices": []}), "")
        self.assertEqual(litellm.testo_da_risposta({}), "")

    def test_estrai_primo_oggetto_json_semplice(self) -> None:
        self.assertEqual(
            litellm.estrai_primo_oggetto_json('{"esito": "routine", "motivo": "ok"}'),
            {"esito": "routine", "motivo": "ok"},
        )

    def test_estrai_primo_oggetto_json_con_prosa_attorno(self) -> None:
        testo = 'Ecco il risultato:\n{"sintesi": "fatto", "conflitto": null}\nSpero sia utile.'
        self.assertEqual(
            litellm.estrai_primo_oggetto_json(testo),
            {"sintesi": "fatto", "conflitto": None},
        )

    def test_estrai_primo_oggetto_json_annidato(self) -> None:
        """Guardrail di sicurezza (revisione esterna, 2026-08-25): il vecchio pattern
        index('{')...rindex('}') si rompeva con oggetti annidati o graffe nel testo
        dopo il JSON - qui una graffa di chiusura nella prosa seguente non deve
        far includere testo spurio nell'oggetto estratto."""
        testo = '{"esito": "escalation", "dettagli": {"riga": 12, "colonna": {"da": 1, "a": 5}}} testo dopo con una } graffa spuria'
        self.assertEqual(
            litellm.estrai_primo_oggetto_json(testo),
            {"esito": "escalation", "dettagli": {"riga": 12, "colonna": {"da": 1, "a": 5}}},
        )

    def test_estrai_primo_oggetto_json_graffa_dentro_stringa(self) -> None:
        testo = '{"motivo": "trovato un blocco { non chiuso } nel codice"}'
        self.assertEqual(
            litellm.estrai_primo_oggetto_json(testo),
            {"motivo": "trovato un blocco { non chiuso } nel codice"},
        )

    def test_estrai_primo_oggetto_json_senza_graffe_solleva(self) -> None:
        with self.assertRaises(ValueError):
            litellm.estrai_primo_oggetto_json("nessun json qui")

    def test_estrai_primo_oggetto_json_malformato_solleva(self) -> None:
        with self.assertRaises(ValueError):
            litellm.estrai_primo_oggetto_json("prefisso {non e' json valido")

    def test_completamento_locale_forza_costo_zero_misurato_e_provider_locale(self) -> None:
        """L'inferenza locale non ha un costo API da stimare: e' un fatto noto (zero),
        non un'ipotesi. Verifica anche che punti di default all'endpoint llama-server
        locale senza dover ripetere api_base/api_key ad ogni chiamata."""
        with patch("litellm.completion", return_value=RispostaFinta()) as mock_completion:
            _risposta, misurazione = litellm.completamento_locale(
                messaggi=[{"role": "user", "content": "ciao"}],
            )

        self.assertEqual(misurazione.costo_usd, 0.0)
        self.assertEqual(misurazione.provider, "locale")

        _, kwargs = mock_completion.call_args
        self.assertEqual(kwargs["api_base"], litellm.API_BASE_LOCALE_PREDEFINITO)
        self.assertEqual(kwargs["api_key"], "non-serve")
        self.assertEqual(kwargs["model"], litellm.MODELLO_LOCALE_PREDEFINITO)

    def test_completamento_applica_timeout_di_default(self) -> None:
        """Guardrail M2 (revisione sicurezza, 2026-08-25): senza un timeout di
        default, litellm.completion() puo' restare appesa indefinitamente."""
        with patch("litellm.completion", return_value=RispostaFinta()) as mock_completion:
            litellm.completamento(modello="openai/gpt-4o-mini", messaggi=[{"role": "user", "content": "ciao"}])

        _, kwargs = mock_completion.call_args
        self.assertEqual(kwargs["timeout"], litellm.TIMEOUT_SECONDI_PREDEFINITO)

    def test_completamento_rispetta_timeout_esplicito_del_chiamante(self) -> None:
        with patch("litellm.completion", return_value=RispostaFinta()) as mock_completion:
            litellm.completamento(
                modello="openai/gpt-4o-mini", messaggi=[{"role": "user", "content": "ciao"}], timeout=5.0,
            )

        _, kwargs = mock_completion.call_args
        self.assertEqual(kwargs["timeout"], 5.0)


if __name__ == "__main__":
    unittest.main()
