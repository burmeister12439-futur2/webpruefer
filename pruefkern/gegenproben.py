#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gegenproben.py — beschaedigt eine Seite absichtlich und prueft, dass es auffaellt.

Eine Pruefung, die nur am heilen Stand gruen zeigt, beweist nichts. Sie koennte
alles gruen melden. Deshalb wird sie hier gegen absichtlich beschaedigte Kopien
gehalten. Jede muss rot werden, und zwar mit einem Befund. Eine rote Ampel aus
dem falschen Grund, etwa weil der Pruefer abbricht statt zu pruefen, zaehlt
nicht.

Der Kern kennt kein Projekt. Alle Beschaedigungen werden aus der Seite selbst
abgeleitet, nicht aus festen Zeichenketten eines bestimmten Projekts. Wo eine
Seite das noetige Element nicht hat, entfaellt der Fall und wird als entfallen
gemeldet, nicht als bestanden.

Die Kopien entstehen ausserhalb des Projekts und werden nie committet. Die
geltende Seite wird nicht angefasst.

Aufruf:  gegenproben.py <projektordner> <_pruefprofil.json> [seite.html]
Rueckgabe: 0 wenn jede anwendbare Gegenprobe rot wurde, sonst 1.
"""
import io, json, os, re, subprocess, sys, tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
PRUEFER = os.path.join(HIER, "pruefe_seite.py")
BROWSERPRUEFER = os.path.join(HIER, "pruefe_browser.js")

if len(sys.argv) < 3:
    print("Aufruf: gegenproben.py <projektordner> <_pruefprofil.json> [seite.html]")
    sys.exit(2)
PROJEKT = os.path.abspath(sys.argv[1])
PROFIL = os.path.abspath(sys.argv[2])
SEITE = os.path.join(PROJEKT, sys.argv[3] if len(sys.argv) > 3 else "index.html")

# Auch die Beschaedigungen an Bedienteilen muessen aus dem Projekt kommen und
# nicht aus festen Zeichenketten. Was ein Bedienteil ist und wie der Ablauf
# heisst, steht im Profil.
_p = json.load(io.open(PROFIL, encoding="utf-8"))
_e = None
for _s in _p.get("seiten", []):
    if os.path.basename(_s.get("datei", "")) == os.path.basename(SEITE):
        _e = _s
        break
EINTRAG = _e or (_p.get("seiten") or [{}])[0]
BEDIENFELDER = list((EINTRAG.get("bedienfelder") or {}).keys())
PFLICHTSICHTBAR = list(EINTRAG.get("pflichtsichtbar") or [])
ABLAUF = EINTRAG.get("bedienablauf") or {}

FELD = re.compile(r"<textarea\b[^>]*>.*?</textarea>", re.S | re.I)


def waehler(x):
    """Aus einer Kennung oder einem Waehler einen CSS-Waehler machen."""
    return x if x.startswith(("#", ".", "[")) else "#" + x


def element_von(s, wahl):
    """Das Element zu einem id-Waehler im Rohtext finden. Nur ids, weil nur die
    im Profil vorkommen und weil ein Regex nichts anderes verlaesslich trifft."""
    if not wahl.startswith("#"):
        return None
    kennung = wahl[1:]
    m = re.search(r'<([a-zA-Z][\w-]*)\b[^>]*\sid="%s"' % re.escape(kennung), s)
    if not m:
        return None
    tag = m.group(1).lower()
    if tag in ("input", "img", "br", "hr", "meta", "link"):
        ende = s.find(">", m.start())
        return (m.start(), ende + 1, tag)
    schluss = re.search(r"</%s\s*>" % re.escape(tag), s[m.start():], re.I)
    if not schluss:
        return None
    return (m.start(), m.start() + schluss.end(), tag)


def skript_ans_ende(s, code):
    if "</body>" not in s:
        return None
    return s.replace("</body>", "<script>%s</script>\n</body>" % code, 1)


def felder(s):
    return list(FELD.finditer(s))


def kaputt_1(s):
    """Das erste schliessende </details> entfernen. Was dahinter stand, faellt
    damit in ein zugeklapptes Fenster. Genau der Fehler vom 22.09.2026."""
    m = re.search(r"</details>", s, re.I)
    if not m:
        return None, "entfaellt, die Seite hat kein einziges <details>"
    return s[:m.start()] + s[m.end():], "das erste schliessende </details> entfernt"


def kaputt_2(s):
    """Die ersten beiden Antwortfelder loeschen."""
    ms = felder(s)
    if len(ms) < 2:
        return None, "entfaellt, die Seite hat weniger als zwei Antwortfelder"
    for m in reversed(ms[:2]):
        s = s[:m.start()] + s[m.end():]
    return s, "die ersten beiden Antwortfelder geloescht"


def kaputt_3(s):
    """Dem ersten Antwortfeld das data-frage nehmen."""
    for m in felder(s):
        t = re.search(r'\sdata-frage="[^"]*"', m.group(0))
        if t:
            neu = m.group(0)[:t.start()] + m.group(0)[t.end():]
            return s[:m.start()] + neu + s[m.end():], "dem ersten Antwortfeld das data-frage genommen"
    return None, "entfaellt, kein Antwortfeld mit data-frage gefunden"


def kaputt_4(s):
    """Das Label des ersten Antwortfelds auf eine falsche Kennung zeigen lassen."""
    for m in felder(s):
        i = re.search(r'\sid="([^"]+)"', m.group(0))
        if not i:
            continue
        kennung = i.group(1)
        lab = re.search(r'<label\s+for="%s"' % re.escape(kennung), s)
        if lab:
            neu = s[:lab.start()] + '<label for="%s-vertippt"' % kennung + s[lab.end():]
            return neu, "das Label von %s auf eine falsche Kennung zeigen lassen" % kennung
    return None, "entfaellt, kein Antwortfeld mit id und passendem Label gefunden"


def kaputt_5a(s):
    """Das erste Antwortfeld per inline-CSS verstecken."""
    ms = felder(s)
    if not ms:
        return None, "entfaellt, die Seite hat kein Antwortfeld"
    m = ms[0]
    roh = m.group(0)
    st = re.search(r'\sstyle="', roh)
    if st:
        neu = roh[:st.end()] + "display:none;" + roh[st.end():]
    else:
        neu = re.sub(r"^<textarea\b", '<textarea style="display:none"', roh, count=1)
    return s[:m.start()] + neu + s[m.end():], "das erste Antwortfeld per inline-CSS versteckt"


def kaputt_5b(s):
    """Das erste Antwortfeld per CSS-Klasse verstecken. Faengt nur die Browserpruefung."""
    ms = felder(s)
    if not ms or "</head>" not in s:
        return None, "entfaellt, kein Antwortfeld oder kein </head>"
    m = ms[0]
    neu = re.sub(r"^<textarea\b", '<textarea class="pruefprobe-weg"', m.group(0), count=1)
    s = s[:m.start()] + neu + s[m.end():]
    return s.replace("</head>", "<style>.pruefprobe-weg{display:none}</style>\n</head>", 1), \
        "das erste Antwortfeld per CSS-Klasse versteckt"


TABELLE = """
<section id="pruefprobe"><div style="%s">
<table style="min-width:900px;border-collapse:collapse">
<tr><th>eins</th><th>zwei</th><th>drei</th><th>vier</th></tr>
<tr><td>Wert</td><td>Wert</td><td>Wert</td><td>Wert am rechten Rand</td></tr>
</table></div></section>
"""


def kaputt_6(s):
    if "</body>" not in s:
        return None, "entfaellt, kein </body>"
    return s.replace("</body>", TABELLE % "overflow-x:auto" + "</body>", 1), \
        "eine 900px breite Tabelle in einem Kasten mit overflow-x:auto eingesetzt"


def kaputt_7(s):
    if "</body>" not in s:
        return None, "entfaellt, kein </body>"
    return s.replace("</body>", TABELLE % "overflow-x:hidden" + "</body>", 1), \
        "dieselbe Tabelle in einem Kasten mit overflow-x:hidden eingesetzt"


def kaputt_8(s):
    """Ein Bedienfeld ganz entfernen. Muss in 5b auffallen."""
    if not PFLICHTSICHTBAR:
        return None, "entfaellt, das Profil nennt kein pflichtsichtbares Bedienteil"
    wahl = waehler(PFLICHTSICHTBAR[0])
    treffer = element_von(s, wahl)
    if not treffer:
        return None, "entfaellt, %s ist im Rohtext nicht als Element auffindbar" % wahl
    a, b, _ = treffer
    return s[:a] + s[b:], "das Bedienteil %s ganz entfernt" % wahl


def kaputt_9(s):
    """Ein Bedienfeld per CSS-Klasse verstecken. Muss in 5b auffallen."""
    if not PFLICHTSICHTBAR or "</head>" not in s:
        return None, "entfaellt, kein pflichtsichtbares Bedienteil oder kein </head>"
    wahl = waehler(PFLICHTSICHTBAR[-1])
    treffer = element_von(s, wahl)
    if not treffer:
        return None, "entfaellt, %s ist im Rohtext nicht als Element auffindbar" % wahl
    a, b, tag = treffer
    roh = s[a:b]
    neu = re.sub(r"^<%s\b" % re.escape(tag), '<%s class="pruefprobe-weg"' % tag, roh, count=1, flags=re.I)
    s = s[:a] + neu + s[b:]
    return s.replace("</head>", "<style>.pruefprobe-weg{display:none}</style>\n</head>", 1), \
        "das Bedienteil %s per CSS-Klasse versteckt" % wahl


def kaputt_10(s):
    """Dem Knopf des Bedienablaufs die Wirkung nehmen, ohne ihn zu entfernen.
    Der Knopf bleibt sichtbar und klickbar; er loest nur nichts mehr aus. Genau
    diesen Fall wuerde blosses Zaehlen von Bedienteilen nicht bemerken."""
    if not ABLAUF.get("knopf"):
        return None, "entfaellt, das Profil nennt keinen Knopf"
    k = ABLAUF["knopf"]
    code = ("document.addEventListener('DOMContentLoaded',function(){"
            "var b=document.querySelector(%s);if(b)b.replaceWith(b.cloneNode(true));});" % json.dumps(k))
    neu = skript_ans_ende(s, code)
    if neu is None:
        return None, "entfaellt, kein </body>"
    return neu, "dem Knopf %s alle Ereignisbindungen genommen, er bleibt sichtbar" % k


def kaputt_11(s):
    """Die Antwort ausbleiben lassen. Das Antwortfeld wird sichtbar, bleibt aber
    leer. Auch das faellt beim blossen Zaehlen nicht auf."""
    if not ABLAUF.get("antwort"):
        return None, "entfaellt, das Profil nennt kein Antwortfeld des Ablaufs"
    a = ABLAUF["antwort"]
    code = ("document.addEventListener('DOMContentLoaded',function(){"
            "var e=document.querySelector(%s);if(!e)return;"
            "new MutationObserver(function(){if(e.textContent)e.textContent='';})"
            ".observe(e,{childList:true,subtree:true,characterData:true});});" % json.dumps(a))
    neu = skript_ans_ende(s, code)
    if neu is None:
        return None, "entfaellt, kein </body>"
    return neu, "das Antwortfeld %s dauerhaft leeren lassen" % a


def kaputt_12(s):
    """Eine Anfrage nach draussen einsetzen, die im Profil nicht steht. Die
    Gegenprobe zur Liste der benannten Aussenanfragen: erlaubt ist nur, was
    dort mit Grund eingetragen ist, nicht alles Externe."""
    if "</head>" not in s:
        return None, "entfaellt, kein </head>"
    return s.replace("</head>",
                     '<script src="https://pruefprobe.invalid/nicht-im-profil.js"></script>\n</head>', 1), \
        "ein externes Skript eingesetzt, das im Profil nicht benannt ist"


STATISCH = [("1 kaputte Verschachtelung", kaputt_1),
            ("2 zwei entfernte Felder", kaputt_2),
            ("3 Feld ohne data-frage", kaputt_3),
            ("4 Feld ohne Label", kaputt_4),
            ("5a per inline-CSS verstecktes Feld", kaputt_5a)]

IM_BROWSER = [("5b per CSS-Klasse verstecktes Feld", kaputt_5b, "muss rot werden"),
              ("6 breite Tabelle im Scrollkasten", kaputt_6, "muss gruen bleiben"),
              ("7 dieselbe Tabelle in overflow-x:hidden", kaputt_7, "muss rot werden"),
              ("8 fehlendes Bedienfeld", kaputt_8, "muss rot werden"),
              ("9 verstecktes Bedienfeld", kaputt_9, "muss rot werden"),
              ("10 Knopf ohne Wirkung", kaputt_10, "muss rot werden"),
              ("11 ausbleibende Antwort", kaputt_11, "muss rot werden"),
              ("12 nicht benannte Aussenanfrage", kaputt_12, "muss rot werden")]


def bauplatz(ordner, nr, inhalt):
    """Eine beschaedigte Kopie ablegen, zusammen mit Verweisen auf alle
    Nachbardateien der Originalseite. Ohne ihre Bilder und Schriften wuerde die
    Kopie Ladefehler melden, die nichts mit der eingebauten Beschaedigung zu tun
    haben, und die Gegenprobe wuerde aus dem falschen Grund rot. Verweise, keine
    Kopien: das Projekt wird nur gelesen."""
    unter = os.path.join(ordner, nr)
    os.makedirs(unter, exist_ok=True)
    quelle = os.path.dirname(os.path.abspath(SEITE))
    for eintrag in os.listdir(quelle):
        if eintrag == os.path.basename(SEITE):
            continue
        ziel = os.path.join(unter, eintrag)
        if not os.path.lexists(ziel):
            try:
                os.symlink(os.path.join(quelle, eintrag), ziel)
            except OSError:
                pass
    pfad = os.path.join(unter, os.path.basename(SEITE))
    io.open(pfad, "w", encoding="utf-8").write(inhalt)
    return pfad


def main():
    roh = io.open(SEITE, encoding="utf-8").read()
    ordner = tempfile.mkdtemp(prefix="gegenproben_")
    print("Gegenproben gegen %s" % SEITE)
    print("Kopien liegen in %s, das Projekt bleibt unberuehrt.\n" % ordner)

    alle_rot = True
    for name, fn in STATISCH:
        s, was = fn(roh)
        print("=" * 74)
        print("GEGENPROBE %s" % name)
        if s is None:
            print("   %s" % was)
            print()
            continue
        pfad = bauplatz(ordner, name.split()[0], s)
        r = subprocess.run([sys.executable, PRUEFER, pfad, PROFIL], capture_output=True, text=True)
        befunde = [l.strip() for l in r.stdout.splitlines() if "BEFUND" in l]
        print("   beschaedigt: %s" % was)
        for b in befunde[:6]:
            print("   " + b)
        if len(befunde) > 6:
            print("   ... und %d weitere Befunde" % (len(befunde) - 6))
        schluss = [l for l in r.stdout.splitlines() if l.startswith("NICHT BESTANDEN") or l == "BESTANDEN"]
        print("   Ergebnis: %s" % (schluss[-1] if schluss else "(keine Meldung)"))
        print("   Rueckgabecode: %d  %s" % (
            r.returncode, "richtig, der Push wird angehalten" if r.returncode == 1 else "FALSCH"))
        if r.returncode != 1 or not befunde:
            print("   ACHTUNG: kein Befund ausgegeben. Der Pruefer hat nicht geprueft,")
            print("            sondern abgebrochen. Das zaehlt nicht als Nachweis.")
            alle_rot = False
        print()

    print("=" * 74)
    print("FAELLE FUER DIE BROWSERPRUEFUNG")
    print("   Die statische Pruefung liest kein Stylesheet, kennt keine")
    print("   Fensterbreite und loest nichts aus. Diese Faelle gehen an")
    print("   pruefe_browser.js.")
    print()

    # Laeuft Playwright hier? Wenn nicht, werden die Faelle nur vorbereitet und
    # der Aufruf ausgegeben. Das wird dann laut gesagt und nicht als Nachweis
    # verbucht: ein nicht ausgefuehrter Fall ist kein bestandener Fall.
    probe = subprocess.run(["node", "-e", "require(process.env.PW||'playwright')"],
                           capture_output=True, text=True)
    lauffaehig = probe.returncode == 0
    if not lauffaehig:
        print("   Playwright ist hier nicht aufrufbar. Die Faelle werden nur")
        print("   vorbereitet; ausgefuehrt sind sie damit nicht.")
        print()

    for name, fn, erwartung in IM_BROWSER:
        s, was = fn(roh)
        print("   GEGENPROBE %s  (%s)" % (name, erwartung))
        if s is None:
            print("      %s" % was)
            print()
            continue
        pfad = bauplatz(ordner, name.split()[0], s)
        print("      veraendert: %s" % was)
        if not lauffaehig:
            print("      node %s %s %s" % (BROWSERPRUEFER, pfad, PROFIL))
            alle_rot = False
            print()
            continue
        r = subprocess.run(["node", BROWSERPRUEFER, pfad, PROFIL], capture_output=True, text=True)
        befunde = [l.strip() for l in r.stdout.splitlines() if "BEFUND" in l]
        for b in befunde[:6]:
            print("      " + b)
        if len(befunde) > 6:
            print("      ... und %d weitere Befunde" % (len(befunde) - 6))
        schluss = [l for l in r.stdout.splitlines() if l.startswith("NICHT BESTANDEN") or l == "BESTANDEN"]
        print("      Ergebnis: %s" % (schluss[-1] if schluss else "(keine Meldung)"))
        print("      Rueckgabecode: %d" % r.returncode)
        soll_rot = erwartung.startswith("muss rot")
        if soll_rot:
            gut = r.returncode == 1 and bool(befunde)
            print("      %s" % ("richtig, die Beschaedigung faellt auf" if gut else
                                "FALSCH, die Beschaedigung faellt nicht auf oder der Pruefer brach ab"))
        else:
            gut = r.returncode == 0
            print("      %s" % ("richtig, die Absicht wird nicht als Fehler gemeldet" if gut else
                                "FALSCH, eine gewollte Loesung wird als Fehler gemeldet"))
        if not gut:
            if r.returncode not in (0, 1):
                print("      Fehlerausgabe: %s" % (r.stderr.strip().splitlines() or ["(leer)"])[-1])
            alle_rot = False
        print()

    # --- Gegenprobe am Pruefprotokoll -----------------------------------
    # Die Faelle oben beschaedigen die Seite. Dieser Fall beschaedigt nichts an
    # der Seite, sondern aendert das Profil. Ein vorhandenes, gruenes Protokoll
    # muss dadurch ungueltig werden: am Profil haengt, was ueberhaupt geprueft
    # wird. Ohne diese Bindung bliebe ein gruenes Protokoll stehen, waehrend
    # zum Beispiel eine erlaubte Aussenanfrage zurueckgenommen wurde.
    print("=" * 74)
    print("GEGENPROBE 13 geaendertes Profil bei unveraenderter Seite")
    prot_rel = EINTRAG.get("protokoll")
    pruefer_js = BROWSERPRUEFER
    if not prot_rel:
        print("   entfaellt, das Profil nennt keinen Ablageort fuer das Protokoll")
    elif not os.path.exists(os.path.join(PROJEKT, prot_rel)):
        print("   entfaellt, es gibt noch kein Protokoll unter %s" % prot_rel)
    else:
        unter = os.path.join(ordner, "13")
        os.makedirs(unter, exist_ok=True)
        # Das Profil um eine Kleinigkeit veraendern, inhaltlich folgenlos.
        roh_profil = io.open(PROFIL, encoding="utf-8").read()
        profil_kopie = os.path.join(unter, os.path.basename(PROFIL))
        io.open(profil_kopie, "w", encoding="utf-8").write(
            roh_profil.rstrip("\n") + "\n\n")
        pruefwerkzeug = os.path.join(HIER, "pruefe_protokoll.py")
        r = subprocess.run([sys.executable, pruefwerkzeug,
                            SEITE, os.path.join(PROJEKT, prot_rel),
                            pruefer_js, profil_kopie],
                           capture_output=True, text=True)
        befunde = [l.strip() for l in r.stdout.splitlines() if "BEFUND" in l]
        print("   veraendert: das Profil, die Seite bleibt unberuehrt")
        for b in befunde[:4]:
            print("   " + b)
        print("   Rueckgabecode: %d" % r.returncode)
        gut = r.returncode == 1 and any("Profils" in b for b in befunde)
        print("   %s" % ("richtig, das Protokoll gilt nicht mehr" if gut else
                         "FALSCH, das Protokoll bleibt trotz geaendertem Profil gueltig"))
        if not gut:
            alle_rot = False
    print()

    print("=" * 74)
    if alle_rot:
        print("ALLE ANWENDBAREN GEGENPROBEN HABEN SICH RICHTIG VERHALTEN.")
        print("Die Pruefung greift.")
        return 0
    print("MINDESTENS EINE GEGENPROBE VERHIELT SICH FALSCH ODER BLIEB UNAUSGEFUEHRT.")
    print("Die Pruefung ist damit nicht nachgewiesen.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
