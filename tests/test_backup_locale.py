from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backup_locale


class BackupLocaleTest(unittest.TestCase):
    def test_salva_snapshot_copia_solo_percorsi_esistenti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            cartella_dati = radice / "dati_locali"
            cartella_dati.mkdir()
            (cartella_dati / "eventi.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
            file_env = radice / ".env"
            file_env.write_text("CHIAVE=valore\n", encoding="utf-8")
            file_mai_esistito = radice / "non_esiste.json"

            cartella_backup = radice / "backup_locale"
            destinazione = backup_locale.salva_snapshot(
                percorsi=[cartella_dati, file_env, file_mai_esistito],
                cartella_backup=cartella_backup,
            )

            self.assertTrue((destinazione / "dati_locali" / "eventi.jsonl").exists())
            self.assertEqual((destinazione / "dati_locali" / "eventi.jsonl").read_text(encoding="utf-8"), '{"a": 1}\n')
            self.assertTrue((destinazione / ".env").exists())
            self.assertFalse((destinazione / "non_esiste.json").exists())

            manifesto = (destinazione / "MANIFESTO.txt").read_text(encoding="utf-8")
            self.assertIn("dati_locali", manifesto)
            self.assertIn(".env", manifesto)
            self.assertNotIn("non_esiste.json", manifesto)

    def test_snapshot_non_modifica_l_originale(self) -> None:
        """Un backup non deve mai poter corrompere i dati che sta copiando -
        e' proprio la rete di sicurezza che deve restare intatta."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            file_env = radice / ".env"
            contenuto_originale = "CHIAVE=valore\n"
            file_env.write_text(contenuto_originale, encoding="utf-8")

            backup_locale.salva_snapshot(percorsi=[file_env], cartella_backup=radice / "backup_locale")

            self.assertEqual(file_env.read_text(encoding="utf-8"), contenuto_originale)

    def test_elenca_snapshot_ordina_dal_piu_recente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            cartella_backup = radice / "backup_locale"
            (cartella_backup / "2026-08-27T080000Z").mkdir(parents=True)
            (cartella_backup / "2026-08-27T090000Z").mkdir(parents=True)

            snapshot = backup_locale.elenca_snapshot(cartella_backup)

            self.assertEqual([p.name for p in snapshot], ["2026-08-27T090000Z", "2026-08-27T080000Z"])

    def test_elenca_snapshot_su_cartella_assente_ritorna_vuoto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(backup_locale.elenca_snapshot(Path(tmp) / "non_esiste"), [])

    def test_cli_salva_e_lista(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            (radice / ".env").write_text("X=1\n", encoding="utf-8")
            with patch.object(backup_locale, "PERCORSI_DA_SALVARE", [radice / ".env"]), \
                 patch.object(backup_locale, "CARTELLA_BACKUP", radice / "backup_locale"):
                codice = backup_locale.main(["salva"])
                self.assertEqual(codice, 0)
                codice = backup_locale.main(["lista"])
                self.assertEqual(codice, 0)


if __name__ == "__main__":
    unittest.main()
