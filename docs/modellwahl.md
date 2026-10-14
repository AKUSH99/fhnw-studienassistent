# Modellwahl und Modellvergleich

Warum der Studienassistent **GLM-5.3 Flash** auf der **Swiss AI Research Platform** nutzt, gemessen an den
Kriterien aus SW4 (Folien 22 bis 38) und an unserem Testset.

## Messung

22 Testfragen aus `evaluation/fragen.jsonl` (Termine, Regeln, Inhalte aus sieben Modulen; drei Fragen ohne
Studienbezug, die abgelehnt werden sollen). Gleiche Unterlagen, gleiche Suche, gleicher Agent; nur das Modell und
das Reasoning ändern sich. Gemessen auf dem Thin Client am 07.10.2026 mit `python -m studienassistent bewerten`.

| Modell (Swiss AI Platform) | Reasoning | Fakten richtig | Ablehnung richtig | Quelle genannt | Antwortzeit Median (max) | ohne Wartezeit Ratenlimit | 429-Ablehnungen |
|---|---|---|---|---|---|---|---|
| **GLM-5.3 Flash** (im Chat, 14.10., nach Tempo-Umbau) | für die Antwort | **100 %** | **100 %** | 95 %³ | 21 s (56 s) | **6 s (18 s), 100 % unter 20 s** | 0 |
| GLM-5.3 Flash, 07.10. | für die Antwort | 100 % | 100 % | 100 % | 31 s (61 s) | 10 s (24 s), 91 % unter 20 s | 0 |
| GLM-5.3 Flash, erster Lauf | für die Antwort | 94 %¹ | 100 % | 95 % | 13 s (114 s) | nicht gemessen | nicht protokolliert |
| GLM-5.3 | für die Antwort | 100 % | 100 % | 95 % | 27 s (118 s) | 24 s (118 s), 36 % unter 20 s | 4 |
| DeepSeek V4.1 Flash | aus | 100 % | 100 % | 95 % | 58 s (131 s) | nicht gemessen | nicht protokolliert |
| DeepSeek V4.1 Flash | für die Antwort | 100 % | 100 % | 95 % | 10 s (115 s) | nicht trennbar² | 18 von 135 Anfragen |

Fakten: 18 Fragen mit bekannter Antwort; Ablehnung: alle 22; Quelle genannt: 19 beantwortete Fragen.
¹ Testset-Fehler: Die Antwort «24.–25. Oktober» war richtig, das Testset kannte die Schreibweise nicht (korrigiert).
² Die Wartezeiten nach 429 lagen damals noch im HTTP-Client des SDK und wurden nicht mitgezählt.
³ Die eine Antwort ohne Quelle ist die Begrüssung «Hallo, was kannst du alles?».

Am 11.10. wurde der Graph umgebaut: Mit Reasoning geht es nach der Suche direkt zur Antwort (kein Wegwerf-Entwurf des
schnellen Modells mehr), und die Gedanken des Modells werden live gestreamt. Der Lauf vom 14.10. misst diesen Stand.

**So lesen:** Die Evaluation stellt 22 Fragen ohne Pause hintereinander, also mehr als das Ratenlimit erlaubt.
Darum enthält die Spalte «Antwortzeit» Wartezeit; «ohne Wartezeit Ratenlimit» ist die Zeit, die eine einzelne
Person ohne Andrang erlebt. Die Läufe vor 21:00 liefen noch mit 14 Aufrufen pro Minute und ohne Notbremse; die
Plattform lehnte dabei Anfragen ab (HTTP 429, Wartezeit 41 bis 59 s), schon bei rund 8 Aufrufen pro Minute. Der
letzte Lauf mit 10 Aufrufen pro Minute und Notbremse hatte keine einzige Ablehnung.

**Entscheid:** GLM-5.3 Flash. Es erreicht alle fünf Zielwerte und ist ohne Wartezeit deutlich schneller als das
grosse GLM-5.3 (Median 10 s statt 24 s am 07.10., seit dem Umbau 6 s) bei gleicher Genauigkeit. DeepSeek V4.1 Flash ist ebenso genau und eine
gute Ausweichmöglichkeit (per `--modell deepseek`). Vorsicht beim Vergleich: Die Läufe fanden unter verschiedenen
Bedingungen statt (mit und ohne Notbremse, unterschiedliche Auslastung der Plattform), und bei 22 Fragen sind die
Unterschiede klein. Für eine sichere Aussage sollte das Testset wachsen und alle Modelle unter gleichen
Bedingungen nochmals laufen.

