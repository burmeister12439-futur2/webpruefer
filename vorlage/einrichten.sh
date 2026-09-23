#!/bin/sh
# einrichten.sh — richtet die Pruefung dieses Projekts auf einem neuen Rechner ein.
#
# Versioniert und im Projekt abgelegt, damit ein neuer Rechner nicht aus dem
# Gedaechtnis eingerichtet wird. Holt den Pruefkern in der im Pruefprofil
# festgehaltenen Fassung, richtet ihn ein und setzt den lokalen Git-Haken.
#
# Der Git-Haken ist eine Bequemlichkeit. Er wird nicht mit dem Repositorium
# uebertragen und ist deshalb keine uebertragbare Absicherung. Die dauerhafte
# Absicherung ist der Aufruf von pruefen.sh dort, wo die Veroeffentlichung
# entsteht.
#
# Aufruf:  ./einrichten.sh
set -u
projekt=$(cd "$(dirname "$0")" && pwd)
cd "$projekt" || exit 1

echo "Pruefung einrichten fuer $(basename "$projekt")"
echo ""

[ -f "$projekt/_pruefprofil.json" ] || { echo "ABBRUCH: _pruefprofil.json fehlt."; exit 2; }
soll=$(python3 -c "import json;print(json.load(open('_pruefprofil.json'))['pruefer']['fassung'])" 2>/dev/null) || {
  echo "ABBRUCH: das Pruefprofil nennt keine Pruefer-Fassung."; exit 2; }
echo "Das Profil verlangt den Pruefkern in der Fassung $soll"

echo ""
echo "1 Pruefkern holen"
if [ -f "$projekt/.gitmodules" ] && grep -q "_pruefer" "$projekt/.gitmodules" 2>/dev/null; then
  git submodule update --init _pruefer || { echo "ABBRUCH: das Submodul liess sich nicht holen."; exit 2; }
  kern="$projekt/_pruefer"
elif [ -d "$projekt/../webpruefer" ]; then
  kern=$(cd "$projekt/../webpruefer" && pwd)
  echo "  Nachbarordner benutzt: $kern"
else
  echo "ABBRUCH: kein Pruefkern gefunden."
  echo "  Entweder das Submodul einbinden:  git submodule update --init _pruefer"
  echo "  oder den Kern daneben klonen:     git clone <webpruefer-Adresse> ../webpruefer"
  exit 2
fi

echo ""
echo "2 Kern einrichten"
if [ -x "$kern/einrichten.sh" ]; then
  "$kern/einrichten.sh" || echo "  Hinweis: die Einrichtung des Kerns war nicht vollstaendig, siehe oben."
fi

echo ""
echo "3 Lokalen Git-Haken setzen"
if [ -d "$projekt/.git" ]; then
  cp "$kern/vorlage/pre-push" "$projekt/.git/hooks/pre-push" && chmod +x "$projekt/.git/hooks/pre-push" \
    && echo "  gesetzt: .git/hooks/pre-push (nicht uebertragbar, nur Bequemlichkeit)"
else
  echo "  uebersprungen, hier ist kein .git-Ordner"
fi

echo ""
echo "4 Erste Pruefung"
"$projekt/pruefen.sh"
