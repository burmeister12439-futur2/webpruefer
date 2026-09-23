#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefe_protokoll.py — haelt das Protokoll der Browserpruefung an die Seite
und an den Pruefer.

Die Browserpruefung braucht Playwright und laeuft deshalb nicht auf diesem
Rechner, sondern dort, wo Playwright liegt. Damit sie trotzdem nicht still
ausfallen kann, schreibt sie ein Protokoll mit zwei Fingerabdruecken. Dieses
Werkzeug prueft vier Dinge und wird vom Push-Haken aufgerufen:

  1 Das Protokoll gibt es.
  2 Sein sha256 ist der der Seite, die gleich hochgeladen wird.
  3 Sein pruefer_sha256 ist der von pruefe_browser.js. Ohne das bliebe ein
    altes gruenes Protokoll zu einer unveraenderten Seite gueltig, waehrend
    sich der Pruefer darunter geaendert hat. Von Klaus am 23.09.2026 verlangt.
  4 Sein Ergebnis lautet bestanden.

Ein Protokoll ohne pruefer_sha256 stammt aus der Zeit vor dieser Regel und
gilt nicht mehr.

Aufruf:  python3 _werkzeug/pruefe_protokoll.py <seite> <protokoll.json> [pruefer.js]
Rueckgabe: 0 bestanden, 1 Befunde.
"""
import sys, os, json, hashlib


def sha(pfad):
    return hashlib.sha256(open(pfad, "rb").read()).hexdigest()


def main(seite, prot, pruefer):
    print("\n8 Protokoll der Browserpruefung")
    if not os.path.exists(prot):
        print("   BEFUND  es gibt kein Protokoll %s. Die Browserpruefung ist nie gelaufen." % prot)
        return 1
    try:
        d = json.load(open(prot, encoding="utf-8"))
    except Exception as e:
        print("   BEFUND  das Protokoll ist nicht lesbar: %s" % e)
        return 1

    fehler = 0
    ist_seite = sha(seite)
    if d.get("sha256") != ist_seite:
        print("   BEFUND  das Protokoll gehoert zu einem anderen Stand der Seite.")
        print("           Seite      %s" % ist_seite)
        print("           Protokoll  %s" % d.get("sha256"))
        fehler = 1

    if not os.path.exists(pruefer):
        print("   BEFUND  der Pruefer %s fehlt, sein Fingerabdruck ist nicht pruefbar." % pruefer)
        fehler = 1
    else:
        ist_pruefer = sha(pruefer)
        if "pruefer_sha256" not in d:
            print("   BEFUND  das Protokoll nennt keinen pruefer_sha256. Es stammt aus der Zeit")
            print("           vor dieser Regel und gilt nicht mehr.")
            fehler = 1
        elif d.get("pruefer_sha256") != ist_pruefer:
            print("   BEFUND  das Protokoll gehoert zu einem anderen Stand des Pruefers.")
            print("           pruefe_browser.js  %s" % ist_pruefer)
            print("           Protokoll          %s" % d.get("pruefer_sha256"))
            fehler = 1

    if d.get("ergebnis") != "bestanden":
        print("   BEFUND  die Browserpruefung war nicht bestanden: %s"
              % "; ".join(d.get("befunde", [])))
        fehler = 1

    if fehler:
        print("           Die Browserpruefung muss fuer diesen Stand neu laufen.")
    else:
        print("   in Ordnung, Browserpruefung bestanden am %s, passend zu Seite und Pruefer"
              % d.get("zeitpunkt", "(ohne Zeitpunkt)"))
    return fehler


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Aufruf: pruefe_protokoll.py <seite> <protokoll.json> [pruefer.js]")
        sys.exit(1)
    pruefer = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "pruefe_browser.js")
    sys.exit(main(sys.argv[1], sys.argv[2], pruefer))
