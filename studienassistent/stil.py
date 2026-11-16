"""Aussehen der Chat-App: ruhig und redaktionell statt «KI-Look».

Heller Papierton, schwarze Schrift, Überschrift mit Serifen (Source Serif 4), Fliesstext IBM Plex Sans, eine einzige
Akzentfarbe (Textmarker-Gelb). Keine Verläufe, kein Leuchten, keine Glas-Effekte. Streamlit erlaubt eigenes CSS über
st.markdown; die Selektoren nutzen die data-testid-Attribute.
"""
from __future__ import annotations

import html

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap');

:root {
  --sa-papier: #f6f4ef;
  --sa-flaeche: #fffdf8;
  --sa-tinte: #1c1b19;
  --sa-leise: #6b6860;
  --sa-linie: #dedad0;
  --sa-gelb: #ffe45c;
  --sa-text2: #3d3b36;
  --sa-blase: #ebe7dc;
  --sa-rand-eingabe: #cfcabd;
  --sa-leiste: #efece4;
  --sa-auf-tinte: #ffffff;
  --sa-knopf-hover: #000000;
  --sa-markierung: rgba(255,228,92,0.7);
  --sa-hover-zeile: rgba(255,228,92,0.25);
}

html, body, [class*="st-"], .stMarkdown, .stChatInput textarea, button {
  font-family: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}
[data-testid="stIconMaterial"], .material-symbols-rounded { font-family: 'Material Symbols Rounded' !important; }

[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { padding-top: 3.5rem; max-width: 760px; }

/* Kopf: linksbündig wie eine Titelseite */
.sa-kopf { margin: 0.5rem 0 2rem; }
.sa-kicker { font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--sa-leise); }
.sa-titel {
  font-family: 'Source Serif 4', Georgia, serif !important; font-weight: 600; font-size: clamp(2.2rem, 5vw, 3rem);
  letter-spacing: -0.015em; line-height: 1.08; color: var(--sa-tinte); margin: 0.35rem 0 0.9rem; padding: 0;
}
.sa-titel mark { background: linear-gradient(transparent 58%, var(--sa-gelb) 58%); color: inherit; padding: 0 0.05em; }
.sa-text { font-size: 1.05rem; line-height: 1.6; color: var(--sa-text2); max-width: 590px; margin: 0; }
.sa-module { font-size: 0.85rem; color: var(--sa-leise); margin-top: 0.9rem; line-height: 1.6; }
.sa-abschnitt { font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--sa-leise); margin: 0.2rem 0 0.4rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--sa-linie); }

/* Beispielfragen als schlichte Liste */
.st-key-beispiele [data-testid="stVerticalBlock"] { gap: 0; }
.st-key-beispiele [data-testid="stButton"] button {
  width: 100%; justify-content: flex-start; text-align: left; padding: 0.85rem 0.25rem; min-height: 0;
  background: transparent; border: none; border-bottom: 1px solid var(--sa-linie); border-radius: 0; color: var(--sa-tinte);
}
.st-key-beispiele [data-testid="stButton"] button > div { justify-content: flex-start; gap: 0.7rem; width: 100%; }
.st-key-beispiele [data-testid="stButton"] button p { font-size: 0.98rem; white-space: normal; text-align: left; }
.st-key-beispiele [data-testid="stButton"] button [data-testid="stIconMaterial"] { color: var(--sa-leise); font-size: 1.15rem; }
.st-key-beispiele [data-testid="stButton"] button:hover { background: var(--sa-hover-zeile); color: var(--sa-tinte); }
.st-key-beispiele [data-testid="stButton"] button:hover p { text-decoration: underline; text-underline-offset: 3px; }

/* Chat */
[data-testid="stChatMessage"] { background: transparent; padding: 0.4rem 0; gap: 0.8rem; }
[data-testid="stElementContainer"]:has(.sa-du) { display: none; }  /* unsichtbare Marke der Nutzer-Nachricht */
/* Eigene Frage: rechtsbündig, die Blase sitzt direkt auf dem Text (unabhängig von Streamlits Innenabständen) */
[data-testid="stChatMessage"]:has(.sa-du) { justify-content: flex-end; padding: 0.5rem 0; }
[data-testid="stChatMessage"]:has(.sa-du) [data-testid="stMarkdownContainer"] { text-align: right; }
[data-testid="stChatMessage"]:has(.sa-du) [data-testid="stMarkdownContainer"] p {
  display: inline-block; text-align: left; max-width: 75%; margin: 0; padding: 0.55rem 0.95rem; line-height: 1.5;
  background: var(--sa-blase); border-radius: 14px;
}
[data-testid="stChatMessage"]:has(.sa-du) [data-testid="stVerticalBlock"] { gap: 0; }
[data-testid="stChatMessage"]:has(.sa-du) [data-testid="stChatMessageContent"] { margin: 0; padding: 0; min-height: 0; width: 100%; }
[data-testid="stChatMessage"]:has(.sa-du) [data-testid="stChatMessageAvatarCustom"] { display: none; }
[data-testid="stChatMessageAvatarCustom"] {
  width: 32px; height: 32px; border-radius: 8px; border: none; background: var(--sa-tinte) !important; color: var(--sa-auf-tinte) !important;
}
[data-testid="stChatMessageAvatarCustom"] [data-testid="stIconMaterial"], [data-testid="stChatMessageAvatarCustom"] span {
  color: var(--sa-auf-tinte) !important; fill: var(--sa-auf-tinte) !important;
}
[data-testid="stChatMessageContent"] { font-size: 1rem; line-height: 1.65; color: var(--sa-tinte); }
[data-testid="stChatMessageContent"] strong { font-weight: 600; background: linear-gradient(transparent 62%, var(--sa-markierung) 62%); }
[data-testid="stChatMessageContent"] a { color: var(--sa-tinte); text-decoration: underline; text-underline-offset: 2px; }
[data-testid="stChatMessageContent"] [data-testid="stExpander"] details {
  border: 1px solid var(--sa-linie); border-radius: 8px; background: var(--sa-flaeche);
}
[data-testid="stChatMessageContent"] [data-testid="stExpander"] summary { font-size: 0.85rem; color: var(--sa-leise); }

