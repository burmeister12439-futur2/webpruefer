# webpruefer · der gemeinsame Prüfkern

**Stand:** 23.09.2026

Ein Prüfkern für alle Webprojekte von Klaus Burmeister. Der Kern kennt kein
Projekt. Jedes Projekt hält in seinem eigenen `_pruefprofil.json` fest, was
geprüft wird und mit welcher Fassung des Kerns.

## Warum es das gibt

Am 22.09.2026 stand in der GRUNDRISSE-Landkarte ein schließendes `</details>`
an der falschen Stelle. Die Fragen zu Abschnitt D lagen dadurch in einem
zugeklappten Fenster und waren für jeden Leser unsichtbar. Der Fehler stand
einen Tag live und ist von keiner Prüfung gefunden worden, sondern von einer
Leserin.

Der Grund: Alle Prüfungen haben gezählt. Fünf `<details>` zu fünf `</details>`,
sechzehn Felder. Die Zahlen stimmten, die Position war falsch.

**Der Grundsatz: Eine Zählung ist keine Prüfung.** Jede Zahl wird gegen einen
hinterlegten Sollbestand gehalten, nicht gegen sich selbst.

## Aufbau

| Teil | Wofür |
|---|---|
| `pruefkern/pruefen.py` | Der Ablauf. Liest das Profil, ruft die Prüfungen je Seite. |
| `pruefkern/pruefe_seite.py` | Statisch: Verschachtelung, Sichtbarkeit ohne Klick, Verdrahtung, Vollständigkeit gegen den Sollbestand, Leseblick, tote Sprungmarken, doppelte Kennungen. |
| `pruefkern/pruefe_browser.js` | Im Browser: Konsole, berechnete Sichtbarkeit, Diagramme, Explorer, Sammelleiste, mobile Breite. Braucht Playwright. |
| `pruefkern/pruefe_protokoll.py` | Bindet das Browserprotokoll an Seite und Prüfer, über zwei SHA-256. |
| `pruefkern/gegenproben.py` | Beschädigt eine Seite absichtlich und weist nach, dass die Prüfung anschlägt. |
| `vorlage/` | Was ein Projekt bekommt: `pruefen.sh`, `_pruefprofil.json`, `pre-push`. |

## Wie ein Projekt den Kern findet

Kein fest verdrahteter persönlicher Pfad. `pruefen.sh` sucht in dieser
Reihenfolge:

1. die Umgebungsvariable `WEBPRUEFER`
2. `_pruefer` im Projekt, als Submodul oder Klon
3. `webpruefer` als Nachbarordner neben dem Projekt

Wird der Kern nicht gefunden oder trägt er eine andere Fassung als das Profil
erwartet, bricht `pruefen.sh` laut ab und nennt die Abhilfe. Keine stillen
Ausnahmen, kein Durchwinken.

## Wie ein Projekt seine Prüferfassung festhält

Im Profil unter `pruefer.fassung` stehen die ersten zwölf Zeichen des
Kern-Commits. `pruefen.sh` vergleicht sie mit dem vorgefundenen Kern. Eine
neue Fassung wird bewusst eingetragen, nicht nebenbei übernommen.

## Einrichtung auf einem neuen Rechner

Im Prüfkern:

```
./einrichten.sh
```

Das installiert die festgenagelten Abhängigkeiten aus `package-lock.json`
(Playwright 1.56.0, keine unbestimmte globale Installation) und lädt den
Chromium Headless Shell, rund 320 MB. Die Browserablage bleibt am Standardort
des Systems, unter macOS `~/Library/Caches/ms-playwright`, unter Linux
`~/.cache/ms-playwright`. Sie gehört nicht ins Repositorium.

Unter Linux fehlen dem heruntergeladenen Browser noch Systembibliotheken.
Playwright nennt den Befehl selbst, er braucht Verwaltungsrechte:

```
sudo npx playwright install-deps
```

Unter macOS ist das nicht nötig.

In einem Projekt, das den Kern benutzt:

```
./einrichten.sh
```

Das holt den Kern in der Fassung, die das Prüfprofil verlangt, richtet ihn
ein, setzt den lokalen Git-Haken und lässt einmal prüfen. Ist der Kern als
Submodul eingebunden, genügt auf einem neuen Rechner:

```
git submodule update --init
```

## Der Haken ist nicht die Absicherung

Ein lokaler `pre-push` wird nicht mit dem Repositorium übertragen. Er ist eine
Bequemlichkeit für den täglichen Betrieb. Die dauerhafte Absicherung ist der
Aufruf von `pruefen.sh` im Upload- oder Release-Schritt des jeweiligen
Projekts, dort wo die Veröffentlichung tatsächlich entsteht.
