"""Tests ohne Netz: kleine Beispieldokumente und ein simuliertes Sprachmodell."""
import datetime as dt
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from studienassistent.agent import Pruefung, baue_agent, fragen
from studienassistent.bewertung import fakten_ok
from studienassistent.einlesen import einlesen, laden, speichern, zerlegen
from studienassistent.fristen import Fristen
from studienassistent.suche import Suche

DATEN = Path(__file__).parent / "daten"


class FakeModell(BaseChatModel):
    """Antwortet der Reihe nach mit vorbereiteten Nachrichten; die Eingangsprüfung lehnt Nachrichten mit «Rezept» ab."""
    antworten: list = []
    gesehen: list = []

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.gesehen.append(messages)
        return ChatResult(generations=[ChatGeneration(message=self.antworten.pop(0))])

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        return RunnableLambda(lambda msgs: Pruefung(erlaubt="Rezept" not in msgs[-1].content, grund="kein Studienbezug"))


def test_einlesen_mit_modul_und_quelle(tmp_path):
    abschnitte = einlesen([DATEN])
    assert {a.modul for a in abschnitte} == {"Generative KI", "Marketing"}
    speichern(abschnitte, tmp_path / "a.jsonl")
    wieder = laden(tmp_path / "a.jsonl")
    assert wieder[0].quelle().startswith("Generative KI · semesterprogramm.md")
    assert all(len(t) <= 900 for t in zerlegen("Satz. " * 600))


def test_suche_findet_die_richtige_stelle_und_filtert_nach_modul():
    suche = Suche(einlesen([DATEN]))
    assert suche.suchen("Wann ist die Abschlusspräsentation?", k=1)[0][0].modul == "Generative KI"
    assert suche.suchen("Projektbericht", k=3, modul="Marketing")[0][0].modul == "Marketing"


def test_fristen_nach_zeitraum_und_modul():
    f = Fristen([{"date": "2026-11-23", "sort": "2026-11-23", "module": "Generative KI", "title": "Präsentation"},
                 {"date": "Januar", "module": "Mensch-KI", "title": "Prüfung"},
                 {"date": "2026-12-23", "sort": "2026-12-23", "module": "Marketing", "title": "Projektbericht"}])
    assert [e["title"] for e in f.suchen(ab="2026-11-01", bis="2026-11-30")] == ["Präsentation"]
    assert len(f.suchen()) == 3 and f.suchen(modul="marketing")[0]["title"] == "Projektbericht"


def test_agent_sucht_und_antwortet_mit_quelle():
    modell = FakeModell(antworten=[
        AIMessage("", tool_calls=[{"name": "unterlagen_durchsuchen", "args": {"frage": "Abschlusspräsentation"}, "id": "1"}]),
        AIMessage("Am 23.11.2026 um 13.00 Uhr, 10 Minuten (Quelle: Generative KI · semesterprogramm.md)."),
        AIMessage("Ja, inklusive Verständnisfragen."),
    ], gesehen=[])
    graph = baue_agent(modell, Suche(einlesen([DATEN])), Fristen([]), heute=dt.date(2026, 10, 5))
    r = fragen(graph, "Wann ist die GenAI-Präsentation?", "t1")
    assert r["werkzeuge"] == ["unterlagen_durchsuchen"] and "semesterprogramm.md" in r["quellen"][0]
    assert "23.11.2026" in r["antwort"] and not r["abgelehnt"]
    assert "Heute ist 2026-10-05 (Montag)" in modell.gesehen[0][0].content
    # Gedächtnis: die Rückfrage im selben Gespräch sieht den bisherigen Verlauf
    fragen(graph, "Und mit Fragen?", "t1")
    assert any("Wann ist die GenAI-Präsentation?" in str(m.content) for m in modell.gesehen[-1])


def test_pruefung_lehnt_themen_ohne_studienbezug_ab():
    modell = FakeModell(antworten=[], gesehen=[])
    graph = baue_agent(modell, Suche(einlesen([DATEN])), Fristen([]))
    r = fragen(graph, "Schreib mir ein Rezept für Lasagne.")
    assert r["abgelehnt"] and "Studium" in r["antwort"] and not modell.gesehen  # das Hauptmodell wird gar nicht gefragt


