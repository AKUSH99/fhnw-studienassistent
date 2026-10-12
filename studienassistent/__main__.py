"""Befehle des Studienassistenten.

    python -m studienassistent einlesen <Ordner> [<Ordner> …] [--fristen fristen.json]
    python -m studienassistent frage "Wann ist die GenAI-Präsentation?"
    python -m studienassistent app                 # Chat im Browser (Streamlit)
    python -m studienassistent bewerten            # Evaluation mit evaluation/fragen.jsonl
    python -m studienassistent mcp                 # Werkzeuge als MCP-Server (stdio)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from .konfig import daten_ordner


def lade_alles(modell_name: str = "deepseek", denken: bool = False, mcp: bool = True):
    from .agent import baue_agent
    from .einlesen import laden
    from .fristen import Fristen
    from .konfig import chat_modell
    from .suche import Suche, swissai_einbetter
    d = daten_ordner()
    datei = d / "abschnitte.jsonl"
    if not datei.exists():
        raise SystemExit(f"Keine Unterlagen in {datei} – zuerst: python -m studienassistent einlesen <Ordner>")
    suche = Suche(laden(datei), swissai_einbetter(d / "embeddings.json"))
    fristen = Fristen.laden(d / "fristen.json")
    # Mit Reasoning prüft und sucht das schnelle Modell; nur die Antwort schreibt das denkende (einmal statt pro Runde).
    denkmodell = chat_modell(modell_name, True) if denken else None
    # Werkzeuge über MCP: Der Agent ist Client des eigenen MCP-Servers (im selben Prozess, siehe mcp_client.py)
    werkzeuge = None
    if mcp:
        from .mcp_client import MCPWerkzeuge
        from .mcp_server import erstelle_server
        werkzeuge = MCPWerkzeuge(erstelle_server(suche, fristen)).werkzeuge
    return baue_agent(chat_modell(modell_name, False), suche, fristen, denkmodell=denkmodell, werkzeuge=werkzeuge), suche, fristen


def _einlesen(args) -> None:
    from .einlesen import einlesen, speichern
    d = daten_ordner()
    import json
    module = json.loads(Path(args.module).read_text(encoding="utf-8")) if args.module else None
    abschnitte = einlesen([Path(o) for o in args.ordner], module)
    speichern(abschnitte, d / "abschnitte.jsonl")
    if args.fristen:
        shutil.copy(args.fristen, d / "fristen.json")
    module = sorted({a.modul for a in abschnitte})
    print(f"{len(abschnitte)} Abschnitte aus {len({a.datei for a in abschnitte})} Dateien, {len(module)} Module → {d}")
    for m in module:
        print(f"  {m}: {sum(1 for a in abschnitte if a.modul == m)} Abschnitte")


def _frage(args) -> None:
    from .agent import fragen
    graph, _, _ = lade_alles(args.modell, args.denken)
    r = fragen(graph, args.text)
    print(r["antwort"])
    if args.quellen:
        print("\n--- Werkzeuge:", ", ".join(r["werkzeuge"]) or "keine")
        for q in r["quellen"]:
            print("\n" + q[:1500])


def _app(args) -> None:
    app = Path(__file__).with_name("app.py")
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), "--server.headless", "true",
                              "--server.port", str(args.port)] + (["--server.address", args.adresse] if args.adresse else [])))


def _mcp(args) -> None:
    from .mcp_server import erstelle_server
    _, suche, fristen = lade_alles()
    erstelle_server(suche, fristen).run()


def _bewerten(args) -> None:
    from .bewertung import bewerte, tabelle
    graph, suche, _ = lade_alles(args.modell, args.denken)
    ergebnis = bewerte(graph, suche, Path(args.testset), nur_suche=args.nur_suche)
    if args.ausgabe:
        import json
        from .bewertung import ohne_antworten
        Path(args.ausgabe).write_text(json.dumps(ohne_antworten(ergebnis) | {"modell": args.modell, "denken": args.denken},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(tabelle(ergebnis))


def main() -> int:
    p = argparse.ArgumentParser(prog="studienassistent", description="FHNW-Studienassistent")
    sub = p.add_subparsers(dest="befehl", required=True)
    s = sub.add_parser("einlesen", help="Kursunterlagen einlesen (PDF, PowerPoint, Word, Markdown)")
    s.add_argument("ordner", nargs="+")
    s.add_argument("--fristen", help="JSON-Liste mit Terminen (z. B. deadline-overview.json des Studienarchivs)")
    s.add_argument("--module", help="JSON: {Modulname: [Teil des Ordnernamens, …]} – saubere Namen, Rest weglassen")
    s.set_defaults(fn=_einlesen)
    for name, fn, hilfe in (("frage", _frage, "eine Frage stellen"), ("bewerten", _bewerten, "Evaluation mit Testfragen")):
        s = sub.add_parser(name, help=hilfe)
        if name == "frage":
            s.add_argument("text")
            s.add_argument("--quellen", action="store_true", help="gefundene Stellen mit ausgeben")
        else:
            s.add_argument("--testset", default="evaluation/fragen.jsonl")
            s.add_argument("--nur-suche", action="store_true", help="nur die Suche bewerten (ohne Sprachmodell)")
            s.add_argument("--ausgabe", help="Ergebnis als JSON speichern (ohne Antworttexte)")
        s.add_argument("--modell", default="deepseek", help="glm, glm-flash, deepseek, apertus oder eine Modell-ID")
        s.add_argument("--denken", action="store_true", help="Reasoning einschalten (langsamer)")
        s.set_defaults(fn=fn)
    s = sub.add_parser("app", help="Chat im Browser starten")
    s.add_argument("--port", type=int, default=8501)
    s.add_argument("--adresse", help="z. B. die Tailscale-IP, um im Tailnet erreichbar zu sein")
    s.set_defaults(fn=_app)
    sub.add_parser("mcp", help="Werkzeuge als MCP-Server (stdio) anbieten").set_defaults(fn=_mcp)
    args = p.parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
