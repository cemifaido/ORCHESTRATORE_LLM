#!/usr/bin/env python3
"""Adapter di sistema operativo per la Dashboard (Lotto E).

Centralizza le interazioni a basso livello con Windows e il runtime:
- Verifica PID vivi via Windows API (Kernel32) o segnali POSIX
- Discovery delle sessioni Claude attive in ~/.claude/sessions
- Manipolazione appunti (PowerShell su Windows)
- Protocol handler antigravity-ide:// e avvio processi staccati
- Invocazione subprocess per sentinella.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NOME_STATO_RIAVVIO = "dashboard_riavvio.json"
NOME_LOG_RIAVVIO = "dashboard_riavvio.log"


def _percorso_stato_riavvio(radice: Path) -> Path:
    return radice / "dati_locali" / "orchestrazione" / NOME_STATO_RIAVVIO


def _adesso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scrivi_stato_riavvio(radice: Path, stato: dict[str, Any]) -> None:
    """Stato atomico, leggibile anche dopo l'uscita del processo precedente."""
    percorso = _percorso_stato_riavvio(radice)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=percorso.parent, delete=False) as file:
        json.dump(stato, file, ensure_ascii=False, sort_keys=True)
        file.write("\n")
        temporaneo = Path(file.name)
    os.replace(temporaneo, percorso)


def leggi_stato_riavvio(radice: Path) -> dict[str, Any] | None:
    try:
        stato = json.loads(_percorso_stato_riavvio(radice).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return stato if isinstance(stato, dict) else None


def richiedi_riavvio(radice: Path) -> dict[str, Any]:
    stato = {"id": str(uuid.uuid4()), "stato": "richiesto", "aggiornato_utc": _adesso_utc()}
    _scrivi_stato_riavvio(radice, stato)
    return stato


def identita_processo_corrente() -> dict[str, Any]:
    """Tupla d'identita' del processo che chiama: pid + istante di creazione +
    percorso dell'eseguibile. Va persistita accanto a un pid ogni volta che
    quel pid verra' riletto per un controllo di vivezza (PIANO §15 Slice A):
    su Windows i pid si riciclano in fretta e il solo numero non distingue il
    processo originale da uno nuovo che ha ereditato lo stesso pid."""
    pid = os.getpid()
    return {
        "pid": pid,
        "creato_il": tempo_creazione_processo(pid),
        "eseguibile": sys.executable or None,
    }


def registra_dashboard_pronto(radice: Path) -> None:
    """Il nuovo processo scrive readiness solo dopo l'avvio di FastAPI."""
    precedente = leggi_stato_riavvio(radice) or {}
    _scrivi_stato_riavvio(radice, {
        "id": precedente.get("id"), "stato": "pronto",
        "aggiornato_utc": _adesso_utc(), **identita_processo_corrente(),
    })


PROCESSO_VIVO = "vivo"
PROCESSO_MORTO = "morto"
PROCESSO_NON_VERIFICABILE = "non_verificabile"

# Scarto massimo, in secondi, fra istante di creazione atteso e osservato prima
# di dichiarare che il pid e' stato riciclato. Copre l'imprecisione fra la
# lettura FILETIME/clock-tick e l'ISO string persistita, non di piu'.
_TOLLERANZA_CREAZIONE_S = 2.0


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87


def _kernel32() -> Any:
    """kernel32 con i tipi giusti: senza restype=HANDLE ctypes tronca il valore
    a un int a 32 bit su Windows 64 (handle mangiato, CloseHandle sul valore
    sbagliato)."""
    import ctypes
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return k


def _con_handle_processo(pid: int, azione: Any) -> Any:
    """Apre il processo, passa l'handle ad `azione`, chiude sempre. Ritorna
    ('errore', codice_win32) se OpenProcess fallisce, altrimenti azione(k, h)."""
    import ctypes

    k = _kernel32()
    handle = k.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ("errore", ctypes.get_last_error())
    try:
        return azione(k, handle)
    finally:
        k.CloseHandle(handle)


def _pid_attivo(pid: int) -> bool | None:
    """Vivezza grezza, senza controllo d'identita': True vivo, False terminato,
    None se l'OS non da' una risposta certa (permessi, errore inatteso) - il
    chiamante lo tratta come 'non_verificabile' e fa fail-closed."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        def leggi(k: Any, handle: Any) -> bool | None:
            codice = wintypes.DWORD(0)
            if not k.GetExitCodeProcess(handle, ctypes.byref(codice)):
                return None
            return codice.value == _STILL_ACTIVE

        esito = _con_handle_processo(pid, leggi)
        if isinstance(esito, tuple):  # OpenProcess fallita
            err = esito[1]
            if err == _ERROR_INVALID_PARAMETER:
                return False  # nessun processo con questo pid
            if err == _ERROR_ACCESS_DENIED:
                return True  # il processo esiste, semplicemente non e' nostro
            return None
        return esito
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def tempo_creazione_processo(pid: Any) -> float | None:
    """Istante di creazione del processo come epoch UTC (secondi), o None se non
    ottenibile su questa piattaforma o per questo pid. Windows: GetProcessTimes
    (FILETIME dal 1601). Linux: campo starttime di /proc/<pid>/stat piu' btime."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        def leggi(k: Any, handle: Any) -> float | None:
            creazione, uscita, kernel_t, utente_t = (wintypes.FILETIME() for _ in range(4))
            if not k.GetProcessTimes(
                handle, ctypes.byref(creazione), ctypes.byref(uscita),
                ctypes.byref(kernel_t), ctypes.byref(utente_t),
            ):
                return None
            ticks = (creazione.dwHighDateTime << 32) | creazione.dwLowDateTime
            return (ticks - 116_444_736_000_000_000) / 1e7 if ticks else None

        esito = _con_handle_processo(pid, leggi)
        return None if isinstance(esito, tuple) else esito
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", encoding="ascii") as stat_file:
                campi = stat_file.read().rsplit(")", 1)[1].split()
            starttime_tick = int(campi[19])  # 22esimo campo, meno "pid (comm)"
            with open("/proc/stat", encoding="ascii") as proc_stat:
                btime = next(
                    int(r.split()[1]) for r in proc_stat if r.startswith("btime ")
                )
            return btime + starttime_tick / os.sysconf("SC_CLK_TCK")
        except (OSError, ValueError, StopIteration, IndexError):
            return None
    if sys.platform == "darwin":
        # macOS non ha /proc: `ps -o lstart=` da' l'istante di avvio in ora
        # locale (non un delta -> nessuno skew col clock del chiamante).
        # Rilievo review v4 N6: senza questo ramo il chiamante restava
        # 'non_verificabile' per sempre e un test falliva su darwin.
        try:
            esito = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                capture_output=True, text=True, timeout=5, check=False,
            )
            testo = " ".join((esito.stdout or "").split())
            if esito.returncode != 0 or not testo:
                return None
            return datetime.strptime(testo, "%a %b %d %H:%M:%S %Y").timestamp()
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
    return None