def test_fakten_vergleich():
    assert fakten_ok("Abgabe am 20. Dezember 2026", [["20.12", "20. Dezember"]])
    assert not fakten_ok("Abgabe im Dezember", ["20.12"])
    from studienassistent.bewertung import quelle_genannt
    assert quelle_genannt("Am 23.11. (Quelle: Generative KI · plan.pdf, S. 1).") and not quelle_genannt("Am 23.11.")


def test_module_zuordnen_und_weglassen():
    abschnitte = einlesen([DATEN], {"GenAI": ["Generative"]})
    assert {a.modul for a in abschnitte} == {"GenAI"}  # Marketing ist nicht zugeordnet und fällt weg


def test_hybrid_suche_mit_embeddings():
    import numpy as np

    def einbetten(texte, merken=True):  # Spielzeug-Embedding: Buchstabenhäufigkeiten, normiert
        m = np.array([[t.lower().count(c) for c in "abcdefghijklmnopqrstuvwxyzäöü"] for t in texte], dtype=np.float32)
        return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)

    suche = Suche(einlesen([DATEN]), einbetten)
    assert suche.vektoren.shape[0] == len(suche.abschnitte)
    assert suche.suchen("Wann ist die Abschlusspräsentation?", k=1)[0][0].modul == "Generative KI"


def test_einbetter_mit_praefixen_wie_embeddinggemma():
    """EmbeddingGemma 2 braucht «title: … | text: …» für Dokumente und «task: search result | query: …» für Anfragen."""
    import numpy as np
    gesehen = []

    def einbetten(texte, merken=True):
        gesehen.extend(texte)
        return np.ones((len(texte), 4), dtype=np.float32) / 2

    einbetten.dokument_vorlage = "title: {modul} · {datei} | text: {text}"
    einbetten.anfrage_vorlage = "task: search result | query: {anfrage}"
    suche = Suche(einlesen([DATEN]), einbetten)
    suche.suchen("Wann ist die Präsentation?", k=1)
    assert gesehen[0].startswith("title: Generative KI · semesterprogramm.md | text: ")
    assert gesehen[-1] == "task: search result | query: Wann ist die Präsentation?"


def test_einbetter_wahl_ueber_umgebungsvariable(tmp_path, monkeypatch):
    from studienassistent.suche import einbetter
    monkeypatch.setenv("STUDIENASSISTENT_EMBEDDINGS", "lokal")
    e = einbetter(tmp_path / "embeddings.json")
    assert e.anfrage_vorlage.startswith("task: search result")  # ohne Netz: nur erzeugt, nichts angefragt
    monkeypatch.setenv("STUDIENASSISTENT_EMBEDDINGS", "swissai")
    monkeypatch.delenv("SWISSAI_API_KEY", raising=False)
    assert einbetter(tmp_path / "embeddings.json") is None  # ohne Schlüssel bleibt es bei BM25


def test_taktbremse_wartet_erst_am_limit_auch_ueber_prozesse(tmp_path):
    from studienassistent.betrieb import Betrieb
    app, update_job = Betrieb(tmp_path / "b.sqlite", 3), Betrieb(tmp_path / "b.sqlite", 3)  # zwei Prozesse, eine Datei
    assert [app.warten(), update_job.warten("embedding"), app.warten()] == [0.0, 0.0, 0.0]  # die ersten drei sofort
    assert 59 < app.warten() <= 60.1 and 59 < update_job.warten() <= 60.1  # die vierte erst, wenn die erste rausfällt
    assert app.lage()["aufrufe_minute"] == 3


def test_besucher_und_fragen_zaehlen(tmp_path):
    import time
    from studienassistent.betrieb import Betrieb
    b = Betrieb(tmp_path / "b.sqlite", 14)
    b.lebenszeichen("anna"), b.lebenszeichen("ben"), b.lebenszeichen("anna")
    b.frage_erledigt("anna", time.time() - 12)
    lage = b.lage()
    assert (lage["aktiv"], lage["besucher_heute"], lage["fragen_heute"], lage["fragende_heute"]) == (2, 2, 1, 1)
    assert 11 < lage["schnitt_sekunden"] < 14
    b.bewerten("a1", True), b.bewerten("a2", False), b.bewerten("a2", True), b.bewerten("a3", False), b.bewerten("a3", None)
    assert (b.lage()["daumen_hoch"], b.lage()["daumen_runter"]) == (2, 0)  # umentschieden und zurückgenommen zählt richtig


