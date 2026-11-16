# Projektskizze: FHNW Studienassistent

**Ein KI-Agent, der Fragen zum Studium aus den echten Kursunterlagen beantwortet – mit Quelle.**

Modul Generative KI & Agentensysteme · FHNW BSc Business Artificial Intelligence · Gruppenarbeit HS 2026
Stand: 07.10.2026 · Abschlusspräsentation: 23.11.2026, 13:00 Uhr (10 Min. inkl. Verständnisfragen)

## Team

Das Team hat fünf Mitglieder; das ist mit dem Dozenten abgesprochen (vorgesehen wären 3 bis 4, SW4, Folie 4).

| Name | Rolle (Abschnitt 9) |
|---|---|
| Almidin Bangoji | Agent & Prompts |
| Robin Meier | Daten & Suche |
| Jan Steiner | Evaluation |
| Andrej Mauron | Interface & Demo |
| Flavio Sibilia | Integration & Präsentation |

## 1. Problemstellung

Im BAI-Studium sind die Informationen zu einem Semester auf viele Orte verteilt: Semesterprogramme als PDF,
Folien, Moodle-Kursseiten, Aufgabenbeschreibungen, Teams-Beiträge. Allein im HS 2026 sind es bei sieben Modulen
rund 80 Dateien mit über 4000 Textabschnitten. Fragen wie «Wann ist die Präsentation?», «Wie viele Folien darf das
Pitch Deck haben?» oder «Was ist diese Woche fällig?» kosten jedes Mal Minuten der Suche – und wer die Stelle nicht
findet, fragt im Gruppenchat oder bei Dozierenden nach.

Ein gewöhnlicher Chatbot hilft hier nicht: Er kennt die Unterlagen nicht und erfindet im Zweifel ein Datum.
Gebraucht wird ein Assistent, der **in den eigenen Unterlagen sucht, kurz antwortet und die Fundstelle nennt**.

## 2. Use Case und Nutzerbedürfnisse

| Nutzerrolle | Bedürfnis |
|---|---|
| **Studierende** im BAI | schnell eine verlässliche Antwort zu Terminen, Abgaben, Regeln und Inhalten – mit Quelle zum Nachprüfen |
| **Projektgruppen** | gemeinsamer Stand, was wann abzugeben ist und welche Anforderungen gelten |
| **Dozierende** (indirekt) | weniger wiederkehrende Organisationsfragen per Mail |

**User Stories** (Form nach SW4, Folie 14):

- Als **Studentin** möchte ich fragen «Wann ist die GenAI-Präsentation und wie lange dauert sie?», damit ich die
  Antwort nicht im Semesterprogramm suchen muss.
- Als **Student** möchte ich zu jeder Antwort die Quelle (Modul, Datei, Seite) sehen, damit ich der Antwort trauen
  oder sie selbst nachlesen kann.
- Als **Studentin** möchte ich fragen «Was ist in den nächsten zwei Wochen fällig?», damit ich meine Woche planen kann.
- Als **Student** möchte ich Rückfragen stellen können («Und wie viele Folien?»), ohne den Zusammenhang zu wiederholen.
- Als **Studentin** möchte ich, dass der Assistent ehrlich sagt, wenn etwas nicht in den Unterlagen steht, statt zu raten.

**Vergleich mit heute:** Studierende suchen manuell in Moodle und Teams oder fragen nach. Allgemeine Chatbots
(ChatGPT, Copilot) kennen die Kursunterlagen nicht und nennen keine überprüfbare Quelle.

## 3. Lösungsansatz

Ein einzelner LLM-Agent mit Werkzeugen (laut Moodle genügt ein «LLM-Agent oder agentisches System»; Multi-Agent ist
keine Pflicht). Ablauf als LangGraph-Zustandsgraph:

1. **Prüfen** – Hat die Frage einen Studienbezug? Wenn nicht: freundliche Absage (Guardrail).
2. **Agent** – Das Sprachmodell entscheidet, welches Werkzeug es braucht.
3. **Werkzeuge** – `unterlagen_durchsuchen` (Hybrid-Suche in den Kursunterlagen, optional nach Modul gefiltert),
   `fristen_anzeigen` (Termine in einem Zeitraum), `module_auflisten`.
4. **Antwort** – zwei, drei Sätze mit «(Quelle: Modul · Datei, S. n)».
   Nach höchstens drei Suchrunden antwortet der Agent mit dem Gefundenen. Bei unklaren Fragen («das Projekt») fragt er
   zuerst nach dem Modul. Mit Reasoning prüft und sucht das schnelle Modell; nur die Antwort schreibt das denkende
   Modell (Knoten `antworten`), so denkt es einmal statt in jeder Suchrunde.

