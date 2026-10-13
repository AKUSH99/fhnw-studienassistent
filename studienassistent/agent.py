"""Der Agent als LangGraph-Graph.

    START → pruefen ──(erlaubt)──▶ agent ⇄ werkzeuge
              │                      ├──(fertig, ohne Reasoning)──▶ END
              │                      └──(fertig, mit Reasoning)───▶ antworten ──▶ END
              └──(nicht erlaubt)──▶ END

- pruefen: Guardrail – Manipulationsversuche, Themen ohne Studienbezug und «schreib meine Abgabe» werden abgelehnt.
- agent: das Sprachmodell mit drei Werkzeugen (Unterlagen durchsuchen, Fristen, Module); es entscheidet selbst, welches
  Werkzeug es braucht, und kann mehrmals suchen.
- werkzeuge: führt die Aufrufe aus und gibt die Treffer mit Quellen zurück.
- antworten: nur mit Reasoning. Prüfen und Suchen erledigt das schnelle Modell; erst die Antwort schreibt das denkende
  Modell aus den gefundenen Stellen. So denkt es einmal statt in jeder Suchrunde.
Nach MAX_SUCHRUNDEN Suchrunden muss der Agent mit dem antworten, was er gefunden hat.
Gedächtnis: Der Checkpointer speichert den Gesprächsverlauf pro `thread_id`, so funktionieren Rückfragen.
"""
from __future__ import annotations

import datetime as dt

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langgraph.errors import GraphRecursionError
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

from . import prompts
from .fristen import Fristen
from .suche import Suche
from .werkzeuge import erstelle_werkzeuge

MAX_SUCHRUNDEN = 3
# pruefen + je Suchrunde agent und werkzeuge + letzter agent + antworten, mit Reserve
REKURSIONSGRENZE = 2 * MAX_SUCHRUNDEN + 6
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class Pruefung(BaseModel):
    erlaubt: bool = Field(description="True, wenn der Assistent auf die Nachricht eingehen darf")
    grund: str = Field(description="kurze Begründung, ein Satz")


class Zustand(MessagesState):
    erlaubt: bool


def baue_agent(modell, suche: Suche, fristen: Fristen, heute: dt.date | None = None, gedaechtnis=None, denkmodell=None,
               werkzeuge: list | None = None):
    """Kompilierter Graph. `modell`: ein LangChain-Chatmodell mit Werkzeug-Unterstützung (z. B. konfig.chat_modell()),
    zuständig für Prüfung und Suche. `denkmodell`: optional ein Modell mit Reasoning, das nur die Antwort schreibt."""
    werkzeuge = werkzeuge or erstelle_werkzeuge(suche, fristen)  # z. B. über MCP (mcp_client.py) oder direkt
    mit_werkzeugen = modell.bind_tools(werkzeuge)
    # Über einen Werkzeugaufruf statt JSON-Schema: bei GLM mit Reasoning viel schneller, und Gedankentext stört nicht
    pruefer = modell.with_structured_output(Pruefung, method="function_calling")

    def system() -> SystemMessage:
        tag = heute or dt.date.today()
        return SystemMessage(prompts.SYSTEM.format(heute=tag.isoformat(), wochentag=WOCHENTAGE[tag.weekday()],
                                                   module=", ".join(suche.module())))

    def pruefen(zustand: Zustand) -> dict:
        try:
            ergebnis = pruefer.invoke([SystemMessage(prompts.PRUEFEN), zustand["messages"][-1]])
        except Exception:  # noqa: BLE001 – fällt die Prüfung aus, entscheidet der Agent mit seinen eigenen Regeln
            return {"erlaubt": True}
        if ergebnis.erlaubt:
            return {"erlaubt": True}
        return {"erlaubt": False, "messages": [AIMessage(prompts.ABLEHNUNG.format(grund=ergebnis.grund))]}

    def suchrunden(zustand: Zustand) -> int:
        nachrichten = zustand["messages"]
        letzte_frage = max((i for i, m in enumerate(nachrichten) if isinstance(m, HumanMessage)), default=0)
        return sum(1 for m in nachrichten[letzte_frage:] if getattr(m, "tool_calls", None))

    def agent(zustand: Zustand) -> dict:
        if suchrunden(zustand) >= MAX_SUCHRUNDEN:  # genug gesucht: ohne Werkzeuge antworten
            if denkmodell is not None:
                return {"messages": [AIMessage("")]}  # Platzhalter, die Antwort schreibt gleich das Denkmodell
            return {"messages": [modell.invoke([system()] + zustand["messages"] + [SystemMessage(prompts.JETZT_ANTWORTEN)])]}
        return {"messages": [mit_werkzeugen.invoke([system()] + zustand["messages"])]}

    def antworten(zustand: Zustand) -> dict:
        # Kommt es direkt von der Suche, ist die letzte Nachricht das Suchergebnis und bleibt. Hat das schnelle Modell
        # ohne Suche geantwortet, ist die letzte Nachricht sein Entwurf: Den sieht das Denkmodell nicht, er wird ersetzt.
        letzte = zustand["messages"][-1]
        ist_entwurf = isinstance(letzte, AIMessage) and not getattr(letzte, "tool_calls", None)
        verlauf = zustand["messages"][:-1] if ist_entwurf else zustand["messages"]
        antwort = denkmodell.invoke([system()] + verlauf + [SystemMessage(prompts.JETZT_ANTWORTEN)])
        return {"messages": ([RemoveMessage(id=letzte.id)] if ist_entwurf else []) + [antwort]}

    def nach_agent(zustand: Zustand) -> str:
        if tools_condition(zustand) == "tools":
            return "werkzeuge"
        return "antworten" if denkmodell is not None else END

    g = StateGraph(Zustand)
    g.add_node("pruefen", pruefen)
    g.add_node("agent", agent)
    g.add_node("werkzeuge", ToolNode(werkzeuge))
    g.add_edge(START, "pruefen")
    g.add_conditional_edges("pruefen", lambda z: "agent" if z["erlaubt"] else END, ["agent", END])
    ziele = ["werkzeuge", END]
    if denkmodell is not None:
        g.add_node("antworten", antworten)
        g.add_edge("antworten", END)
        ziele.append("antworten")
    g.add_conditional_edges("agent", nach_agent, ziele)
    # Mit Denkmodell nach der Suche direkt zur Antwort: Eine zweite Runde des schnellen Modells würde nur einen
    # Entwurf schreiben, der verworfen wird (4 bis 9 s). Mehrere Suchen gehen trotzdem, parallel im selben Schritt.
    g.add_edge("werkzeuge", "antworten" if denkmodell is not None else "agent")
    return g.compile(checkpointer=gedaechtnis or MemorySaver())