def test_warteschlange_der_reihe_nach():
    from studienassistent.betrieb import Warteschlange
    s = Warteschlange(plaetze=2)
    a, b, c, d = (s.anstellen() for _ in range(4))
    assert [s.position(n) for n in (a, b, c, d)] == [0, 0, 1, 2]  # zwei dürfen, die anderen warten
    assert s.position(d) == 2 and s.zustand() == (2, 2)            # d kann nicht vordrängeln
    s.fertig(a)
    assert s.position(d) == 2 and s.position(c) == 0 and s.position(d) == 1
    s.fertig(d)  # wer die Seite schliesst, verlässt die Schlange
    assert s.zustand() == (2, 0)


def test_fragen_live_liefert_werkzeug_und_ergebnis():
    from studienassistent.agent import fragen_live
    modell = FakeModell(antworten=[
        AIMessage("", tool_calls=[{"name": "unterlagen_durchsuchen", "args": {"frage": "Präsentation"}, "id": "1"}]),
        AIMessage("Am 23.11.2026 (Quelle: Generative KI · semesterprogramm.md)."),
    ], gesehen=[])
    graph = baue_agent(modell, Suche(einlesen([DATEN])), Fristen([]))
    ereignisse = list(fragen_live(graph, "Wann ist die GenAI-Präsentation?", "live"))
    assert ereignisse[-1][0] == "fertig" and "23.11.2026" in ereignisse[-1][1]["antwort"]
    assert ereignisse[-1][1]["werkzeuge"] == ["unterlagen_durchsuchen"]


def _suche(i):
    return AIMessage("", tool_calls=[{"name": "unterlagen_durchsuchen", "args": {"frage": f"Abschlusspräsentation {i}"},
                                      "id": f"s{i}"}])


def test_nach_drei_suchrunden_wird_geantwortet_statt_abgebrochen():
    from studienassistent.agent import MAX_SUCHRUNDEN
    from studienassistent.prompts import JETZT_ANTWORTEN
    modell = FakeModell(antworten=[_suche(i) for i in range(MAX_SUCHRUNDEN)] + [AIMessage("Das Projekt braucht … (Quelle: x)")],
                        gesehen=[])
    graph = baue_agent(modell, Suche(einlesen([DATEN])), Fristen([]))
    r = fragen(graph, "Was muss das Projekt beinhalten?", "runden")
    assert len(r["werkzeuge"]) == MAX_SUCHRUNDEN and r["antwort"].startswith("Das Projekt braucht")
    assert modell.gesehen[-1][-1].content == JETZT_ANTWORTEN  # die letzte Runde war ohne Werkzeuge erzwungen
    # Die Grenze gilt pro Frage: die nächste Frage darf wieder suchen
    modell.antworten += [_suche(9), AIMessage("Am 23.11.2026.")]
    assert fragen(graph, "Und wann ist die Präsentation?", "runden")["werkzeuge"] == ["unterlagen_durchsuchen"]


def test_mit_reasoning_denkt_nur_die_antwort():
    schnell = FakeModell(antworten=[_suche(1), AIMessage("Entwurf ohne Nachdenken")], gesehen=[])
    denker = FakeModell(antworten=[AIMessage("Durchdachte Antwort (Quelle: Generative KI · semesterprogramm.md)")], gesehen=[])
    graph = baue_agent(schnell, Suche(einlesen([DATEN])), Fristen([]), denkmodell=denker)
    r = fragen(graph, "Wann ist die GenAI-Präsentation?", "denken")
    assert r["antwort"].startswith("Durchdachte Antwort") and r["werkzeuge"] == ["unterlagen_durchsuchen"]
    assert len(denker.gesehen) == 1  # Prüfung und Suche liefen über das schnelle Modell
    gesehen = " ".join(str(m.content) for m in denker.gesehen[0])
    assert "semesterprogramm.md" in gesehen and "Entwurf" not in gesehen  # Treffer ja, Entwurf nein
    verlauf = graph.get_state({"configurable": {"thread_id": "denken"}}).values["messages"]
    assert not any("Entwurf" in str(m.content) for m in verlauf)  # der Entwurf bleibt nicht im Gedächtnis


