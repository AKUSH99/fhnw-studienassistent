"""Chat-Oberfläche (Streamlit):  python -m studienassistent app

Mit STUDIENASSISTENT_PASSWORT verlangt die Seite ein gemeinsames Passwort (für den öffentlichen Zugang). Ein Link
mit ?zugang=<Passwort> (z. B. als QR-Code) meldet direkt an; der Code verschwindet danach aus der Adresszeile.
"""
from __future__ import annotations

import hmac
import html
import os
import time
import uuid

import streamlit as st

from studienassistent.__main__ import lade_alles
from studienassistent.agent import fragen_live
from studienassistent.betrieb import Warteschlange
from studienassistent.konfig import betrieb
from studienassistent.stellen import als_markdown, farbe, suchbegriffe, zerlegen

MODELL = "glm-flash"  # GLM-5.3 Flash; die Antwort entsteht immer mit maximalem Reasoning
REPO = "https://github.com/AKUSH99/fhnw-studienassistent"
BEISPIELE = ["Was ist diese Woche fällig?", "Wie wird die Gruppenarbeit in GenAI bewertet?",
             "Wie viele Folien darf das Pitch Deck in Entrepreneurship haben?", "Wann ist die Marketing-Präsentation?"]

st.set_page_config(page_title="FHNW Studienassistent", page_icon="🎓")


def anmelden() -> None:
    """Gemeinsames Passwort vor der App, wenn STUDIENASSISTENT_PASSWORT gesetzt ist (öffentlicher Zugang)."""
    passwort = os.environ.get("STUDIENASSISTENT_PASSWORT", "")
    if not passwort or st.session_state.get("angemeldet"):
        return
    zugang = st.query_params.get("zugang", "")
    if zugang:
        st.query_params.clear()  # Code nicht in der Adresszeile stehen lassen (Lesezeichen, Weiterleiten)
        if hmac.compare_digest(zugang.encode(), passwort.encode()):
            st.session_state["angemeldet"] = True
            return
    st.title("🎓 FHNW Studienassistent")
    st.caption("Fragen zu Prüfungen, Abgaben und Fristen im BAI-Herbstsemester 2026, beantwortet aus den Kursunterlagen.")
    with st.form("anmelden"):
        eingabe = st.text_input("Passwort", type="password", help="Das Passwort bekommst du von deinem Team.")
        if st.form_submit_button("Los geht's", type="primary"):
            if hmac.compare_digest(eingabe.encode(), passwort.encode()):
                st.session_state["angemeldet"] = True
                st.rerun()
            time.sleep(2)  # bremst Ratespiele
            st.error("Das Passwort stimmt nicht.")
    st.stop()


anmelden()


@st.cache_resource(show_spinner="Unterlagen werden geladen …")
def agent(modell: str):
    return lade_alles(modell, denken=True)


@st.cache_resource
def schlange() -> Warteschlange:
    return Warteschlange()  # eine für alle Sitzungen der App


graph, suche, _ = agent(MODELL)
st.session_state.setdefault("besucher", str(uuid.uuid4()))  # zählt offene Seiten, bleibt bei «Neues Gespräch»
st.session_state.setdefault("thread", str(uuid.uuid4()))
st.session_state.setdefault("verlauf", [])


