"""Einstellungen: Modelle der Swiss AI Research Platform und der Ordner für eingelesene Unterlagen.

Schlüssel: Umgebungsvariable SWISSAI_API_KEY (nach Login auf https://serving.swissai.svc.cscs.ch).
Daten: STUDIENASSISTENT_DATEN (Standard: ./daten) – dort liegen Index, Fristen und Embedding-Cache. Kursunterlagen der
FHNW gehören nicht ins öffentliche Repository; sie werden lokal eingelesen.
"""
from __future__ import annotations

import os
from pathlib import Path

SWISSAI_URL = "https://api.swissai.svc.cscs.ch/v1"
MODELLE = {
    "deepseek": "RCP-AIaaS/deepseek-ai/DeepSeek-V4.1-Flash",   # schnell, zuverlässiges Werkzeug-Aufrufen
    "apertus": "CSCS-Inference/swiss-ai/Apertus-v1.5-70B",     # das Schweizer Modell
    "glm": "CSCS-Inference/zai-org/GLM-5.3",                   # stärkstes Modell der Plattform
    "glm-flash": "RCP-AIaaS/zai-org/GLM-5.3-Flash",            # schnellere GLM-Variante
}
EMBEDDING_MODELL = "RCP-AIaaS/Qwen/Qwen3-Embedding-8B"
# Ratenlimit der Plattform laut FAQ: unter 15 Anfragen pro Minute pro Nutzer (weitergeleitete Modelle)
# Die Plattform lehnte bei 14 pro Minute schon ab (HTTP 429, gemessen 07.10.2026), darum vorsichtiger
ANFRAGEN_PRO_MINUTE = 10
# Zeitlimit pro Modell-Aufruf in Sekunden
ZEITLIMIT_SCHNELL = 60
ZEITLIMIT_DENKEN = 240


def daten_ordner() -> Path:
    return Path(os.environ.get("STUDIENASSISTENT_DATEN", "daten"))


_BETRIEB = None
_BETRIEB_SPERRE = __import__("threading").Lock()


def betrieb():
    """Gemeinsame Taktbremse und Statistik für alle Prozesse, die den Schlüssel nutzen (siehe betrieb.py)."""
    global _BETRIEB
    with _BETRIEB_SPERRE:
        if _BETRIEB is None:
            from .betrieb import Betrieb
            _BETRIEB = Betrieb(daten_ordner() / "betrieb.sqlite", ANFRAGEN_PRO_MINUTE)
        return _BETRIEB


def _pause_aus(antwort) -> float:
    """Wie lange die Plattform warten lässt: Retry-After in Sekunden, sonst eine Minute (das Fenster des Limits)."""
    try:
        return max(1.0, float(antwort.headers.get("retry-after", "")))
    except ValueError:
        return 60.0


def http_client(zeitlimit: float, transport=None):
    """HTTP-Client für alle Anfragen an die Plattform. Jede Anfrage (auch Wiederholungen nach Fehlern) wartet vorher auf
    die gemeinsame Taktbremse; lehnt die Plattform mit 429 ab, pausieren alle Prozesse (Notbremse)."""
    import httpx

    def vorher(anfrage) -> None:
        betrieb().bremsen("embedding" if anfrage.url.path.endswith("/embeddings") else "chat")

    def nachher(antwort) -> None:
        if antwort.status_code == 429:
            betrieb().abgelehnt(_pause_aus(antwort))

    return httpx.Client(timeout=zeitlimit, transport=transport, event_hooks={"request": [vorher], "response": [nachher]})


def _mit_gedanken_klasse():
    """ChatOpenAI, das die Gedanken des Modells (Feld reasoning_content der Plattform) beim Streaming mitliefert.
    LangChain verwirft das Feld sonst; die Plattform schickt die Gedanken ab der ersten Sekunde, den Text erst danach."""
    from langchain_core.messages import AIMessageChunk
    from langchain_openai import ChatOpenAI

    class ChatMitGedanken(ChatOpenAI):
        def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
            stueck = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)
            wahl = (chunk.get("choices") or [{}])[0] or {}
            gedanke = (wahl.get("delta") or {}).get("reasoning_content")
            if stueck is not None and gedanke and isinstance(stueck.message, AIMessageChunk):
                stueck.message.additional_kwargs["reasoning_content"] = gedanke
            return stueck

    return ChatMitGedanken


def chat_modell(name: str = "deepseek", denken: bool = False):
    """LangChain-Chatmodell auf der Swiss AI Platform (OpenAI-kompatibel), mit Taktbremse fürs Ratenlimit."""
    from langchain_openai import ChatOpenAI
    klasse = _mit_gedanken_klasse() if denken else ChatOpenAI
    return klasse(
        model=MODELLE.get(name, name),
        base_url=SWISSAI_URL,
        api_key=os.environ.get("SWISSAI_API_KEY", "fehlt"),
        temperature=0.2,
        max_tokens=32000 if denken else 3000,  # mit Reasoning das volle Denkbudget
        # Ohne Zeitlimit wartet ein hängender Aufruf ewig. Mit Reasoning darf eine Antwort lange denken.
        timeout=ZEITLIMIT_DENKEN if denken else ZEITLIMIT_SCHNELL,
        max_retries=2,
        http_client=http_client(ZEITLIMIT_DENKEN if denken else ZEITLIMIT_SCHNELL),  # mit Taktbremse und Notbremse
        # Denkmodus über die Chat-Vorlage (DeepSeek: thinking, Qwen/GLM: enable_thinking)
        extra_body={"chat_template_kwargs": {"thinking": denken, "enable_thinking": denken}},
    )
