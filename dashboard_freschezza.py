"""Sentinella non bloccante del codice caricato dal processo dashboard.

Python mantiene in memoria i moduli gia' importati: una modifica su disco non
entra quindi nel processo finche' non viene riavviato. Questo modulo conserva
una fotografia dell'insieme esplicito dei moduli Python della dashboard e la
confronta con il disco su ogni richiesta di stato.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Final
import sys

import dashboard_config


RADICE: Final = dashboard_config.RADICE
AVVIO_UTC: Final = datetime.now(timezone.utc).isoformat()


def _file_runtime(radice: Path = RADICE) -> list[Path]:
    """Perimetro centralizzato: solo moduli della dashboard nella sua radice.

    Esclude deliberatamente test, dati locali, cache e asset web: questi ultimi
    sono letti dal browser a ogni refresh e non richiedono il reload di Python.
    """
    return sorted(path for path in radice.glob("*.py") if path.is_file())


def _impronta(radice: Path = RADICE) -> dict[str, str]:
    impronta: dict[str, str] = {}
    for percorso in _file_runtime(radice):
        relativo = percorso.relative_to(radice).as_posix()
        impronta[relativo] = hashlib.blake2b(percorso.read_bytes(), digest_size=20).hexdigest()
    return impronta


IMPRONTA_AVVIO: Final = _impronta()


def stato_codice_dashboard(
    *,
    radice: Path = RADICE,
    impronta_avvio: dict[str, str] = IMPRONTA_AVVIO,
    avvio_utc: str = AVVIO_UTC,
) -> dict[str, object]:
    """DTO per API/UI: allineato, modificato o non_verificabile.

    Un errore di lettura non viene scambiato per allineamento. Non pubblichiamo
    dettagli dell'eccezione: l'endpoint e' consultabile anche fuori dal devbox.
    """
    controllo_utc = datetime.now(timezone.utc).isoformat()
    try:
        impronta_corrente = _impronta(radice)
    except OSError:
        return {
            "stato": "non_verificabile",
            "avvio_utc": avvio_utc,
            "controllo_utc": controllo_utc,
            "file_modificati": [],
        }
    modificati = sorted(
        percorso
        for percorso in set(impronta_avvio) | set(impronta_corrente)
        if impronta_avvio.get(percorso) != impronta_corrente.get(percorso)
    )
    return {
        "stato": "modificato" if modificati else "allineato",
        "avvio_utc": avvio_utc,
        "controllo_utc": controllo_utc,
        "file_modificati": modificati[:20],
    }


_ultimo_avviso_modificati: list[str] | None = None


def segnala_disallineamento(
    stato: dict[str, object] | None = None,
    *,
    radice: Path = RADICE,
    impronta_avvio: dict[str, str] = IMPRONTA_AVVIO,
    file_log: object = sys.stderr,
) -> bool:
    """Emette un log esplicito su stderr quando viene rilevato un disallineamento
    dei moduli runtime su disco rispetto all'avvio. Evita spam ripetendo il log
    solo se l'insieme dei file modificati cambia. Restituisce True se e' stato
    emesso un nuovo avviso."""
    global _ultimo_avviso_modificati
    if stato is None:
        stato = stato_codice_dashboard(radice=radice, impronta_avvio=impronta_avvio)

    if stato.get("stato") == "modificato":
        file_modificati = list(stato.get("file_modificati", []))  # type: ignore
        if file_modificati != _ultimo_avviso_modificati:
            _ultimo_avviso_modificati = file_modificati
            nomi = ", ".join(str(f) for f in file_modificati) if file_modificati else "moduli non specificati"
            print(
                f"[FRESCHEZZA CODICE] ATTENZIONE: codice dashboard modificato su disco rispetto all'avvio del processo! "
                f"Moduli disallineati: {nomi}. Riavviare il processo dashboard per applicare le modifiche.",
                file=file_log,  # type: ignore
            )
            return True
    elif stato.get("stato") == "allineato":
        _ultimo_avviso_modificati = None
    return False


def reset_stato_segnalazione() -> None:
    """Ripristina lo stato interno delle segnalazioni (utile per test o riavvii)."""
    global _ultimo_avviso_modificati
    _ultimo_avviso_modificati = None