def zeige_details(eintrag: dict) -> None:
    """Alles Zusätzliche zu einer Antwort in EINEM zugeklappten Feld: Quellen, Gedanken, Ablauf."""
    stellen, termine = zerlegen(eintrag.get("quellen", []), eintrag["text"])
    gedanken = eintrag.get("gedanken", "").strip()
    if not (stellen or termine or gedanken):
        return
    teile = [f"{len(stellen)} Quellen" if stellen else "", f"{len(termine)} Termine" if termine else "",
             f"{eintrag['sekunden']:.0f} s" if eintrag.get("sekunden") else ""]
    with st.expander("Details · " + " · ".join(x for x in teile if x)):
        if eintrag.get("ablauf"):
            st.caption(eintrag["ablauf"])
        reiter = [n for n, da in (("Quellen", stellen or termine), ("Gedanken", gedanken)) if da]
        for name, bereich in zip(reiter, st.tabs(reiter)):
            with bereich:
                if name == "Gedanken":
                    st.markdown(gedanken_html(gedanken), unsafe_allow_html=True)
                    continue
                for f in termine:
                    st.markdown(f"**{f.datum}**{' ' + f.zeit if f.zeit else ''} · {f.modul}: {als_markdown(f.titel, [])}")
                begriffe = suchbegriffe(eintrag.get("frage", ""))
                for s in stellen:
                    with st.container(border=True):
                        kopf = f":{farbe(s.modul)}-badge[{s.modul}] **{als_markdown(s.datei, [])}**"
                        kopf += f" · S. {s.seite}" if s.seite else ""
                        kopf += " · :green[zitiert]" if s.zitiert else ""
                        st.markdown(kopf)
                        st.markdown(f"<small>{als_markdown(s.text, begriffe)}</small>", unsafe_allow_html=True)


def gedanken_html(text: str, nur_ende: int | None = None) -> str:
    """Gedanken des Modells klein und grau; live nur das Ende, damit es wie ein Ticker mitläuft."""
    if nur_ende and len(text) > nur_ende:
        text = "… " + text[-nur_ende:]
    return ("<div style='font-size:0.85em;font-style:italic;opacity:0.65;white-space:pre-wrap'>"
            f"{html.escape(text.strip())}</div>")


def zeige_bewertung(eintrag: dict) -> None:
    """👍/👎 (gezählt, ohne den Text zu speichern)."""
    schluessel = f"daumen_{eintrag['id']}"

    def gespeichert() -> None:
        wert = st.session_state.get(schluessel)
        betrieb().bewerten(eintrag["id"], None if wert is None else wert == 1)

    st.feedback("thumbs", key=schluessel, on_change=gespeichert)


def zeige_antwort(eintrag: dict) -> None:
    zeige_details(eintrag)
    zeige_bewertung(eintrag)


@st.fragment(run_every=10)
def auslastung() -> None:
    """Lebenszeichen senden und die Lage kurz anzeigen; aktualisiert sich alle 10 Sekunden von selbst."""
    b = betrieb()
    b.lebenszeichen(st.session_state["besucher"])
    lage, (in_arbeit, wartend) = b.lage(), schlange().zustand()
    st.caption(f"👥 {lage['aktiv']} online · 🔑 {lage['aufrufe_minute']}/{lage['limit']} Aufrufe pro Minute")
    if wartend:
        st.caption(f"⏳ {wartend} in der Warteschlange")
    if lage["pause_noch"] > 0:
        st.caption(f"⏸️ Die Plattform bremst, noch {lage['pause_noch']:.0f} s")
    with st.expander("Statistik"):
        schnitt = f" · Ø {lage['schnitt_sekunden']:.0f} s" if lage["schnitt_sekunden"] else ""
        st.caption(f"Heute {lage['fragen_heute']} Fragen von {lage['fragende_heute']} Personen{schnitt}  \n"
                   f"Bewertungen 👍 {lage['daumen_hoch']} · 👎 {lage['daumen_runter']}")


def beispiel_gewaehlt() -> None:
    st.session_state["vorschlag"] = st.session_state["beispiel"]
    st.session_state["beispiel"] = None


with st.sidebar:
    if st.button("Neues Gespräch", icon=":material/add_comment:", width="stretch"):
        st.session_state.pop("thread", None)
        st.session_state.pop("verlauf", None)
        st.rerun()
    auslastung()
    st.caption(f"GLM-5.3 Flash · Swiss AI Research Platform · [GitHub]({REPO})  \n"
               "Antworten können Fehler enthalten. Verbindlich sind Moodle und die Dozierenden.")

st.title("🎓 Studienassistent")
if not st.session_state["verlauf"] and "vorschlag" not in st.session_state and not st.session_state.get("eingabe"):
    st.caption("Fragen zu Prüfungen, Abgaben und Fristen im BAI-Herbstsemester 2026, jede Antwort mit Quelle.  \n"
               "Module: " + " · ".join(suche.module()))
    st.pills("Beispiele", BEISPIELE, key="beispiel", on_change=beispiel_gewaehlt, label_visibility="collapsed")