Das Gesprächsgedächtnis pro Chat erlaubt Rückfragen. Die Unterlagen werden einmal eingelesen (PDF, PowerPoint inkl.
Notizen, Word, Markdown), in Abschnitte von etwa 900 Zeichen zerlegt und mit BM25 und Embeddings durchsuchbar gemacht.

## 4. Erfolgskriterien und Zielwerte

Gemessen mit dem Testset `evaluation/fragen.jsonl` (echte Fragen mit bekannten Antworten aus den Unterlagen):

| Kriterium | Zielwert |
|---|---|
| Suche: richtige Quelle unter den ersten 5 Treffern | ≥ 90 % |
| Antwort enthält die erwarteten Fakten (Datum, Zahl, Regel) | ≥ 80 % |
| Fragen ohne Studienbezug abgelehnt, Studienfragen beantwortet | 100 % |
| Antwort nennt eine Quelle | ≥ 90 % |
| Antwortzeit | < 20 s |

## 5. Scope (MVP) und Limitierungen

**Im Scope:** Fragen zu den sieben Modulen des eigenen Semesters, Fristen, Rückfragen, Chat im Browser, Evaluation.
**Nicht im Scope:** Abgaben schreiben oder Aufgaben lösen (bewusst ausgeschlossen), automatisches Herunterladen aus
Moodle/Teams im Repository (jede Person liest ihre eigenen Unterlagen ein), Noten oder persönliche Daten.
**Limitierungen:** Der Assistent weiss nur, was in den eingelesenen Unterlagen steht; gescannte Bilder ohne Text
werden nicht gelesen; das Ratenlimit der Swiss AI Platform (≈ 15 Anfragen/Minute) begrenzt gleichzeitige Nutzer.

## 6. Eingesetzte Konzepte aus dem Modul

| Modulthema | Umsetzung |
|---|---|
| System-Prompt | Rolle, heutiges Datum und Wochentag, Regeln (erst suchen, Quelle nennen, nichts erfinden) |
| Function Calling / Tools | drei Werkzeuge, das Modell wählt selbst |
| Orchestrierung | LangGraph: Prüfung → Agent ⇄ Werkzeuge, bedingte Kanten |
| RAG | Chunking mit Überlappung, Hybrid-Suche (BM25 + Qwen3-Embeddings, Reciprocal Rank Fusion), Modulfilter |
| Memory | Gesprächsgedächtnis pro Chat (LangGraph-Checkpointer), Trimming: ans Modell geht nur der jüngste Verlauf |
| Guardrails / Safeguarding | Zwei Gates nach OWASP: Eingang (zuerst deterministische Regeln, dann Prüfung mit strukturierter Ausgabe; fail closed) und Kontext (Suchtreffer als Daten eingerahmt, Sätze an eine KI entfernt). Keine unumkehrbaren Aktionen, kein offenes Web, kein Langzeit-Gedächtnis: von der «lethal trifecta» fehlt die Kommunikation nach aussen |
| MCP | Eigener MCP-Server mit den drei Werkzeugen; der Agent ist MCP-Client und holt Werkzeugliste und Ergebnisse über das Protokoll (`mcp_client.py`). Andere Clients (Claude Desktop, Claude Code) können denselben Server nutzen |
| Modellwahl | Swiss AI Research Platform: im Chat GLM-5.3 Flash mit maximalem Reasoning für die Antwort; Prüfung und Suche im schnellen Modus. Per Befehl auch DeepSeek und Apertus |
| Evaluation & Tracing | Testset mit fünf Kennzahlen inkl. Antwortzeit, Modellvergleich (`docs/modellwahl.md`), Tests ohne Netz (GitHub Actions), LangSmith-Tracing (Projekt `studienassistent`) |
| Interface | Streamlit-Chat mit Fundstellen als Karten, Warteschlange und Auslastungsanzeige für viele Nutzende |

## 7. Evaluation

`python -m studienassistent bewerten` stellt alle Testfragen, misst die Kennzahlen aus Abschnitt 4 und listet die
nicht bestandenen Fragen. Modelle (DeepSeek, Apertus, GLM) und Reasoning an/aus werden auf demselben Testset
verglichen. Die Tests in `tests/` laufen ohne Netz mit einem simulierten Sprachmodell.

## 8. Zeitplan