**Suche allein** (ohne Sprachmodell): Die richtige Quelle steht bei 14 von 14 Fragen unter den ersten 5 Treffern,
mit BM25 allein wie mit der Hybrid-Suche (BM25 + Qwen3-Embeddings). Das Testset prüft die Quelle nur auf Ebene
des Moduls; der Nutzen der Embeddings zeigt sich bei Umschreibungen, etwa bei der Teamgrösse («Teams aus 3
Studierenden», nur über die Bedeutungssuche gefunden, Rang 7).

## Kriterien aus SW4

| Kriterium (SW4, Folie 25) | Was es für uns heisst | Entscheid |
|---|---|---|
| Endnutzer | Studierende erwarten richtige Daten und Regeln mit Quelle; eine falsche Frist ist schlimmer als keine Antwort | Antwort mit Reasoning, Quelle Pflicht, Fakten-Kennzahl im Testset |
| Throughput & Geschwindigkeit | Chat soll sich flüssig anfühlen; Ziel aus der Projektskizze: Antwort unter 20 s | Flash statt des grossen GLM-5.3 (siehe Messung) |
| Kosten | Kein Budget; Studierende sollen die App gratis nutzen | Swiss AI Research Platform: für uns ohne Kosten nutzbar (Zugang mit Hochschul-Login) |
| Technische Anforderungen | Function Calling für drei Werkzeuge, Deutsch, Kontext für 8 Treffer à 700 Zeichen | GLM-5.3 Flash kann alles davon; Ratenlimit unter 15 Anfragen/Min. pro Schlüssel |
| Betriebsmodell | Kursunterlagen und Fragen sollen in der Schweiz bleiben; offene Modelle | Plattform der Swiss AI Initiative (ETH, EPFL) am CSCS in der Schweiz; die GLM-Modelle sind offen verfügbar (Open Weights) |

**Alternativen, die wir nicht genommen haben:**
- **Kommerzielle APIs** (OpenAI, Anthropic, Google): stärker, aber kostenpflichtig, und Daten verlassen die Schweiz.
- **FHNW-LiteLLM-Proxy**: stellt Modelle mit Kostenobergrenze bereit; gut als Ausweichmöglichkeit, wenn das
  Ratenlimit der Swiss AI Platform nicht reicht.
- **Apertus** (das Schweizer Modell): für Deutsch und Schweizer Kontext interessant und per `--modell apertus`
  nutzbar; im Testset haben wir es noch nicht gemessen.

## Was wir beim Ausprobieren gelernt haben

- **GLM ohne Reasoning schreibt seine Gedanken in den Text.** Die Plattform trennt den Denkteil nur, wenn das
  Reasoning eingeschaltet ist; sonst steht vor der Antwort roher Gedankentext («…question is in German…»). Für
  Werkzeugaufrufe stört das nicht, für Antworten schon.
- **Reasoning nur für die Antwort.** Mit Reasoning in jeder Suchrunde dauerte eine unklare Frage über 3 Minuten und
  endete im Rekursionslimit. Jetzt prüft und sucht das Modell im schnellen Modus, und nur die Antwort entsteht mit
  maximalem Reasoning (Knoten `antworten`).
- **Strukturierte Ausgabe über Function Calling.** Die Eingangsprüfung als JSON-Schema brauchte mit GLM-5.3 und
  Reasoning bis zu 90 s; über einen Werkzeugaufruf im schnellen Modus 1 bis 3 s.
- **Ratenlimit statt Rechenleistung ist der Engpass.** Eine Frage braucht etwa 5 Aufrufe (Prüfung, Suche,
  Embedding, Antwort). Bei 14 Aufrufen pro Minute schafft ein Schlüssel rund 3 Fragen pro Minute; darum gibt es eine
  gemeinsame Taktbremse und eine Warteschlange (`betrieb.py`).