for eintrag in st.session_state["verlauf"]:
    with st.chat_message(eintrag["rolle"]):
        st.markdown(eintrag["text"])
        if eintrag["rolle"] == "assistant":
            zeige_antwort(eintrag)

frage = st.chat_input("Deine Frage zum Studium …", key="eingabe") or st.session_state.pop("vorschlag", None)
if frage:
    st.session_state["verlauf"].append({"rolle": "user", "text": frage})
    with st.chat_message("user"):
        st.markdown(frage)
    with st.chat_message("assistant"):
        status, denkfeld, feld, text, gedanken = st.empty(), st.empty(), st.empty(), "", ""
        hinweise = {"unterlagen_durchsuchen": "🔎 Durchsuche die Unterlagen …", "fristen_anzeigen": "📅 Schaue in die Fristen …",
                    "module_auflisten": "📚 Liste die Module …"}
        nummer, start, suchen = schlange().anstellen(), time.time(), []
        try:  # finally gibt den Platz auch frei, wenn jemand die Seite schliesst oder neu lädt
            while (stelle := schlange().position(nummer)) > 0:
                status.caption(f"⏳ Gerade fragen viele gleichzeitig. Du bist Nr. {stelle} in der Warteschlange …")
                time.sleep(1)
            status.caption("🛡️ Prüfe die Frage …")
            for art, inhalt in fragen_live(graph, frage, st.session_state["thread"]):
                if art == "werkzeug":  # Zwischentext vor einer Suche verwerfen, nur die Endantwort bleibt stehen
                    suchen.append(inhalt)
                    status.caption(hinweise.get(inhalt, "Arbeite …"))
                    text = ""
                    feld.empty()
                elif art == "denken":  # Entwurf verwerfen: Jetzt schreibt das Modell mit Reasoning die Antwort
                    status.caption("🧠 Denke über die Antwort nach …")
                    text = ""
                    feld.empty()
                elif art == "gedanke":  # sofort sichtbar: das Modell denkt laut, bevor der Text kommt
                    gedanken += inhalt
                    status.caption("🧠 Denke nach …")
                    denkfeld.markdown(gedanken_html(gedanken, nur_ende=500), unsafe_allow_html=True)
                elif art == "text":
                    status.empty()
                    denkfeld.empty()
                    text += inhalt
                    feld.markdown(text + " ▌")
                else:
                    r = inhalt
        except Exception as fehler:  # noqa: BLE001 – Plattform nicht erreichbar, Zeitlimit: Hinweis statt Absturz
            r = {"antwort": "Die Sprachmodell-Plattform antwortet gerade nicht oder zu langsam. Versuch es bitte in einer "
                            f"Minute nochmals. ({type(fehler).__name__})", "quellen": [], "abgelehnt": False}
        finally:
            schlange().fertig(nummer)
        betrieb().frage_erledigt(st.session_state["besucher"], start)
        status.empty()
        denkfeld.empty()
        feld.markdown(r["antwort"])
        n_suche = sum(1 for s in suchen if s == "unterlagen_durchsuchen")
        schritte = ["🛡️ abgelehnt" if r.get("abgelehnt") else "🛡️ geprüft"]
        schritte += [f"🔎 {n_suche} {'Suche' if n_suche == 1 else 'Suchen'}"] if n_suche else []
        schritte += ["📅 Fristen"] if "fristen_anzeigen" in suchen else []
        schritte += [] if r.get("abgelehnt") else ["🧠 Antwort mit Reasoning"]
        eintrag = {"rolle": "assistant", "text": r["antwort"], "quellen": r["quellen"], "frage": frage, "id": str(uuid.uuid4()),
                   "gedanken": gedanken, "ablauf": " → ".join(schritte), "sekunden": time.time() - start}
        zeige_antwort(eintrag)
    st.session_state["verlauf"].append(eintrag)