| Woche | Meilenstein laut Semesterprogramm | Stand |
|---|---|---|
| KW 41 (05.10.) | Gruppenbildung, Use Case, Evaluationskriterien | diese Skizze; **Rollen eintragen** |
| KW 42 (12.10.) | erste lauffähige Version, Tracing | lauffähig (Chat, CLI, Tests); Tracing in LangSmith, Projekt `studienassistent` |
| KW 43 (19.10.) | MCP-Server anbinden | umgesetzt: eigener Server (`python -m studienassistent mcp`), Agent als MCP-Client |
| KW 44 (26.10.) | RAG, Chunking, Hybrid Retrieval | umgesetzt; Feinschliff nach Evaluation |
| KW 46 (09.11.) | Memory festlegen | Gesprächsgedächtnis umgesetzt |
| KW 47 (16.11.) | Safeguarding, Evaluation | Guardrail, Testset und Modellvergleich umgesetzt (`docs/modellwahl.md`). Lauf vom 16.11. mit allen Änderungen (24 Fragen, `evaluation/ergebnisse/2026-11-16_glmflashdenken.json`): Quelle in Top 5, Fakten und Ablehnung je 100 %, Quelle genannt 95 %; Antwortzeit Median 15 s (Ziel < 20 s im Median erreicht; 62 % aller Antworten unter 20 s, ohne Wartezeit der Taktbremse 96 %). Zum Vergleich 14.10.: Median 21 s. Neu nach SW9: deterministische Vorprüfung, fail closed, Suchtreffer als Daten (`sicherheit.py`); nach SW8: Trimming des Verlaufs |
| KW 48 (23.11.) | Abschlusspräsentation | Live-Demo im Chat |

## 9. Arbeitsteilung

| Rolle | Verantwortung | Dateien | Person |
|---|---|---|---|
| Daten & Suche | Einlesen, Chunking, Hybrid-Suche, Fristen | `einlesen.py`, `suche.py`, `fristen.py` | Robin Meier |
| Agent & Prompts | LangGraph, Werkzeuge, System-Prompt, Guardrail | `agent.py`, `werkzeuge.py`, `prompts.py` | Almidin Bangoji |
| Evaluation | Testset, Kennzahlen, Modellvergleich, Tracing | `bewertung.py`, `evaluation/`, `tests/` | Jan Steiner |
| Interface & Demo | Chat-App, Betrieb (Warteschlange, Auslastung), Live-Demo | `app.py`, `betrieb.py`, `stellen.py` | Andrej Mauron |
| Integration & Präsentation | MCP-Server und -Client, Modellwahl, Folien | `mcp_server.py`, `mcp_client.py`, `docs/` | Flavio Sibilia |

## 10. Risiken

| Risiko | Gegenmassnahme |
|---|---|
| Modell erfindet Antworten | Regel «nur aus Unterlagen», Quelle Pflicht, Fakten-Kennzahl im Testset |
| Suche findet die Stelle nicht | Hybrid-Suche, Modulfilter, Fehlfälle aus der Evaluation gezielt verbessern |
| Ratenlimit / Ausfall der Plattform | Gemeinsame Taktbremse für alle Prozesse (14 Aufrufe/Min.), Warteschlange mit höchstens 2 gleichzeitigen Fragen, Modell per Befehl umschaltbar |
| Urheberrecht der Kursunterlagen | Unterlagen nie im Repository, nur lokal eingelesen |
| Demo scheitert live | Beispielfragen vorbereitet, Aufzeichnung als Rückfall |

## 11. Ethik und Grenzen

Der Assistent hilft beim Finden von Informationen, nicht beim Erledigen von Leistungsnachweisen; Anfragen, Abgaben
zu schreiben, lehnt er ab. Die Antworten ersetzen nicht die offiziellen Angaben – darum steht bei jeder Antwort die
Quelle. Kursunterlagen der FHNW sind urheberrechtlich geschützt und bleiben lokal. Code und Dokumentation sind mit
Unterstützung eines KI-Assistenten (Claude Code) entstanden; das wird in Abgabe und Präsentation offengelegt.

## 12. Projektgeschichte

Begonnen hat das Team mit «KI-Kartell» (Simulation, ob KI-Preisagenten Kartelle bilden). Im Gespräch mit dem
Dozenten am 05.10. wurde klar, dass dieses Projekt zu komplex war und keinen greifbaren Nutzen hatte. Es ist im
Branch `ki-kartell` archiviert; übernommen wurden Hybrid-Suche, Swiss-AI-Anbindung und Evaluationserfahrung.

## 13. Quellen

- Schwander, S. (2026): SW4 Agentensystem – Bausteine, Vorgehen, Modellauswahl. FHNW.
- LangGraph Dokumentation: Agents, Tool Calling, Persistence. langchain-ai.github.io/langgraph
- Robertson, S., Zaragoza, H. (2009): The Probabilistic Relevance Framework: BM25 and Beyond.
- Cormack, G., Clarke, C., Büttcher, S. (2009): Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods. SIGIR.
- Swiss AI Initiative (2026): Apertus und Swiss AI Research Platform, CSCS.
