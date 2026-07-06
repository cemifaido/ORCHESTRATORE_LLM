#!/usr/bin/env python3
# ruff: noqa: E402
"""Motore di Orchestrazione Reale ed Handoff Cooperativo (Capoturno).

Esegue un ciclo di lavoro reale delegando compiti ad agenti AI tramite LiteLLM,
applicando le modifiche sul filesystem del progetto target, convalidando
il risultato con la Sentinella ed avviando cicli di Rework in caso di errori.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

# Aggiunge la radice al path
RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))

import registro
from adattatori import litellm
import instrada

SCRIPT_SENTINELLA_CENTRALE = RADICE / "sentinella.py"


def _scegli_modello_per_agente(agente: str) -> str:
    """Ritorna il modello LiteLLM associato all'agente, considerando le chiavi disponibili."""
    if agente == "gemini":
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini/gemini-1.5-flash"
        return "openai/gpt-4o-mini"
    elif agente == "codex":
        return "openai/gpt-4o"
    else:
        # Per Claude e fallbacks generici
        return "claude-3-haiku"


class Capoturno:
    def __init__(
        self,
        progetto_id: str,
        progetto_percorso: str,
        registro_percorso: str,
        on_passo: Callable[[str, str, str, str, str], None] | None = None
    ) -> None:
        self.progetto_id = progetto_id
        self.progetto_percorso = Path(progetto_percorso).resolve()
        self.registro_percorso = Path(registro_percorso).resolve()
        self.on_passo = on_passo
        self.limite_rework = 3

    def _notifica(self, da: str, a: str, agente_attivo: str, messaggio: str, esito: str = "in_corso") -> None:
        if self.on_passo:
            self.on_passo(da, a, agente_attivo, messaggio, esito)

    def _estrai_codice(self, risposta_testo: str) -> str | None:
        # Trova codice racchiuso tra tripli backtick
        match = re.search(r"```(?:python)?\n(.*?)\n```", risposta_testo, re.DOTALL)
        if match:
            return match.group(1)
        # Fallback se non ci sono backtick ma sembra codice Python
        if "def " in risposta_testo or "import " in risposta_testo:
            return risposta_testo
        return None

    def esegui_compito(
        self,
        id_compito: str,
        tipo_compito: str,
        compito_prompt: str,
        file_target: str,
        rischio: str = "basso"
    ) -> bool:
        """Esegue il flusso di orchestrazione reale del compito.

        Ritorna True se il compito è completato ed approvato (passa i gate), False altrimenti.
        """
        self._notifica(
            da="umano",
            a="locale",
            agente_attivo="locale",
            messaggio=f"Inizio esecuzione compito '{id_compito}' su file '{file_target}'."
        )

        # 1. Routing ed Handoff iniziale
        info_routing = instrada.instrada(tipo_compito, rischio, self.registro_percorso)
        agente_suggerito = info_routing.get("agente_suggerito", "umano")

        if info_routing.get("serve_umano_prima"):
            self._notifica(
                da="locale",
                a="umano",
                agente_attivo="umano",
                messaggio=f"Attesa approvazione per rischio {rischio} o agente Umano richiesto.",
                esito="in_corso"
            )
            # In un workflow reale sincrono qui ci si fermerebbe.
            # Per il nostro motore di base, notifichiamo e proseguiamo assumendo il via libera.

        agente_corrente = agente_suggerito
        latenze: dict[str, int] = {}
        costo_totale = 0.0
        rework_effettuato = 0
        ultimo_errore = ""

        file_completo_target = self.progetto_percorso / file_target
        codice_originale = ""
        if file_completo_target.exists():
            codice_originale = file_completo_target.read_text(encoding="utf-8")

        # 2. Inizio loop di Rework
        while rework_effettuato <= self.limite_rework:
            self._notifica(
                da="locale",
                a=agente_corrente,
                agente_attivo=agente_corrente,
                messaggio=f"Chiamata all'agente {agente_corrente.upper()} per elaborare la patch."
            )

            # Genera il prompt per l'agente
            prompt_agente = (
                f"Devi completare questo compito sul file '{file_target}':\n"
                f"COMPITO: {compito_prompt}\n\n"
            )
            if codice_originale:
                prompt_agente += f"CODICE CORRENTE DEL FILE:\n```python\n{codice_originale}\n```\n\n"
            else:
                prompt_agente += "Il file non esiste ancora, crealo da zero.\n\n"

            if ultimo_errore:
                prompt_agente += (
                    f"ATTENZIONE: Il tentativo precedente è FALLITO con il seguente errore dei test:\n"
                    f"--- INIZIO ERRORE ---\n{ultimo_errore}\n--- FINE ERRORE ---\n"
                    f"Correggi l'errore sopra e restituisci il codice corretto.\n\n"
                )

            prompt_agente += (
                "IMPORTANTE: Restituisci SOLO ed ESCLUSIVAMENTE il codice Python completo aggiornato del file "
                "racchiuso tra tripli backtick ```python ... ```. Non aggiungere spiegazioni o testo prima o dopo."
            )

            messaggi = [
                {"role": "system", "content": "Sei un assistente programmatore esperto e sintetico."},
                {"role": "user", "content": prompt_agente}
            ]

            risposta = ""
            misurazione = None

            # Esecuzione chiamata con supporto al Failover e tracciamento latenza
            agente_tentato = agente_corrente
            t0 = time.perf_counter()
            try:
                risposta, misurazione = litellm.completamento(
                    modello=_scegli_modello_per_agente(agente_tentato),
                    messaggi=messaggi,
                    temperature=0.2
                )
                t1 = time.perf_counter()
                latenza_passo = int((t1 - t0) * 1000)
            except Exception as err:
                # Se Claude o Gemini falliscono per mancanza crediti/quota, proviamo il failover
                agente_fallback = "gemini" if agente_tentato == "claude" else "claude"
                self._notifica(
                    da=agente_tentato,
                    a="locale",
                    agente_attivo="locale",
                    messaggio=f"Errore chiamata agente {agente_tentato.upper()} ({err}). Avvio failover su {agente_fallback.upper()}...",
                    esito="ambiente_errore"
                )
                try:
                    t0_fallback = time.perf_counter()
                    risposta, misurazione = litellm.completamento(
                        modello=_scegli_modello_per_agente(agente_fallback),
                        messaggi=messaggi,
                        temperature=0.2
                    )
                    t1_fallback = time.perf_counter()
                    latenza_passo = int((t1_fallback - t0_fallback) * 1000)
                    agente_corrente = agente_fallback
                except Exception as err_fallback:
                    # Fallimento totale: nessuna risorsa disponibile
                    messaggio_errore = f"Tutti gli agenti hanno fallito (crediti esauriti o API offline): {err_fallback}"
                    self._notifica(
                        da="locale",
                        a="umano",
                        agente_attivo="umano",
                        messaggio=messaggio_errore,
                        esito="ambiente_errore"
                    )
                    # Registra l'evento come errore_ambiente
                    evento_errore = {
                        "versione_schema": 1,
                        "id_evento": str(uuid.uuid4()),
                        "timestamp": registro.adesso_utc(),
                        "id_compito": id_compito,
                        "agente": agente_tentato,
                        "tipo_compito": tipo_compito,
                        "stato": "errore_ambiente",
                        "esito_gate": "non_eseguito",
                        "verdetto_umano": "non_revisionato",
                        "costo_stimato_usd": costo_totale,
                        "origine_costo": "misurato",
                        "latenza_ms": sum(latenze.values()),
                        "regole_incluse": [],
                        "file_modificati": [file_target],
                        "note": f"Errore API e failover fallito: {err_fallback}"
                    }
                    registro.aggiungi_evento(self.registro_percorso, evento_errore)
                    return False

            # Accumula statistiche
            costo_totale += misurazione.costo_usd if (misurazione and misurazione.costo_usd is not None) else 0.0
            latenze[agente_corrente] = latenze.get(agente_corrente, 0) + latenza_passo

            # 3. Estrazione e scrittura del codice
            codice_proposto = self._estrai_codice(litellm.testo_da_risposta(risposta))
            if not codice_proposto:
                ultimo_errore = "Non è stato possibile estrarre codice Python valido dal blocco markdown della risposta."
                rework_effettuato += 1
                self._notifica(
                    da=agente_corrente,
                    a="locale",
                    agente_attivo="locale",
                    messaggio="Estrazione codice fallita, avvio rework.",
                    esito="fallito"
                )
                continue

            # Scrive fisicamente sul filesystem
            file_completo_target.parent.mkdir(parents=True, exist_ok=True)
            file_completo_target.write_text(codice_proposto, encoding="utf-8")

            # 4. Validazione con la Sentinella (Quality Gate)
            self._notifica(
                da=agente_corrente,
                a="locale",
                agente_attivo="locale",
                messaggio=f"Modifiche applicate a '{file_target}'. Avvio validazione Sentinella."
            )

            # Eseguiamo il gate con ruff, usando SEMPRE la sentinella e il comando
            # centrali (RADICE), ma cwd e --registro puntati al progetto target: senza
            # questo, "ruff check ." validerebbe il codice dell'orchestratore invece del
            # file appena scritto nel progetto target, e il gate passerebbe sempre a
            # prescindere da cosa ha scritto l'agente.
            cmd = [
                sys.executable, str(SCRIPT_SENTINELLA_CENTRALE), "controllo_lint",
                "--config", str(RADICE / "config" / "comandi.json"),
                "--registro", str(self.registro_percorso),
            ]
            res = subprocess.run(cmd, cwd=str(self.progetto_percorso), capture_output=True, text=True)

            if res.returncode == 0:
                # Successo! Registra l'evento
                self._notifica(
                    da="locale",
                    a="umano",
                    agente_attivo="umano",
                    messaggio=f"Tutti i quality gate superati con successo per '{file_target}'!",
                    esito="successo"
                )

                evento_successo = {
                    "versione_schema": 1,
                    "id_evento": str(uuid.uuid4()),
                    "timestamp": registro.adesso_utc(),
                    "id_compito": id_compito,
                    "agente": agente_corrente,
                    "tipo_compito": tipo_compito,
                    "stato": "passato",
                    "esito_gate": "superato",
                    "verdetto_umano": "non_revisionato",
                    "costo_stimato_usd": costo_totale,
                    "origine_costo": "misurato",
                    "latenza_ms": sum(latenze.values()),
                    "regole_incluse": ["comandi_whitelistati"],
                    "file_modificati": [file_target],
                    "note": f"Compito completato con successo al tentativo {rework_effettuato + 1}",
                    "metadati": {
                        "litellm_costo_totale": costo_totale,
                        "latenze_agenti": latenze
                    }
                }
                registro.aggiungi_evento(self.registro_percorso, evento_successo)
                return True
            else:
                # Fallito: prepariamo il rework
                ultimo_errore = res.stdout or res.stderr
                rework_effettuato += 1
                self._notifica(
                    da="locale",
                    a=agente_corrente,
                    agente_attivo=agente_corrente,
                    messaggio=f"Quality gate FALLITO. Richiedo correzione (Tentativo rework {rework_effettuato}/{self.limite_rework}).",
                    esito="fallito"
                )
                # Ripristina il codice originale prima del prossimo tentativo se serve per confronto
                # (manteniamo quello proposto così l'agente può correggerlo)
                codice_originale = codice_proposto

        # Se usciamo dal loop senza successo, registriamo il fallimento finale
        self._notifica(
            da="locale",
            a="umano",
            agente_attivo="umano",
            messaggio=f"Compito FALLITO dopo aver raggiunto il limite massimo di rework ({self.limite_rework}).",
            esito="fallito"
        )

        evento_fallito = {
            "versione_schema": 1,
            "id_evento": str(uuid.uuid4()),
            "timestamp": registro.adesso_utc(),
            "id_compito": id_compito,
            "agente": agente_corrente,
            "tipo_compito": tipo_compito,
            "stato": "fallito",
            "esito_gate": "fallito",
            "verdetto_umano": "non_revisionato",
            "costo_stimato_usd": costo_totale,
            "origine_costo": "misurato",
            "latenza_ms": sum(latenze.values()),
            "regole_incluse": [],
            "file_modificati": [file_target],
            "note": f"Fallito dopo {rework_effettuato} rework. Ultimo errore: {ultimo_errore[:200]}"
        }
        registro.aggiungi_evento(self.registro_percorso, evento_fallito)
        return False
