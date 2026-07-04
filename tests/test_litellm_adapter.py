from __future__ import annotations

import copy
import unittest

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


if __name__ == "__main__":
    unittest.main()
