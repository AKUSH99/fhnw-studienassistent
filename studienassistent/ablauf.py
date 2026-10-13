"""Der LangGraph-Graph als Bild, live eingefärbt: welche Schritte eine Frage durchläuft und wie lange jeder dauert.

Das Diagramm entsteht direkt aus dem kompilierten Graphen (`graph.get_graph()`), nicht aus einer Zeichnung von Hand:
Kommt ein Knoten dazu, erscheint er automatisch. Ausgabe ist Graphviz-DOT für `st.graphviz_chart`.

    schritte = Schritte()
    schritte.start("pruefen"); schritte.ende("pruefen")   # aus fragen_live: ("schritt", Name) / ("schritt_fertig", Name)
    dot(graph, schritte)                                   # Graphviz-Text, besuchte Knoten grün, laufender orange
"""
from __future__ import annotations

import time

NAMEN = {"__start__": "Frage", "__end__": "Antwort", "pruefen": "🛡️ Prüfen", "agent": "🤖 Agent",
         "werkzeuge": "🔎 Werkzeuge", "antworten": "🧠 Antworten"}
ERKLAERUNG = {"pruefen": "Guardrail: Gehört die Frage zum Studium?", "agent": "Sprachmodell entscheidet: suchen oder antworten",
              "werkzeuge": "Unterlagen, Fristen oder Module durchsuchen", "antworten": "Denkmodell schreibt die Antwort aus den Treffern"}
GRUEN, ORANGE, GRAU = "#2e7d32", "#ef6c00", "#9e9e9e"


class Schritte:
    """Merkt sich Reihenfolge und Dauer der Knoten einer Frage (ein Knoten kann mehrmals laufen, z. B. mehrere Suchen)."""

    def __init__(self, uhr=time.monotonic):
        self.uhr = uhr
        self.folge: list[str] = []          # Knoten in der Reihenfolge, in der sie gestartet sind
        self.dauer: dict[str, float] = {}   # Summe pro Knoten in Sekunden
        self.laeuft: dict[str, float] = {}  # Knoten, die gerade rechnen, mit Startzeit

    def start(self, name: str) -> None:
        self.folge.append(name)
        self.laeuft[name] = self.uhr()

    def ende(self, name: str) -> None:
        if name in self.laeuft:
            self.dauer[name] = self.dauer.get(name, 0.0) + self.uhr() - self.laeuft.pop(name)

    def anzahl(self, name: str) -> int:
        return self.folge.count(name)

    def zeile(self) -> str:
        """Kurzfassung für die Ablaufzeile, z. B. «🛡️ Prüfen 0.8 s → 🤖 Agent 2.1 s → 🔎 Werkzeuge 0.4 s»."""
        teile, gesehen = [], []
        for name in self.folge:
            if name in gesehen:
                continue
            gesehen.append(name)
            n = self.anzahl(name)
            teile.append(f"{NAMEN.get(name, name)}{f' ×{n}' if n > 1 else ''} {self.dauer.get(name, 0):.1f} s")
        return " → ".join(teile)


def _kanten_besucht(schritte: Schritte, fertig: bool) -> set[tuple[str, str]]:
    pfad = ["__start__"] + schritte.folge + (["__end__"] if fertig else [])
    return set(zip(pfad, pfad[1:]))


def dot(graph, schritte: Schritte, fertig: bool = False) -> str:
    """Graphviz-Text des Graphen: besuchte Knoten und Kanten grün (mit Dauer), der laufende Knoten orange, der Rest grau."""
    g = graph.get_graph()
    besucht = _kanten_besucht(schritte, fertig)
    zeilen = ['digraph G {', 'rankdir=LR; bgcolor="transparent"; pad=0.1; nodesep=0.3; ranksep=0.35;',
              'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, fontcolor="white", penwidth=0];',
              'edge [fontname="Helvetica", fontsize=9, arrowsize=0.6];']
    for name in g.nodes:
        rand = name in ("__start__", "__end__")
        if name in schritte.laeuft:
            farbe, text = ORANGE, f"{NAMEN.get(name, name)}\\n läuft …"
        elif name in schritte.dauer or (name == "__start__" and schritte.folge) or (name == "__end__" and fertig):
            n = schritte.anzahl(name)
            dauer = f"\\n{schritte.dauer[name]:.1f} s{f' · {n}×' if n > 1 else ''}" if name in schritte.dauer else ""
            farbe, text = GRUEN, NAMEN.get(name, name) + dauer
        else:
            farbe, text = GRAU, NAMEN.get(name, name)
        form = ', shape=ellipse' if rand else ''
        hilfe = ERKLAERUNG.get(name, "")
        zeilen.append(f'"{name}" [label="{text}", fillcolor="{farbe}", tooltip="{hilfe}"{form}];')
    for k in g.edges:
        aktiv = (k.source, k.target) in besucht
        art = "solid" if not k.conditional else "dashed"
        farbe = GRUEN if aktiv else GRAU
        zeilen.append(f'"{k.source}" -> "{k.target}" [color="{farbe}", style="{art}", penwidth={2.2 if aktiv else 1}];')
    zeilen.append("}")
    return "\n".join(zeilen)