def test_fragen_live_meldet_denken_und_zeigt_nur_die_endantwort():
    from studienassistent.agent import fragen_live
    schnell = FakeModell(antworten=[_suche(1), AIMessage("Entwurf")], gesehen=[])
    denker = FakeModell(antworten=[AIMessage("Endantwort")], gesehen=[])
    graph = baue_agent(schnell, Suche(einlesen([DATEN])), Fristen([]), denkmodell=denker)
    ereignisse = list(fragen_live(graph, "Wann ist die GenAI-Präsentation?", "live-denken"))
    arten = [a for a, _ in ereignisse]
    assert arten.index("werkzeug") < arten.index("denken") < len(arten) - 1
    nach_denken = "".join(i for a, i in ereignisse[arten.index("denken"):] if a == "text")
    assert nach_denken == "Endantwort" and ereignisse[-1][1]["antwort"] == "Endantwort"
    assert not any(a == "text" and "Entwurf" in i for a, i in ereignisse)  # der Entwurf wird gar nicht angezeigt


def test_notbremse_statt_absturz(monkeypatch):
    import studienassistent.agent as agent_modul
    monkeypatch.setattr(agent_modul, "REKURSIONSGRENZE", 2)
    modell = FakeModell(antworten=[_suche(1), _suche(2)], gesehen=[])
    graph = baue_agent(modell, Suche(einlesen([DATEN])), Fristen([]))
    assert fragen(graph, "Was muss das Projekt beinhalten?", "notbremse")["antwort"] == agent_modul.ABBRUCH
    ereignisse = list(agent_modul.fragen_live(graph, "Nochmals?", "notbremse"))
    assert ereignisse[-1] == ("fertig", ereignisse[-1][1]) and ereignisse[-1][1]["antwort"] == agent_modul.ABBRUCH


def test_gefundene_stellen_fuer_die_anzeige():
    from studienassistent.stellen import als_markdown, suchbegriffe, zerlegen
    suche_1 = ("[1] Generative KI · semesterprogramm.pdf, S. 1\nAbschluss  präsentation am 23.11.\n\n"
               "[2] Marketing · plan.pdf, S. 4\nuellen Beitrag.\n\nAbgabe\n\nPräsentation *25 Min.*")
    suche_2 = "[1] Generative KI · semesterprogramm.pdf, S. 1\nAbschluss  präsentation am 23.11."  # doppelt
    termine = ("- 2026-11-23 13:00 · Generative KI: Abschlusspräsentation (Beleg: Folie 4)\n"
               "- 2026-11-30 / 2026-12-07 · Marketing: Schlusspräsentation, Slot unbekannt (Beleg: S. 1)\nKeine passende Stelle.")
    antwort = "Am 23.11. (Quelle: Generative KI · semesterprogramm.pdf, S. 1)."
    stellen, fristen = zerlegen([suche_1, suche_2, termine, "- Marketing\n- Generative KI"], antwort)
    assert [(s.datei, s.seite, s.zitiert) for s in stellen] == [("semesterprogramm.pdf", 1, True), ("plan.pdf", 4, False)]
    assert stellen[0].text == "Abschluss präsentation am 23.11."  # Leerraum geglättet
    assert stellen[1].text == "… Beitrag. Abgabe Präsentation *25 Min.*"  # Absätze im Treffer bleiben, Wortrest weg
    assert [(f.datum, f.zeit, f.modul, f.titel) for f in fristen] == [
        ("2026-11-23", "13:00", "Generative KI", "Abschlusspräsentation"),
        ("2026-11-30 / 2026-12-07", "", "Marketing", "Schlusspräsentation, Slot unbekannt")]
    # andere Seite derselben Datei gilt nicht als zitiert
    assert not zerlegen(["[1] Marketing · plan.pdf, S. 9\nx"], "(Quelle: Marketing · plan.pdf, S. 4)")[0][0].zitiert
    assert suchbegriffe("Wann ist die Präsentation in Marketing?") == ["präsentation", "marketing"]
    assert als_markdown("Präsentation *25 Min.*", ["präsentation"]) == r"**Präsentation** \*25 Min.\*"
    assert als_markdown("wort " * 200, []).endswith(" …")


def test_app_ist_gueltiges_python():
    import ast
    ast.parse((Path(__file__).parent.parent / "studienassistent" / "app.py").read_text(encoding="utf-8"))


