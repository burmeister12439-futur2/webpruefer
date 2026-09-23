#!/bin/sh
# einrichten.sh — richtet den Pruefkern auf einem neuen Rechner ein.
#
# Versioniert, damit ein neuer Rechner nicht aus dem Gedaechtnis eingerichtet
# wird. Installiert die festgenagelten Abhaengigkeiten und den Browser, den die
# Browserpruefung braucht. Aendert nichts an einem Projekt.
#
# Aufruf:  ./einrichten.sh
set -u
cd "$(dirname "$0")" || exit 1

echo "Pruefkern einrichten in $(pwd)"
echo ""

command -v node >/dev/null 2>&1 || { echo "ABBRUCH: node fehlt. Bitte Node.js installieren."; exit 2; }
command -v npm  >/dev/null 2>&1 || { echo "ABBRUCH: npm fehlt. Bitte Node.js installieren."; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "ABBRUCH: python3 fehlt."; exit 2; }
echo "node $(node -v), npm $(npm -v), $(python3 -V)"

echo ""
echo "1 Abhaengigkeiten aus package-lock.json, feste Fassung, nichts Unbestimmtes"
npm ci --no-audit --no-fund || { echo "ABBRUCH: npm ci ist fehlgeschlagen."; exit 2; }

echo ""
echo "2 Browser: nur der Chromium Headless Shell, rund 320 MB"
echo "  Ablage: der Standardort des Systems, nicht dieses Repositorium."
echo "  macOS:  ~/Library/Caches/ms-playwright"
echo "  Linux:  ~/.cache/ms-playwright"
npx playwright install chromium --only-shell
rc=$?
if [ $rc -ne 0 ]; then
  echo ""
  echo "Der Browser ist heruntergeladen, laeuft aber auf diesem System noch nicht."
  echo "Unter Linux fehlen dafuer Systembibliotheken. Playwright nennt den Befehl"
  echo "selbst, er braucht Verwaltungsrechte:"
  echo "    sudo npx playwright install-deps"
  echo "Unter macOS ist das nicht noetig."
  echo "Bis dahin laeuft die Browserpruefung nur dort, wo ein lauffaehiger Browser liegt."
fi

echo ""
echo "3 Probe"
node -e "require('playwright');console.log('  playwright '+require('./node_modules/playwright/package.json').version+' ist geladen')" || exit 2
echo ""
echo "Fertig. Fassung dieses Kerns: $(git rev-parse --short=12 HEAD 2>/dev/null || echo '(keine Versionsgeschichte)')"
