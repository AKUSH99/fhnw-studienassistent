"""Suche in den Kursunterlagen: BM25 (exakte Begriffe wie «Pitch Deck», «KW 48») und, wenn verfügbar, Embeddings
(Umschreibungen wie «Wann muss ich präsentieren?»), verbunden mit Reciprocal Rank Fusion. Optional nur in einem Modul.

Embeddings kommen von der Swiss AI Platform (Qwen3-Embedding-8B) und werden in <daten>/embeddings.npz gespeichert,
damit die Unterlagen nur einmal eingebettet werden. Ohne Schlüssel oder Netz bleibt es bei BM25.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from pathlib import Path

from .einlesen import Abschnitt

_STOPP = set("""der die das den dem des ein eine einer eines einem einen und oder aber nicht kein keine ist sind war wird
werden wurde zu zum zur im in am an auf aus bei mit von vor nach über unter für ohne um als wie auch nur noch schon so
sehr es er sie wir ihr ich du man sich dass wenn weil ob doch ja nein alle was wann wo wer wie welche welcher welches
mein meine muss müssen kann können soll the a an and or of to in on for with is are be""".split())


_MONATE = {m: i for i, m in enumerate("januar februar märz april mai juni juli august september oktober november dezember".split(), 1)}
_DATUM_ZAHL = re.compile(r"\b(\d{1,2})\.\s?(\d{1,2})\.")
_DATUM_WORT = re.compile(r"\b(\d{1,2})\.\s?(" + "|".join(_MONATE) + r")\b")


def daten(text: str) -> list[str]:
    """Datumsangaben als gemeinsames Token: «12.10.» und «12. Oktober» → d12_10."""
    t = text.lower()
    return ([f"d{int(tag)}_{int(monat)}" for tag, monat in _DATUM_ZAHL.findall(t) if 1 <= int(monat) <= 12]
            + [f"d{int(tag)}_{_MONATE[monat]}" for tag, monat in _DATUM_WORT.findall(t)])


def tokens(text: str) -> list[str]:
    woerter = [w for w in re.findall(r"[a-zäöüß0-9]+", text.lower()) if w not in _STOPP and len(w) > 1]
    return woerter + [w[:5] for w in woerter if len(w) > 6] + daten(text)  # Stammform für Komposita und Flexion


class BM25:
    def __init__(self, abschnitte: list[Abschnitt], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokens(f"{a.modul} {Path(a.datei).stem} {a.text}")) for a in abschnitte]
        self.laengen = [sum(c.values()) for c in self.docs]
        self.mittel = sum(self.laengen) / max(1, len(self.laengen))
        df = Counter(t for c in self.docs for t in c)
        n = len(abschnitte)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def werte(self, anfrage: str) -> list[float]:
        q = tokens(anfrage)
        out = []
        for i, c in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in c:
                    f = c[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.laengen[i] / self.mittel))
            out.append(s)
        return out


def swissai_einbetter(cache: Path, stapel: int = 32):
    """Embeddings über die Swiss AI Platform; Ergebnis als normierte NumPy-Matrix (float32), Cache als float16-npz.
    Der Cache wird laufend gespeichert, ein abgebrochener Lauf macht beim nächsten Mal weiter. None ohne Schlüssel."""
    if not os.environ.get("SWISSAI_API_KEY"):
        return None
    import numpy as np
    import openai

    from .konfig import EMBEDDING_MODELL, SWISSAI_URL, http_client
    client = openai.OpenAI(base_url=SWISSAI_URL, api_key=os.environ["SWISSAI_API_KEY"], max_retries=6,
                           http_client=http_client(60))  # Taktbremse und Notbremse wie beim Chat
    cache = cache.with_suffix(".npz")
    gespeichert: dict[str, np.ndarray] = {}
    if cache.exists():
        with np.load(cache) as d:
            gespeichert = dict(zip(d["schluessel"].tolist(), d["vektoren"]))
    schluessel = lambda t: hashlib.sha1(f"{EMBEDDING_MODELL}\n{t}".encode()).hexdigest()

    def sichern():  # erst in eine Hilfsdatei, dann umbenennen: nie eine halb geschriebene Datei
        cache.parent.mkdir(parents=True, exist_ok=True)
        hilfe = cache.with_name(f"{cache.stem}.{os.getpid()}.tmp.npz")
        np.savez(hilfe, schluessel=np.array(list(gespeichert)), vektoren=np.stack(list(gespeichert.values())))
        os.replace(hilfe, cache)

    def einbetten(texte: list[str], merken: bool = True) -> np.ndarray:
        """`merken=False` für Suchanfragen: nur die Unterlagen kommen in den Cache."""
        neu: dict[str, np.ndarray] = {}
        fehlend = [t for t in dict.fromkeys(texte) if schluessel(t) not in gespeichert]
        for nr, start in enumerate(range(0, len(fehlend), stapel), 1):
            teil = fehlend[start:start + stapel]
            antwort = client.embeddings.create(model=EMBEDDING_MODELL, input=teil)
            for t, d in zip(teil, sorted(antwort.data, key=lambda d: d.index)):
                neu[schluessel(t)] = np.asarray(d.embedding, dtype=np.float16)
            if merken:
                gespeichert.update(neu)
                if nr % 20 == 0:
                    sichern()
        if merken and fehlend:
            sichern()
        m = np.stack([neu.get(schluessel(t), gespeichert.get(schluessel(t))) for t in texte]).astype(np.float32)
        return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)

    return einbetten


class Suche:
    def __init__(self, abschnitte: list[Abschnitt], einbetten=None, rrf_k: int = 60):
        if not abschnitte:
            raise ValueError("Keine Unterlagen eingelesen – zuerst `python -m studienassistent einlesen <Ordner>`.")
        self.abschnitte = abschnitte
        self.bm25 = BM25(abschnitte)
        self.einbetten, self.rrf_k = einbetten, rrf_k
        self.vektoren = einbetten([f"{a.modul}: {a.text}" for a in abschnitte]) if einbetten else None

    def module(self) -> list[str]:
        return sorted({a.modul for a in self.abschnitte})

    def suchen(self, anfrage: str, k: int = 5, modul: str | None = None) -> list[tuple[Abschnitt, float]]:
        erlaubt = [i for i, a in enumerate(self.abschnitte) if not modul or modul.lower() in a.modul.lower()]
        if not erlaubt:
            erlaubt = list(range(len(self.abschnitte)))
        b = self.bm25.werte(anfrage)
        listen = [sorted((i for i in erlaubt if b[i] > 0), key=lambda i: -b[i])[:30]]
        if self.vektoren is not None:
            sim = self.vektoren[erlaubt] @ self.einbetten([anfrage], merken=False)[0]
            listen.append([erlaubt[j] for j in sim.argsort()[::-1][:30]])
        rrf: dict[int, float] = {}
        for liste in listen:
            for rang, i in enumerate(liste, 1):
                rrf[i] = rrf.get(i, 0.0) + 1.0 / (self.rrf_k + rang)
        return [(self.abschnitte[i], round(s, 4)) for i, s in sorted(rrf.items(), key=lambda kv: -kv[1])[:k]]