def _eseguibile_processo(pid: int) -> str | None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        def leggi(k: Any, handle: Any) -> str | None:
            dimensione = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(dimensione.value)
            if not k.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(dimensione)):
                return None
            return buffer.value or None

        esito = _con_handle_processo(pid, leggi)
        return None if isinstance(esito, tuple) else esito
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return None


def stato_processo(
    pid: Any,
    *,
    creato_atteso: float | None = None,
    eseguibile_atteso: str | None = None,
) -> str:
    """'vivo' | 'morto' | 'non_verificabile' per un pid, con controllo opzionale
    d'identita' (PIANO §15 Slice A).

    - pid non valido -> 'morto'
    - l'OS non sa dirlo -> 'non_verificabile' (il chiamante fa fail-closed:
      niente blocco fantasma, ma nemmeno un falso 'occupato')
    - vivo ma istante di creazione oltre la tolleranza rispetto a `creato_atteso`
      -> 'morto' (pid riciclato, e' un altro processo)
    - vivo ma nome dell'eseguibile diverso da `eseguibile_atteso` -> 'morto'
      (difesa aggiuntiva, piu' debole del confronto sull'istante di creazione)
    """
    if not isinstance(pid, int) or pid <= 0:
        return PROCESSO_MORTO
    attivo = _pid_attivo(pid)
    if attivo is None:
        return PROCESSO_NON_VERIFICABILE
    if attivo is False:
        return PROCESSO_MORTO
    if creato_atteso is not None:
        creato = tempo_creazione_processo(pid)
        if creato is None:
            return PROCESSO_NON_VERIFICABILE
        if abs(creato - creato_atteso) > _TOLLERANZA_CREAZIONE_S:
            return PROCESSO_MORTO
    if eseguibile_atteso is not None:
        eseguibile = _eseguibile_processo(pid)
        if eseguibile is None:
            return PROCESSO_NON_VERIFICABILE
        if Path(eseguibile).name.lower() != Path(eseguibile_atteso).name.lower():
            return PROCESSO_MORTO
    return PROCESSO_VIVO


def pid_vivo(pid: Any) -> bool:
    """Compat: True solo se il processo e' PROVATO vivo. 'non_verificabile' ->
    False (fail-closed). Il codice nuovo usa stato_processo() per distinguere
    'morto' da 'non_verificabile' e per passare la tupla d'identita'."""
    return stato_processo(pid) == PROCESSO_VIVO


