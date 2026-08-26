from __future__ import annotations

import copy
import unittest
from typing import Any

import valida_capability


def _voce_valida(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "prova_cli_headless",
        "provider": "anthropic",
        "prodotto": "Prova",
        "canale": "cli_headless",
        "os_supportati": ["windows"],
        "piano_costo": "abbonamento",
        "fonte_ufficiale": "verifica diretta",
        "prova_eseguita": "comando lanciato e osservato",
        "checked_at": "2026-08-26T00:00:00Z",
        "expires_at": "2026-09-01T00:00:00Z",
        "stato": "verified",
        "modalita_operativa": "automatica",
    }
    base.update(extra)
    return base


def _catalogo(*voci: dict) -> dict:
    return {"versione_schema": 1, "capability": list(voci)}


class ValidaCapabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = valida_capability.carica_json(valida_capability.PERCORSO_SCHEMA_PREDEFINITO)

    def test_catalogo_predefinito_e_valido(self) -> None:
        """Quello che valida_capability.py usa di default: il reale se esiste
        su questa macchina (mai committato), altrimenti il template pubblico."""
        errori = valida_capability.valida_file(valida_capability.PERCORSO_CATALOGO_PREDEFINITO)
        self.assertEqual(errori, [])

    def test_template_pubblico_e_sempre_valido(self) -> None:
        """Il file versionato deve restare valido a prescindere dalla macchina
        (e' quello che finisce nel repository pubblico e gira in CI)."""
        errori = valida_capability.valida_file(valida_capability._PERCORSO_CATALOGO_ESEMPIO)
        self.assertEqual(errori, [])

    def test_voce_minima_valida(self) -> None:
        errori = valida_capability.valida_catalogo(_catalogo(_voce_valida()), self.schema)
        self.assertEqual(errori, [])

    def test_campo_obbligatorio_mancante(self) -> None:
        voce = _voce_valida()
        del voce["fonte_ufficiale"]
        errori = valida_capability.valida_catalogo(_catalogo(voce), self.schema)
        self.assertTrue(errori)

    def test_stato_non_ammesso_rifiutato(self) -> None:
        errori = valida_capability.valida_catalogo(
            _catalogo(_voce_valida(stato="funziona_forse")), self.schema
        )
        self.assertTrue(errori)

    def test_id_duplicato_rifiutato(self) -> None:
        v1 = _voce_valida()
        v2 = copy.deepcopy(v1)
        errori = valida_capability.valida_catalogo(_catalogo(v1, v2), self.schema)
        self.assertTrue(any("duplicato" in e for e in errori))

    def test_default_deny_stato_non_verified_con_automatica_rifiutato(self) -> None:
        """Guardrail centrale (sezione 3 del piano): una capability non
        'verified' non puo' dichiararsi 'automatica' - deve restare
        manual_only finche' non e' davvero verificata."""
        for stato in ("unknown", "failed", "degraded", "disabled"):
            with self.subTest(stato=stato):
                errori = valida_capability.valida_catalogo(
                    _catalogo(_voce_valida(stato=stato, modalita_operativa="automatica")),
                    self.schema,
                )
                self.assertTrue(any("default deny" in e for e in errori))

    def test_stato_non_verified_con_manual_only_accettato(self) -> None:
        for stato in ("unknown", "failed", "degraded", "disabled"):
            with self.subTest(stato=stato):
                errori = valida_capability.valida_catalogo(
                    _catalogo(_voce_valida(stato=stato, modalita_operativa="manual_only")),
                    self.schema,
                )
                self.assertEqual(errori, [])

    def test_expires_at_non_successivo_a_checked_at_rifiutato(self) -> None:
        errori = valida_capability.valida_catalogo(
            _catalogo(_voce_valida(checked_at="2026-08-26T00:00:00Z", expires_at="2026-08-01T00:00:00Z")),
            self.schema,
        )
        self.assertTrue(any("expires_at" in e for e in errori))

    def test_verified_automatica_senza_expires_at_rifiutato(self) -> None:
        """Guardrail (policy 2026-08-26): una capability verified+automatica
        non puo' restare attestata per sempre senza scadenza."""
        errori = valida_capability.valida_catalogo(
            _catalogo(_voce_valida(expires_at=None)), self.schema
        )
        self.assertTrue(any("expires_at=null" in e for e in errori))

    def test_verified_automatica_con_expires_at_oltre_90_giorni_rifiutato(self) -> None:
        errori = valida_capability.valida_catalogo(
            _catalogo(_voce_valida(checked_at="2026-08-26T00:00:00Z", expires_at="2026-12-01T00:00:00Z")),
            self.schema,
        )
        self.assertTrue(any("90" in e for e in errori))

    def test_verified_automatica_con_expires_at_entro_90_giorni_accettato(self) -> None:
        errori = valida_capability.valida_catalogo(
            _catalogo(_voce_valida(checked_at="2026-08-26T00:00:00Z", expires_at="2026-11-24T00:00:00Z")),
            self.schema,
        )
        self.assertEqual(errori, [])

    def test_manual_only_senza_expires_at_accettato(self) -> None:
        """Il vincolo di scadenza vale solo per verified+automatica: una
        capability manual_only puo' restare senza scadenza (non c'e' nulla
        di automatico da far scadere)."""
        errori = valida_capability.valida_catalogo(
            _catalogo(_voce_valida(stato="unknown", modalita_operativa="manual_only", expires_at=None)),
            self.schema,
        )
        self.assertEqual(errori, [])

    def test_matrice_e_ordinata_e_mostra_i_campi_operativi(self) -> None:
        catalogo = _catalogo(
            _voce_valida(id="zeta_hook_pull", expires_at=None),
            _voce_valida(
                id="alpha_cli_headless", stato="unknown", modalita_operativa="manual_only",
                expires_at=None,
            ),
        )
        matrice = valida_capability.formatta_matrice(catalogo)
        righe = matrice.splitlines()
        self.assertIn("id", righe[0])
        self.assertIn("stato", righe[0])
        self.assertIn("modalita", righe[0])
        self.assertIn("scadenza", righe[0])
        self.assertLess(matrice.index("alpha_cli_headless"), matrice.index("zeta_hook_pull"))
        self.assertIn("unknown", matrice)
        self.assertIn("manual_only", matrice)
        self.assertIn("-", matrice)

    def test_matrice_con_catalogo_vuoto_non_crasha(self) -> None:
        """Lo schema non impone minItems sull'array 'capability' top-level:
        un catalogo appena inizializzato, senza ancora nessuna voce, e'
        validato correttamente - la matrice deve gestirlo, non esplodere."""
        matrice = valida_capability.formatta_matrice(_catalogo())
        self.assertEqual(matrice, "nessuna capability nel catalogo")

    def test_catalogo_illeggibile_ritorna_errore_non_eccezione(self) -> None:
        errori = valida_capability.valida_file(valida_capability.RADICE / "non_esiste.json")
        self.assertTrue(errori)


if __name__ == "__main__":
    unittest.main()