/* Eingabe */
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: var(--sa-papier) !important; }
[data-testid="stChatInput"] {
  background: var(--sa-flaeche) !important; border: 1px solid var(--sa-rand-eingabe) !important; border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(28,27,25,0.06);
}
[data-testid="stChatInput"]:focus-within { border-color: var(--sa-tinte) !important; }
[data-testid="stChatInputSubmitButton"] { background: var(--sa-tinte) !important; color: var(--sa-auf-tinte) !important; border-radius: 8px !important; }

/* Seitenleiste */
[data-testid="stSidebar"] { background: var(--sa-leiste); border-right: 1px solid var(--sa-linie); }
[data-testid="stSidebar"] [data-testid="stButton"] button {
  background: var(--sa-tinte); color: var(--sa-auf-tinte); border: none; border-radius: 8px; font-weight: 500;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover { background: var(--sa-knopf-hover); color: var(--sa-gelb); }
.sa-zahlen { display: grid; grid-template-columns: 1fr 1fr; gap: 0; margin: 1.1rem 0 0.8rem;
  border-top: 1px solid var(--sa-linie); border-bottom: 1px solid var(--sa-linie); }
.sa-zahl { padding: 0.7rem 0.2rem; }
.sa-zahl + .sa-zahl { border-left: 1px solid var(--sa-linie); padding-left: 0.8rem; }
.sa-zahl b { display: block; font-family: 'Source Serif 4', Georgia, serif; font-size: 1.45rem; font-weight: 600; color: var(--sa-tinte); }
.sa-zahl > span { display: block; font-size: 0.72rem; line-height: 1.3; color: var(--sa-leise); }
.sa-punkt { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #2f9e44; margin: 0 6px 3px 0; vertical-align: middle; }

[data-testid="stForm"] { background: var(--sa-flaeche); border: 1px solid var(--sa-linie); border-radius: 10px; }

@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-top: 2rem; }
  [data-testid="stChatMessage"]:has(.sa-du) [data-testid="stChatMessageContent"] { max-width: 88%; }
}
</style>
"""

# Dunkles Design: gleiche Struktur, andere Farben. Aktiv, wenn Streamlit im Dark Mode läuft (Systemeinstellung oder
# Menü ⋮ → Settings → Theme), siehe [theme.dark] in .streamlit/config.toml.
DUNKEL = """
<style>
:root {
  --sa-papier: #151513;
  --sa-flaeche: #1d1c1a;
  --sa-tinte: #ece8df;
  --sa-leise: #9b978d;
  --sa-linie: #34322d;
  --sa-gelb: #ffd84a;
  --sa-text2: #cfcac0;
  --sa-blase: #2a2925;
  --sa-rand-eingabe: #403d37;
  --sa-leiste: #1a1917;
  --sa-auf-tinte: #151513;
  --sa-knopf-hover: #ffffff;
  --sa-markierung: rgba(255,216,74,0.32);
  --sa-hover-zeile: rgba(255,216,74,0.10);
}
.sa-titel mark { background: linear-gradient(transparent 60%, rgba(255,216,74,0.45) 60%); }
[data-testid="stSidebar"] [data-testid="stButton"] button:hover { color: #151513; }
</style>
"""

AVATAR_ASSISTENT = ":material/school:"
AVATAR_NUTZER = ":material/person:"
MARKE_NUTZER = '<span class="sa-du"></span>'


def hero(module: list[str]) -> str:
    liste = " · ".join(html.escape(m) for m in module)
    zeile = f'<div class="sa-module">Unterlagen aus: {liste}</div>' if module else ""
    return f"""
<div class="sa-kopf">
  <div class="sa-kicker">FHNW · Business Artificial Intelligence · HS 2026</div>
  <div class="sa-titel" role="heading" aria-level="1">Was willst du zum <mark>Studium</mark> wissen?</div>
  <p class="sa-text">Fragen zu Prüfungen, Abgaben und Fristen, beantwortet aus euren Kursunterlagen.
  Bei jeder Antwort steht, wo es geschrieben steht.</p>
  {zeile}
</div>"""


def zahlen(online: int, aufrufe: int, limit: int) -> str:
    return f"""
<div class="sa-zahlen">
  <div class="sa-zahl"><b><span class="sa-punkt"></span>{online}</b><span>gerade online</span></div>
  <div class="sa-zahl"><b>{aufrufe}/{limit}</b><span>Aufrufe pro Minute</span></div>
</div>"""