def stato_riavvio_con_vivezza(radice: Path) -> dict[str, Any] | None:
    """leggi_stato_riavvio() piu' il campo derivato `processo` ('vivo'/'morto'/
    'non_verificabile'): quello che la dashboard mostra senza dover fidarsi del
    solo pid persistito."""
    stato = leggi_stato_riavvio(radice)
    if stato is None:
        return None
    return {**stato, "processo": stato_dashboard_pronto(radice)}


def stato_dashboard_pronto(radice: Path) -> str:
    """'vivo' | 'morto' | 'non_verificabile' per il processo dashboard registrato
    in dashboard_riavvio.json, verificando la tupla pid+creazione+eseguibile
    quando presente (gli stati storici hanno solo il pid)."""
    stato = leggi_stato_riavvio(radice)
    if not stato or stato.get("stato") != "pronto":
        return PROCESSO_MORTO
    return stato_processo(
        stato.get("pid"),
        creato_atteso=stato.get("creato_il"),
        eseguibile_atteso=stato.get("eseguibile"),
    )


def trova_ultima_sessione_claude(percorso_progetto: Path) -> str | None:
    """Cerca tra le sessioni di Claude memorizzate in ~/.claude/sessions
    quella associata a questo progetto il cui processo e' ancora vivo."""
    dir_sessioni = Path.home() / ".claude" / "sessions"
    if not dir_sessioni.exists():
        return None
    sessioni = []
    for f in dir_sessioni.glob("*.json"):
        try:
            dati = json.loads(f.read_text(encoding="utf-8"))
            cwd_sessione = Path(dati.get("cwd", ""))
            if cwd_sessione.resolve() != percorso_progetto.resolve():
                continue
            if not pid_vivo(dati.get("pid")):
                continue
            sessioni.append((dati.get("startedAt", 0), dati.get("sessionId")))
        except Exception:
            pass
    if not sessioni:
        return None
    sessioni.sort(reverse=True)
    return sessioni[0][1]


def copia_negli_appunti(testo: str) -> None:
    """Copia il testo negli appunti di sistema (PowerShell su Windows)."""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
        input=testo,
        text=True,
        check=True,
    )


def lancia_ide_uri(uri: str) -> None:
    """Invoca Antigravity IDE per aprire un URI o portare a fuoco l'editor."""
    antigravity_cmd = os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\Antigravity IDE\bin\antigravity-ide.cmd"
    )
    subprocess.Popen([antigravity_cmd, "--open-url", uri])


def avvia_processo_sostituto(script_interfaccia: Path, radice: Path) -> int:
    """Avvia l'istanza sostituta e conserva l'output locale per diagnosticarla."""
    percorso_log = radice / "dati_locali" / "orchestrazione" / NOME_LOG_RIAVVIO
    percorso_log.parent.mkdir(parents=True, exist_ok=True)
    stato_precedente = leggi_stato_riavvio(radice) or {}
    # Va scritto PRIMA della Popen: il figlio puo' raggiungere lo startup prima
    # che questa funzione torni. Scrivere dopo sovrascriverebbe il suo "pronto".
    _scrivi_stato_riavvio(radice, {**stato_precedente, "stato": "processo_avviato", "aggiornato_utc": _adesso_utc()})
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with percorso_log.open("a", encoding="utf-8") as log:
        log.write(f"{_adesso_utc()} avvio processo sostituto\n")
        kwargs["stdout"] = log
        kwargs["stderr"] = subprocess.STDOUT
        try:
            processo = subprocess.Popen(
                [sys.executable, str(script_interfaccia)], cwd=str(radice), env=os.environ.copy(), **kwargs
            )
        except OSError:
            _scrivi_stato_riavvio(radice, {**stato_precedente, "stato": "errore_avvio", "aggiornato_utc": _adesso_utc()})
            raise
        log.write(f"{_adesso_utc()} processo sostituto pid={processo.pid}\n")
    return processo.pid


def interpreta_output_sentinella(output_std: str, output_err: str = "") -> dict:
    """Decodifica l'output JSON completo stampato da sentinella.py."""
    try:
        return json.loads(output_std.strip())
    except Exception:
        return {"output": output_std, "stderr": output_err}


def esegui_sentinella_subprocess(
    script_sentinella: Path,
    comando: str,
    percorso_comandi: Path,
    percorso_registro: Path,
    cwd_path: Path,
    timeout_secondi: int = 180,
) -> tuple[int, dict]:
    """Esegue sentinella.py in un processo figlio e ne restituisce il codice di uscita e i dati decodificati."""
    completato = subprocess.run(
        [
            sys.executable,
            str(script_sentinella),
            comando,
            "--config", str(percorso_comandi),
            "--registro", str(percorso_registro),
            "--triage-locale",
        ],
        cwd=cwd_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_secondi,
        shell=False,
    )
    dati = interpreta_output_sentinella(completato.stdout or "", completato.stderr or "")
    return completato.returncode, dati
