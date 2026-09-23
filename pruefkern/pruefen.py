#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefen.py — der Ablauf des gemeinsamen Pruefkerns.

Wird von pruefen.sh im Projekt aufgerufen, nie direkt mit einem persoenlichen
Pfad. Er liest das Pruefprofil des Projekts und fuehrt fuer jede dort
eingetragene Seite die Pruefungen aus:

  1 die statische Strukturpruefung (pruefe_seite.py)
  2 das Protokoll der Browserpruefung (pruefe_protokoll.py), sofern das Profil
    fuer diese Seite eine Browserpruefung verlangt

Rueckgabe: 0 bestanden, 1 Befunde.
"""
import json, os, subprocess, sys

KERN = os.path.dirname(os.path.abspath(__file__))


def main(projekt, profilpfad):
    with open(profilpfad, encoding="utf-8") as f:
        profil = json.load(f)
    seiten = profil.get("seiten", [])
    if not seiten:
        print("Das Pruefprofil nennt keine einzige Seite. Nichts zu pruefen ist kein Ergebnis.")
        return 1

    fehler = 0
    for eintrag in seiten:
        seite = os.path.join(projekt, eintrag["datei"])
        if not os.path.exists(seite):
            print("BEFUND  die im Profil genannte Seite fehlt: %s" % eintrag["datei"])
            fehler = 1
            continue

        r = subprocess.run([sys.executable, os.path.join(KERN, "pruefe_seite.py"),
                            seite, profilpfad])
        if r.returncode != 0:
            fehler = 1

        art = eintrag.get("browserpruefung", "voll")
        if art == "keine":
            print("\n8 Protokoll der Browserpruefung")
            print("   uebersprungen, das Profil verlangt fuer diese Seite keine Browserpruefung")
            continue
        prot = eintrag.get("protokoll")
        if not prot:
            print("\n8 Protokoll der Browserpruefung")
            print("   BEFUND  das Profil verlangt eine Browserpruefung (%s), nennt aber keinen" % art)
            print("           Ablageort fuer das Protokoll.")
            fehler = 1
            continue
        r = subprocess.run([sys.executable, os.path.join(KERN, "pruefe_protokoll.py"),
                            seite, os.path.join(projekt, prot),
                            os.path.join(KERN, "pruefe_browser.js"),
                            profilpfad])
        if r.returncode != 0:
            fehler = 1

    print()
    if fehler:
        print("NICHT BESTANDEN. Siehe die Befunde oben.")
        return 1
    print("ALLE PRUEFUNGEN BESTANDEN.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Aufruf: pruefen.py <projektordner> <_pruefprofil.json>")
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
