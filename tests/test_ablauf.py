"""Live-Diagramm des Graphen: Schritte aus fragen_live, Einfärbung und Dauer im Graphviz-Text."""
from langchain_core.messages import AIMessage

from studienassistent.ablauf import GRAU, GRUEN, ORANGE, Schritte, dot
from studienassistent.agent import baue_agent, fragen_live
from studienassistent.einlesen import einlesen
from studienassistent.fristen import Fristen
from studienassistent.suche import Suche
from test_studienassistent import DATEN, FakeModell, _suche


def _knoten(text: str, name: str) -> str:
    return next(z for z in text.splitlines() if z.startswith(f'"{name}" ['))


def _graph():
    schnell = FakeModell(antworten=[_suche(1)], gesehen=[])
    denker = FakeModell(antworten=[AIMessage("Am 23.11.")], gesehen=[])
    return baue_agent(schnell, Suche(einlesen([DATEN])), Fristen([]), denkmodell=denker)


def test_fragen_live_meldet_jeden_knoten_mit_start_und_ende():
    ereignisse = list(fragen_live(_graph(), "Wann ist die GenAI-Präsentation?", "schritte"))
    schritte = [(a, i) for a, i in ereignisse if a in ("schritt", "schritt_fertig")]
    assert [i for a, i in schritte if a == "schritt"] == ["pruefen", "agent", "werkzeuge", "antworten"]
    assert schritte[0] == ("schritt", "pruefen") and schritte[1] == ("schritt_fertig", "pruefen")
    assert ereignisse[-1][0] == "fertig"  # das Ergebnis bleibt das letzte Ereignis


def test_diagramm_kommt_aus_dem_graphen_und_faerbt_live_ein():
    graph, uhr = _graph(), iter([0.0, 0.8, 1.0, 3.1, 3.2])
    schritte = Schritte(uhr=lambda: next(uhr))
    leer = dot(graph, schritte)
    for name in ("pruefen", "agent", "werkzeuge", "antworten", "__start__", "__end__"):
        assert f'"{name}" [' in leer  # alle Knoten des kompilierten Graphen, auch ohne Zeichnung von Hand
    assert GRUEN not in leer and ORANGE not in leer

    schritte.start("pruefen"); schritte.ende("pruefen"); schritte.start("agent"); schritte.ende("agent")
    schritte.start("werkzeuge")
    live = dot(graph, schritte)
    assert GRUEN in _knoten(live, "pruefen") and "0.8 s" in _knoten(live, "pruefen")
    assert ORANGE in _knoten(live, "werkzeuge") and GRAU in _knoten(live, "antworten")
    assert f'"pruefen" -> "agent" [color="{GRUEN}"' in live and f'"agent" -> "antworten" [color="{GRAU}"' in live
    assert schritte.zeile() == "🛡️ Prüfen 0.8 s → 🤖 Agent 2.1 s → 🔎 Werkzeuge 0.0 s"


def test_mehrere_suchrunden_werden_gezaehlt():
    uhr = iter(range(10))
    schritte = Schritte(uhr=lambda: next(uhr))
    for name in ("agent", "werkzeuge", "agent"):
        schritte.start(name); schritte.ende(name)
    assert schritte.anzahl("agent") == 2 and "🤖 Agent ×2 2.0 s" in schritte.zeile()