def test_notbremse_bei_429_und_jede_anfrage_zaehlt(tmp_path, monkeypatch):
    import httpx

    import studienassistent.konfig as konfig
    from studienassistent.betrieb import Betrieb
    b = Betrieb(tmp_path / "b.sqlite", 5)
    monkeypatch.setattr(konfig, "_BETRIEB", b)
    antworten = iter([httpx.Response(429, headers={"retry-after": "30"}), httpx.Response(200), httpx.Response(200)])
    client = konfig.http_client(5, transport=httpx.MockTransport(lambda anfrage: next(antworten)))
    assert client.post("https://x/v1/chat/completions").status_code == 429
    lage = b.lage()
    assert lage["abgelehnt_heute"] == 1 and 29 < lage["pause_noch"] <= 30  # alle Prozesse pausieren 30 s
    assert lage["aufrufe_minute"] == 1  # die Anfrage selbst ist in der Taktbremse gezählt
    assert 29 < b.warten() <= 30                                             # auch eine neue Anfrage muss warten


def test_app_verlangt_passwort_wenn_gesetzt(monkeypatch):
    import pytest
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("STUDIENASSISTENT_PASSWORT", "geheim")
    app = AppTest.from_file(str(Path(__file__).parent.parent / "studienassistent" / "app.py"), default_timeout=30).run()
    assert app.text_input[0].label == "Passwort" and not app.chat_input  # ohne Passwort keine App (und kein Modell)
    app.text_input[0].input("falsch")
    app.button[0].click().run()
    assert app.error and not app.chat_input


def test_qr_link_meldet_direkt_an(monkeypatch, tmp_path):
    import pytest
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    speichern(einlesen([DATEN]), tmp_path / "abschnitte.jsonl")  # kleine Testunterlagen statt der echten
    monkeypatch.setenv("STUDIENASSISTENT_DATEN", str(tmp_path))
    monkeypatch.setenv("STUDIENASSISTENT_PASSWORT", "geheim")
    monkeypatch.delenv("SWISSAI_API_KEY", raising=False)
    datei = str(Path(__file__).parent.parent / "studienassistent" / "app.py")

    app = AppTest.from_file(datei, default_timeout=60)
    app.query_params["zugang"] = "geheim"
    app.run()
    assert not app.exception and app.chat_input and not app.text_input  # direkt im Chat, keine Passwortabfrage
    assert app.query_params.get("zugang") in (None, [], "")              # Code aus der Adresszeile entfernt

    falsch = AppTest.from_file(datei, default_timeout=60)
    falsch.query_params["zugang"] = "falsch"
    falsch.run()
    assert falsch.text_input[0].label == "Passwort" and not falsch.chat_input


def test_nach_der_suche_direkt_zur_antwort_mit_gedanken():
    from studienassistent.agent import fragen_live
    schnell = FakeModell(antworten=[_suche(1)], gesehen=[])
    denker = FakeModell(antworten=[AIMessage("Am 23.11.", additional_kwargs={"reasoning_content": "Ich prüfe die Treffer …"})],
                        gesehen=[])
    graph = baue_agent(schnell, Suche(einlesen([DATEN])), Fristen([]), denkmodell=denker)
    ereignisse = list(fragen_live(graph, "Wann ist die GenAI-Präsentation?", "direkt"))
    assert len(schnell.gesehen) == 1  # das schnelle Modell nur einmal: kein zweiter Entwurf nach der Suche
    assert ("gedanke", "Ich prüfe die Treffer …") in ereignisse
    assert any(m.type == "tool" for m in denker.gesehen[0])  # das Denkmodell sieht die Suchtreffer
    assert ereignisse[-1][1]["antwort"] == "Am 23.11."


def test_gedanken_der_plattform_kommen_durch():
    from studienassistent.konfig import _mit_gedanken_klasse
    from langchain_core.messages import AIMessageChunk
    modell = _mit_gedanken_klasse()(model="m", api_key="x", base_url="http://x")
    stueck = modell._convert_chunk_to_generation_chunk(
        {"choices": [{"index": 0, "delta": {"role": "assistant", "content": "", "reasoning_content": "Hm, Montag …"}}]},
        AIMessageChunk, {})
    assert stueck.message.additional_kwargs["reasoning_content"] == "Hm, Montag …"
