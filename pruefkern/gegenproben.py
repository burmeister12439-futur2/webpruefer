#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gegenproben.py — beschaedigt die Seite absichtlich und prueft, dass es auffaellt.

Eine Pruefung, die nur am heilen Stand gruen zeigt, beweist nichts. Sie koennte
alles gruen melden. Deshalb wird sie hier gegen fuenf absichtlich beschaedigte
Kopien gehalten. Jede muss rot werden, jede mit dem richtigen Befund.

Die Kopien entstehen in einem Ordner ausserhalb des Projekts und werden nie
committet. Die geltende Seite wird nicht angefasst.

Gegenprobe 5 gibt es zweimal: per inline-CSS versteckt faengt die statische
Pruefung, per CSS-Klasse versteckt faengt nur die Browserpruefung. Die Datei
fuer den zweiten Fall wird erzeugt und liegen gelassen, damit die
Browserpruefung sie nachweisen kann.

Aufruf:  python3 _werkzeug/gegenproben.py
Rueckgabe: 0 wenn jede Gegenprobe rot wurde, sonst 1.
"""
import io, os, re, subprocess, sys, tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
PRUEFER = os.path.join(HIER, "pruefe_seite.py")

# Projekt, Profil und Seite kommen von aussen. Der Pruefkern kennt kein Projekt.
if len(sys.argv) >= 3:
    PROJEKT = os.path.abspath(sys.argv[1])
    SOLL = os.path.abspath(sys.argv[2])
    SEITE = os.path.join(PROJEKT, sys.argv[3] if len(sys.argv) > 3 else "index.html")
else:
    print("Aufruf: gegenproben.py <projektordner> <_pruefprofil.json> [seite.html]")
    sys.exit(2)


def kaputt_1(s):
    alt = "</div>\n</details>\n<div class=\"fragen\">\n<h4>Fragen zu Abschnitt D</h4>"
    neu = "<div class=\"fragen\">\n<h4>Fragen zu Abschnitt D</h4>"
    assert s.count(alt) == 1
    return s.replace(alt, neu), "das schliessende </details> vor den Fragen zu Abschnitt D entfernt"


def kaputt_2(s):
    for k in ("1a", "1b"):
        m = re.search(r'\n<textarea id="f%s" data-frage="%s"[^>]*></textarea>' % (k, k), s)
        assert m, k
        s = s[:m.start()] + s[m.end():]
    return s, "die beiden Antwortfelder f1a und f1b aus Abschnitt B geloescht"


def kaputt_3(s):
    alt = ' data-frage="4a"'
    assert s.count(alt) == 1
    return s.replace(alt, ""), "dem Feld f4a das data-frage genommen"


def kaputt_4(s):
    alt = '<label for="f9a">'
    assert s.count(alt) == 1
    return s.replace(alt, '<label for="f9a-vertippt">'), "das Label von f9a auf eine falsche id zeigen lassen"


def kaputt_5a(s):
    alt = '<textarea id="f0a" data-frage="0a" rows="4" style="width:100%'
    neu = '<textarea id="f0a" data-frage="0a" rows="4" style="display:none;width:100%'
    assert s.count(alt) == 1
    return s.replace(alt, neu), "das Antwortfeld in Abschnitt A per inline-CSS versteckt"


def kaputt_5b(s):
    alt = '<textarea id="f0a" data-frage="0a" '
    neu = '<textarea id="f0a" data-frage="0a" class="weg" '
    assert s.count(alt) == 1
    s = s.replace(alt, neu)
    assert s.count("</head>") == 1
    return s.replace("</head>", "<style>.weg{display:none}</style>\n</head>"), \
           "das Antwortfeld in Abschnitt A per CSS-Klasse versteckt (faengt nur die Browserpruefung)"


# --- Faelle fuer die Browserpruefung ---------------------------------------
# Die statische Pruefung liest kein Stylesheet und kennt keine Fensterbreite.
# Diese Faelle gehen deshalb an pruefe_browser.js.

BREITE_TABELLE = ("""
<section id="probe"><div class="wrap">
<h2>Gegenprobe</h2>
<div style="%s">
<table style="min-width:900px;border-collapse:collapse">
<tr><th>Spalte eins</th><th>Spalte zwei</th><th>Spalte drei</th><th>Spalte vier</th></tr>
<tr><td>Wert</td><td>Wert</td><td>Wert</td><td>Wert am rechten Rand</td></tr>
</table>
</div>
</div></section>
""")


def kaputt_6(s):
    """Breite Tabelle in einem bedienbaren Scrollkasten. Muss gruen bleiben."""
    kasten = BREITE_TABELLE % "overflow-x:auto"
    return s.replace("</body>", kasten + "</body>", 1), \
           "eine 900px breite Tabelle in einem Kasten mit overflow-x:auto eingesetzt"


def kaputt_7(s):
    """Dieselbe Tabelle in einem abschneidenden Kasten. Muss rot werden."""
    kasten = BREITE_TABELLE % "overflow-x:hidden"
    return s.replace("</body>", kasten + "</body>", 1), \
           "dieselbe Tabelle in einem Kasten mit overflow-x:hidden eingesetzt"


BROWSERFAELLE = [("5b per CSS-Klasse verstecktes Feld", kaputt_5b, "muss rot werden"),
                 ("6 breite Tabelle im Scrollkasten", kaputt_6, "muss gruen bleiben"),
                 ("7 dieselbe Tabelle in overflow-x:hidden", kaputt_7, "muss rot werden")]


FAELLE = [("1 kaputte Verschachtelung", kaputt_1),
          ("2 zwei entfernte Felder", kaputt_2),
          ("3 Feld ohne data-frage", kaputt_3),
          ("4 Feld ohne Label", kaputt_4),
          ("5a per inline-CSS verstecktes Feld", kaputt_5a)]


def main():
    roh = io.open(SEITE, encoding="utf-8").read()
    ordner = tempfile.mkdtemp(prefix="gegenproben_")
    print("Gegenproben gegen %s" % SEITE)
    print("Kopien liegen in %s, das Projekt bleibt unberuehrt.\n" % ordner)
    alle_rot = True
    for name, fn in FAELLE:
        s, was = fn(roh)
        # Jede Gegenprobe bekommt einen eigenen Unterordner und behaelt den
        # Dateinamen der Seite. Sonst findet der Pruefer den Profileintrag nicht
        # und bricht ab, statt zu pruefen. Ein Abbruch ist kein Befund.
        unter = os.path.join(ordner, name.split()[0])
        os.makedirs(unter, exist_ok=True)
        p = os.path.join(unter, os.path.basename(SEITE))
        io.open(p, "w", encoding="utf-8").write(s)
        r = subprocess.run([sys.executable, PRUEFER, p, SOLL],
                           capture_output=True, text=True)
        befunde = [l.strip() for l in r.stdout.splitlines() if "BEFUND" in l]
        print("=" * 74)
        print("GEGENPROBE %s" % name)
        print("   beschaedigt: %s" % was)
        for b in befunde[:6]:
            print("   " + b)
        if len(befunde) > 6:
            print("   ... und %d weitere Befunde" % (len(befunde) - 6))
        schluss = [l for l in r.stdout.splitlines() if l.startswith("NICHT BESTANDEN") or l == "BESTANDEN"]
        print("   Ergebnis: %s" % (schluss[-1] if schluss else "(keine Meldung)"))
        print("   Rueckgabecode: %d  %s" % (r.returncode, "richtig, der Push wird angehalten"
                                            if r.returncode == 1 else "FALSCH, das haette rot werden muessen"))
        if r.returncode != 1 or not befunde:
            # Rueckgabe 1 ohne einen einzigen Befund heisst: der Pruefer ist
            # abgebrochen, statt zu pruefen. Das ist kein bestandener Nachweis.
            print("   ACHTUNG: kein Befund ausgegeben. Der Pruefer hat nicht geprueft,")
            print("            sondern abgebrochen. Das zaehlt nicht als Nachweis.")
            alle_rot = False
        print()

    print("=" * 74)
    print("FAELLE FUER DIE BROWSERPRUEFUNG")
    print("   Die statische Pruefung liest kein Stylesheet und kennt keine")
    print("   Fensterbreite. Diese drei Dateien gehen deshalb an pruefe_browser.js.")
    print()
    for name, fn, erwartung in BROWSERFAELLE:
        s2, was = fn(roh)
        unter = os.path.join(ordner, name.split()[0])
        os.makedirs(unter, exist_ok=True)
        pfad = os.path.join(unter, os.path.basename(SEITE))
        io.open(pfad, "w", encoding="utf-8").write(s2)
        print("   GEGENPROBE %s  (%s)" % (name, erwartung))
        print("      veraendert: %s" % was)
        print("      node _werkzeug/pruefe_browser.js %s" % pfad)
        print()

    print("=" * 74)
    if alle_rot:
        print("ALLE GEGENPROBEN ROT. Die Pruefung greift.")
        return 0
    print("MINDESTENS EINE GEGENPROBE BLIEB GRUEN. Die Pruefung greift nicht.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
