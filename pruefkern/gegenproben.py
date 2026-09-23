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
import io, os, re, subprocess, sys, tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
PRUEFER = os.path.join(HIER, "pruefe_seite.py")

if len(sys.argv) < 3:
    print("Aufruf: gegenproben.py <projektordner> <_pruefprofil.json> [seite.html]")
    sys.exit(2)
PROJEKT = os.path.abspath(sys.argv[1])
PROFIL = os.path.abspath(sys.argv[2])
SEITE = os.path.join(PROJEKT, sys.argv[3] if len(sys.argv) > 3 else "index.html")

FELD = re.compile(r"<textarea\b[^>]*>.*?</textarea>", re.S | re.I)


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


STATISCH = [("1 kaputte Verschachtelung", kaputt_1),
            ("2 zwei entfernte Felder", kaputt_2),
            ("3 Feld ohne data-frage", kaputt_3),
            ("4 Feld ohne Label", kaputt_4),
            ("5a per inline-CSS verstecktes Feld", kaputt_5a)]

IM_BROWSER = [("5b per CSS-Klasse verstecktes Feld", kaputt_5b, "muss rot werden"),
              ("6 breite Tabelle im Scrollkasten", kaputt_6, "muss gruen bleiben"),
              ("7 dieselbe Tabelle in overflow-x:hidden", kaputt_7, "muss rot werden")]


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
        unter = os.path.join(ordner, name.split()[0])
        os.makedirs(unter, exist_ok=True)
        pfad = os.path.join(unter, os.path.basename(SEITE))
        io.open(pfad, "w", encoding="utf-8").write(s)
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
    print("   Die statische Pruefung liest kein Stylesheet und kennt keine")
    print("   Fensterbreite. Diese Dateien gehen an pruefe_browser.js.")
    print()
    for name, fn, erwartung in IM_BROWSER:
        s, was = fn(roh)
        print("   GEGENPROBE %s  (%s)" % (name, erwartung))
        if s is None:
            print("      %s" % was)
            print()
            continue
        unter = os.path.join(ordner, name.split()[0])
        os.makedirs(unter, exist_ok=True)
        pfad = os.path.join(unter, os.path.basename(SEITE))
        io.open(pfad, "w", encoding="utf-8").write(s)
        print("      veraendert: %s" % was)
        print("      node %s %s %s" % (os.path.join(HIER, "pruefe_browser.js"), pfad, PROFIL))
        print()

    print("=" * 74)
    if alle_rot:
        print("ALLE ANWENDBAREN GEGENPROBEN ROT. Die Pruefung greift.")
        return 0
    print("MINDESTENS EINE GEGENPROBE BLIEB GRUEN ODER BRACH AB. Die Pruefung greift nicht.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
