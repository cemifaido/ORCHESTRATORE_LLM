from __future__ import annotations

import copy
import importlib
import json
from dataclasses import dataclass
from typing import Any


class LiteLLMNonConfigurato(RuntimeError):
    """LiteLLM non è installato nell'ambiente corrente."""


@dataclass(frozen=True)
class MisurazioneLiteLLM:
    modello: str
    provider: str | None
    costo_usd: float | None
    token_prompt: int | None
    token_completion: int | None
    token_totali: int | None
    fonte: str = "litellm"

    def come_metadati(self) -> dict[str, Any]:
        return {
            "fonte": self.fonte,
            "modello": self.modello,
            "provider": self.provider,
            "costo_usd": self.costo_usd,
            "token_prompt": self.token_prompt,
            "token_completion": self.token_completion,
            "token_totali": self.token_totali,
        }


def _campo(oggetto: Any, nome: str, predefinito: Any = None) -> Any:
    if isinstance(oggetto, dict):
        return oggetto.get(nome, predefinito)
    return getattr(oggetto, nome, predefinito)


def _intero_o_nullo(valore: Any) -> int | None:
    if valore is None:
        return None
    try:
        return int(valore)
    except (TypeError, ValueError):
        return None


def _float_o_nullo(valore: Any) -> float | None:
    if valore is None:
        return None
    try:
        return float(valore)
    except (TypeError, ValueError):
        return None


def _provider_da_modello(modello: str) -> str | None:
    if "/" not in modello:
        return None
    provider, _nome = modello.split("/", 1)
    return provider or None


