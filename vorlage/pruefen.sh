#!/bin/sh
# pruefen.sh — der Anker im Projekt. Liegt im Projekt, nicht im Pruefkern.
#
# Findet den gemeinsamen Pruefkern, kontrolliert seine Fassung gegen die im
# Pruefprofil festgehaltene, und fuehrt die Pruefungen aus. Aufrufbar von Hand,
# vom Git-Haken, von einem Upload-Schritt oder von einer Fremdpruefung.
#
# Kein fest verdrahteter persoenlicher Pfad. Gesucht wird in dieser Reihenfolge:
#   1 die Umgebungsvariable WEBPRUEFER
#   2 ein Unterordner _pruefer im Projekt (Submodul oder Klon)
#   3 ein Nachbarordner webpruefer neben dem Projekt
# Wird er nicht gefunden oder stimmt seine Fassung nicht, bricht dieses Skript
# laut ab und sagt, was zu tun ist. Keine stillen Ausnahmen.
#
# Rueckgabe: 0 bestanden, 1 Befunde, 2 Kern fehlt oder Fassung falsch.

set -u
projekt=$(cd "$(dirname "$0")" && pwd)
profil="$projekt/_pruefprofil.json"

abbruch() {
  echo ""
  echo "ABBRUCH: $1"
  echo ""
  shift
  for zeile in "$@"; do echo "  $zeile"; done
  echo ""
  exit 2
}

[ -f "$profil" ] || abbruch "Im Projekt fehlt _pruefprofil.json." \
  "Ohne Profil ist nicht bekannt, was geprueft werden soll." \
  "Eine Vorlage liegt im Pruefkern unter vorlage/_pruefprofil.json."

kern=""
for kandidat in "${WEBPRUEFER:-}" "$projekt/_pruefer" "$projekt/../webpruefer"; do
  [ -n "$kandidat" ] || continue
  if [ -f "$kandidat/pruefkern/pruefe_seite.py" ]; then
    kern=$(cd "$kandidat" && pwd)
    break
  fi
done

[ -n "$kern" ] || abbruch "Der gemeinsame Pruefkern wurde nicht gefunden." \
  "Gesucht wurde in: \$WEBPRUEFER, ./_pruefer, ../webpruefer" \
  "Abhilfe, eine der drei:" \
  "  git submodule update --init _pruefer" \
  "  git clone <webpruefer-Adresse> ../webpruefer" \
  "  WEBPRUEFER=/pfad/zum/webpruefer $0"

soll_fassung=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('pruefer',{}).get('fassung',''))" "$profil")
ist_fassung=$(cd "$kern" && git rev-parse --short=12 HEAD 2>/dev/null || echo "")

if [ -z "$soll_fassung" ]; then
  abbruch "Das Pruefprofil nennt keine Pruefer-Fassung." \
    "Jedes Projekt haelt fest, mit welcher Fassung es geprueft wird." \
    "Eintragen unter pruefer.fassung, hier waere das: $ist_fassung"
fi
if [ -z "$ist_fassung" ]; then
  abbruch "Der Pruefkern in $kern hat keine Versionsgeschichte." \
    "Er muss ein Klon des webpruefer-Repositoriums sein, keine lose Kopie."
fi
if [ "$soll_fassung" != "$ist_fassung" ]; then
  abbruch "Der Pruefkern hat eine andere Fassung als das Projekt erwartet." \
    "Profil erwartet: $soll_fassung" \
    "Vorgefunden:     $ist_fassung" \
    "Entweder den Kern auf die erwartete Fassung stellen," \
    "oder das Profil bewusst auf die neue Fassung heben und das begruenden."
fi

echo "Pruefkern: $kern  Fassung $ist_fassung"
exec python3 "$kern/pruefkern/pruefen.py" "$projekt" "$profil"