def _ergebnis(werte: dict, vorher: int) -> dict:
    neu = werte["messages"][vorher:]
    quellen = [m.content for m in neu if getattr(m, "type", "") == "tool"]
    aufrufe = [c["name"] for m in neu if getattr(m, "tool_calls", None) for c in m.tool_calls]
    return {"antwort": werte["messages"][-1].content, "quellen": quellen, "werkzeuge": aufrufe,
            "abgelehnt": not werte.get("erlaubt", True)}


def _konfig(thread_id: str) -> dict:
    # run_name und Metadaten erscheinen im LangSmith-Tracing (eingeschaltet mit LANGSMITH_TRACING=true)
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": REKURSIONSGRENZE,
            "run_name": "Studienassistent", "metadata": {"gespraech": thread_id}}


ABBRUCH = "Ich habe zu lange gesucht und keine Antwort gefunden. Stell die Frage bitte genauer, zum Beispiel mit dem Modul."


def _abbruch(graph, konfig: dict, vorher: int) -> dict:
    """Notbremse, falls der Graph trotz Suchrunden-Grenze nicht fertig wird: Hinweis statt Absturz."""
    ergebnis = _ergebnis(graph.get_state(konfig).values, vorher)
    graph.update_state(konfig, {"messages": [AIMessage(ABBRUCH)]})
    return ergebnis | {"antwort": ABBRUCH}


def fragen(graph, text: str, thread_id: str = "standard") -> dict:
    """Eine Frage stellen; gibt Antwort und die genutzten Quellen-Auszüge zurück."""
    konfig = _konfig(thread_id)
    vorher = len(graph.get_state(konfig).values.get("messages", []))
    try:
        return _ergebnis(graph.invoke({"messages": [("user", text)]}, config=konfig), vorher)
    except GraphRecursionError:
        return _abbruch(graph, konfig, vorher)


def fragen_live(graph, text: str, thread_id: str = "standard"):
    """Wie fragen(), aber als Generator für die Chat-Oberfläche: liefert ("text", Stück) während die Antwort entsteht,
    ("werkzeug", Name) wenn der Agent sucht, ("denken", None) wenn das Denkmodell die Antwort schreibt (der bisherige
    Text war dann nur ein Entwurf), ("gedanke", Stück) für dessen Gedanken, ("schritt", Knoten) und ("schritt_fertig",
    Knoten) wenn ein Knoten des Graphen startet bzw. fertig ist (für das Live-Diagramm, siehe ablauf.py), und zum Schluss
    ("fertig", Ergebnis wie bei fragen())."""
    konfig = _konfig(thread_id)
    vorher = len(graph.get_state(konfig).values.get("messages", []))
    mit_denkmodell = "antworten" in graph.nodes
    try:
        for modus, daten in graph.stream({"messages": [("user", text)]}, config=konfig, stream_mode=["tasks", "updates", "messages"]):
            if modus == "tasks":  # Start ohne «result», Ende mit «result»
                yield ("schritt_fertig" if "result" in daten else "schritt"), daten["name"]
                continue
            if modus == "updates":
                # Suche fertig bzw. Agent braucht keine: Jetzt schreibt das Denkmodell die Antwort.
                letzte = ((daten.get("agent") or {}).get("messages") or [None])[-1]
                if mit_denkmodell and ("werkzeuge" in daten or (letzte is not None and not getattr(letzte, "tool_calls", None))):
                    yield "denken", None
                continue
            stueck, meta = daten
            if meta.get("langgraph_node") not in ("agent", "antworten"):
                continue
            gedanke = (getattr(stueck, "additional_kwargs", None) or {}).get("reasoning_content")
            if gedanke and meta["langgraph_node"] == "antworten":
                yield "gedanke", gedanke
            for aufruf in getattr(stueck, "tool_call_chunks", None) or getattr(stueck, "tool_calls", None) or []:
                if aufruf.get("name"):
                    yield "werkzeug", aufruf["name"]
            # Mit Denkmodell nur dessen Antwort zeigen: Der Text des schnellen Modells ist ein Entwurf (bei GLM ohne
            # Reasoning oft mit rohen Gedanken davor).
            if isinstance(stueck.content, str) and stueck.content and (meta["langgraph_node"] == "antworten" or not mit_denkmodell):
                yield "text", stueck.content
    except GraphRecursionError:
        yield "fertig", _abbruch(graph, konfig, vorher)
        return
    yield "fertig", _ergebnis(graph.get_state(konfig).values, vorher)