def testo_da_risposta(risposta: Any) -> str:
    """Estrae il testo generato da una risposta di litellm.completion() (un oggetto
    ModelResponse con .choices[0].message.content). Gestisce anche dict e stringhe
    semplici (usati nei test come mock, o da provider non standard), tornando ""
    invece di sollevare se la forma e' inattesa: i chiamanti trattano "" come
    "nessun contenuto interpretabile", non come crash."""
    if isinstance(risposta, str):
        return risposta
    try:
        return risposta.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        pass
    if isinstance(risposta, dict):
        try:
            return risposta["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            pass
    return ""


def estrai_primo_oggetto_json(testo: str) -> dict[str, Any]:
    """Estrae il primo oggetto JSON dal testo di un modello, tollerando prosa
    prima/dopo (i modelli locali a volte aggiungono testo attorno al JSON
    richiesto anche quando il prompt lo vieta esplicitamente).

    Usa json.JSONDecoder().raw_decode() invece del pattern ingenuo
    testo.index('{')...testo.rindex('}'): quel pattern si rompe con oggetti
    annidati o testo dopo il JSON che contiene a sua volta una graffa (l'ultima
    '}' del testo non e' detto sia quella dell'oggetto giusto) - bug reale
    segnalato in revisione di sicurezza, 2026-08-25. raw_decode() e' il parser
    JSON vero: rispetta le graffe dentro le stringhe, l'annidamento, e si
    ferma al primo valore completo ignorando cosa viene dopo.

    Solleva ValueError se non trova nessuna '{' o se il valore trovato non e'
    un oggetto (es. il modello ha risposto con un array o uno scalare)."""
    inizio = testo.index("{")
    valore, _fine = json.JSONDecoder().raw_decode(testo, inizio)
    if not isinstance(valore, dict):
        raise ValueError(f"il valore JSON trovato non e' un oggetto: {type(valore).__name__}")
    return valore


def costo_risposta(risposta: Any, modello: str) -> float | None:
    """Legge il costo già calcolato da LiteLLM o lo calcola se la libreria è disponibile."""
    costo = _float_o_nullo(_campo(risposta, "response_cost"))
    if costo is not None:
        return costo

    parametri_nascosti = _campo(risposta, "_hidden_params", {}) or {}
    costo = _float_o_nullo(_campo(parametri_nascosti, "response_cost"))
    if costo is not None:
        return costo

    try:
        calcolatore = importlib.import_module("litellm.cost_calculator")
    except ImportError:
        return None

    completion_cost = getattr(calcolatore, "completion_cost", None)
    if completion_cost is None:
        return None
    try:
        return _float_o_nullo(completion_cost(completion_response=risposta, model=modello))
    except Exception:
        return None


def estrai_misurazione(risposta: Any, modello: str, provider: str | None = None) -> MisurazioneLiteLLM:
    usage = _campo(risposta, "usage", {}) or {}
    token_prompt = _intero_o_nullo(_campo(usage, "prompt_tokens"))
    token_completion = _intero_o_nullo(_campo(usage, "completion_tokens"))
    token_totali = _intero_o_nullo(_campo(usage, "total_tokens"))
    if token_totali is None and token_prompt is not None and token_completion is not None:
        token_totali = token_prompt + token_completion

    return MisurazioneLiteLLM(
        modello=modello,
        provider=provider or _provider_da_modello(modello),
        costo_usd=costo_risposta(risposta, modello),
        token_prompt=token_prompt,
        token_completion=token_completion,
        token_totali=token_totali,
    )


def arricchisci_evento(evento: dict[str, Any], misurazione: MisurazioneLiteLLM) -> dict[str, Any]:
    """Restituisce una copia dell'evento con costo misurato e metadati LiteLLM."""
    arricchito = copy.deepcopy(evento)
    metadati = arricchito.setdefault("metadati", {})
    metadati["litellm"] = misurazione.come_metadati()
    if misurazione.costo_usd is not None:
        arricchito["costo_stimato_usd"] = misurazione.costo_usd
        arricchito["origine_costo"] = "misurato"
    return arricchito


TIMEOUT_SECONDI_PREDEFINITO = 60.0


def completamento(
    *,
    modello: str,
    messaggi: list[dict[str, str]],
    provider: str | None = None,
    **parametri: Any,
) -> tuple[Any, MisurazioneLiteLLM]:
    """Esegue una chat completion LiteLLM e restituisce risposta + misurazione.

    La dipendenza è importata solo qui: il resto del framework resta avviabile senza
    `pip install litellm`.

    Timeout di default (guardrail M2, revisione sicurezza 2026-08-25):
    litellm.completion() non ha un timeout implicito - senza uno esplicito una
    chiamata puo' restare appesa indefinitamente (rete lenta, provider giu',
    llama-server locale bloccato). 'timeout' e' il parametro reale supportato
    da litellm.completion() (verificato via inspect.signature, non assunto per
    analogia con 'request_timeout' di altre SDK). setdefault: se il chiamante
    lo passa gia' esplicitamente in **parametri, quel valore vince sempre.
    """
    try:
        litellm = importlib.import_module("litellm")
    except ImportError as errore:
        raise LiteLLMNonConfigurato("Installa LiteLLM solo nei progetti che usano questo adapter.") from errore

    parametri.setdefault("timeout", TIMEOUT_SECONDI_PREDEFINITO)
    risposta = litellm.completion(model=modello, messages=messaggi, **parametri)
    return risposta, estrai_misurazione(risposta, modello=modello, provider=provider)


# Modello locale (llama-server/llama.cpp, endpoint compatibile OpenAI): nessuna chiave
# reale, nessun costo. Usato per triage/monitoraggio a costo zero prima di scalare a un
# agente a pagamento (vedi docs/ORCHESTRAZIONE_LAVORATORI.md, sezione Capoturno).
MODELLO_LOCALE_PREDEFINITO = "openai/qwen2.5-7b-instruct-q3_k_m.gguf"
API_BASE_LOCALE_PREDEFINITO = "http://127.0.0.1:8090/v1"


def completamento_locale(
    messaggi: list[dict[str, str]],
    modello: str = MODELLO_LOCALE_PREDEFINITO,
    api_base: str = API_BASE_LOCALE_PREDEFINITO,
    **parametri: Any,
) -> tuple[Any, MisurazioneLiteLLM]:
    """Chiama il modello locale (llama-server) con lo stesso adapter usato per i
    provider a pagamento. Il costo e' sempre 0.0 misurato (non stimato): l'inferenza
    locale non ha un costo API reale da stimare, e' un fatto noto, non un'ipotesi."""
    parametri.setdefault("api_key", "non-serve")
    risposta, misurazione = completamento(
        modello=modello,
        messaggi=messaggi,
        provider="locale",
        api_base=api_base,
        **parametri,
    )
    misurazione = MisurazioneLiteLLM(
        modello=misurazione.modello,
        provider=misurazione.provider,
        costo_usd=0.0,
        token_prompt=misurazione.token_prompt,
        token_completion=misurazione.token_completion,
        token_totali=misurazione.token_totali,
    )
    return risposta, misurazione
