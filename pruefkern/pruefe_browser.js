/* pruefe_browser.js — die Browserpruefung der Landkarte.
 *
 * Ergaenzt pruefe_seite.py um alles, was erst im laufenden Browser sichtbar
 * wird: Konsolenfehler, berechnete Sichtbarkeit (auch Verstecken per
 * CSS-Klasse), die mobile Breite, die vier Diagramme, den Quellen-Explorer
 * und die Sammelleiste.
 *
 * Braucht Playwright und laeuft deshalb dort, wo Playwright liegt, nicht auf
 * dem Rechner. Ergebnis ist ein Pruefprotokoll mit dem SHA-256 der geprueften
 * Seite. Der Push-Haken laesst nur durch, was ein Protokoll zu genau diesem
 * Stand hat. Eine Aenderung an der Seite macht das Protokoll damit ungueltig,
 * statt es still veralten zu lassen.
 *
 * Aufruf:  node pruefe_browser.js <seite.html> [protokoll.json]
 * Rueckgabe: 0 bestanden, 1 Befunde.
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { chromium } = require(process.env.PW || 'playwright');

const seite = process.argv[2];
const protokoll = process.argv[3] || null;
if (!seite || !fs.existsSync(seite)) { console.error('Seite fehlt: ' + seite); process.exit(1); }
const sha = crypto.createHash('sha256').update(fs.readFileSync(seite)).digest('hex');
// Der Pruefer haelt auch seinen eigenen SHA fest. Sonst bliebe ein altes gruenes
// Protokoll gueltig, waehrend sich der Pruefer darunter geaendert hat.
const pruefer_sha = crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex');

const befunde = [];
const zeile = (s) => console.log(s);
const befund = (s) => { console.log('   BEFUND  ' + s); befunde.push(s); };

(async () => {
  const browser = await chromium.launch();
  const seiteUrl = 'file://' + path.resolve(seite);

  // --- 1 Konsole und Skriptfehler -------------------------------------
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const konsole = [];
  page.on('pageerror', e => konsole.push('Skriptfehler: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') konsole.push('Konsole: ' + m.text()); });
  await page.goto(seiteUrl, { waitUntil: 'load' });
  await page.waitForTimeout(1200);

  zeile('=' .repeat(74));
  zeile('BROWSERPRUEFUNG  ' + seite);
  zeile('SHA-256 Seite    ' + sha);
  zeile('SHA-256 Pruefer  ' + pruefer_sha);
  zeile('='.repeat(74));

  zeile('\n1 Konsole und Skriptfehler');
  konsole.forEach(befund);
  if (!konsole.length) zeile('   in Ordnung, keine Fehler in der Konsole');

  // --- 2 Berechnete Sichtbarkeit --------------------------------------
  zeile('\n2 Berechnete Sichtbarkeit der Antwortfelder');
  const sicht = await page.evaluate(() => {
    return [...document.querySelectorAll('textarea[data-frage]')].map(t => {
      const cs = getComputedStyle(t);
      const r = t.getBoundingClientRect();
      const details = t.closest('details');
      return {
        id: t.id, frage: t.getAttribute('data-frage'),
        sichtbar: t.offsetParent !== null && cs.display !== 'none' &&
                  cs.visibility !== 'hidden' && cs.opacity !== '0' &&
                  r.width > 0 && r.height > 0,
        imFenster: !!(details && !details.open),
        breite: Math.round(r.width), hoehe: Math.round(r.height)
      };
    });
  });
  sicht.filter(f => !f.sichtbar).forEach(f =>
    befund('Antwortfeld ' + (f.id || f.frage) + ' ist im Browser nicht sichtbar (' + f.breite + 'x' + f.hoehe + ')'));
  sicht.filter(f => f.imFenster).forEach(f =>
    befund('Antwortfeld ' + (f.id || f.frage) + ' steckt in einem geschlossenen Fenster'));
  if (sicht.every(f => f.sichtbar && !f.imFenster))
    zeile('   in Ordnung, alle ' + sicht.length + ' Antwortfelder sind berechnet sichtbar');

  // --- 3 Diagramme ------------------------------------------------------
  zeile('\n3 Diagramme');
  const charts = await page.evaluate(() => {
    return [...document.querySelectorAll('canvas')].map(c => {
      const r = c.getBoundingClientRect();
      let gemalt = false;
      try {
        const ctx = c.getContext('2d');
        const d = ctx.getImageData(0, 0, c.width, c.height).data;
        for (let i = 3; i < d.length; i += 4 * 97) { if (d[i] !== 0) { gemalt = true; break; } }
      } catch (e) { gemalt = null; }
      return { id: c.id, breite: Math.round(r.width), hoehe: Math.round(r.height), gemalt };
    });
  });
  if (!charts.length) befund('kein einziges Diagramm auf der Seite gefunden');
  charts.forEach(c => {
    if (c.breite < 10 || c.hoehe < 10) befund('Diagramm ' + c.id + ' hat keine Flaeche (' + c.breite + 'x' + c.hoehe + ')');
    else if (c.gemalt === false) befund('Diagramm ' + c.id + ' ist leer, es ist nichts gezeichnet worden');
  });
  if (charts.length && charts.every(c => c.breite >= 10 && c.hoehe >= 10 && c.gemalt !== false))
    zeile('   in Ordnung, ' + charts.length + ' Diagramme gezeichnet: ' + charts.map(c => c.id).join(', '));

  // --- 4 Quellen-Explorer ----------------------------------------------
  zeile('\n4 Quellen-Explorer');
  const ex = await page.evaluate(async () => {
    const tb = document.getElementById('tbody');
    if (!tb) return { fehlt: true };
    const vorher = tb.querySelectorAll('tr').length;
    const q = document.getElementById('q');
    if (!q) return { vorher, ohneSuche: true };
    q.value = 'zzzqqqxyz';
    q.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 400));
    const leer = tb.querySelectorAll('tr').length;
    q.value = '';
    q.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 400));
    const zurueck = tb.querySelectorAll('tr').length;
    return { vorher, leer, zurueck };
  });
  if (ex.fehlt) befund('der Quellen-Explorer hat keine Tabelle #tbody');
  else if (ex.ohneSuche) befund('der Quellen-Explorer hat kein Suchfeld #q');
  else {
    if (!ex.vorher) befund('der Quellen-Explorer zeigt keine einzige Zeile');
    if (ex.leer >= ex.vorher) befund('die Suche filtert nicht: ' + ex.vorher + ' Zeilen vorher, ' + ex.leer + ' bei einem Suchwort ohne Treffer');
    if (ex.zurueck !== ex.vorher) befund('nach dem Leeren der Suche stehen ' + ex.zurueck + ' statt ' + ex.vorher + ' Zeilen');
    if (ex.vorher && ex.leer < ex.vorher && ex.zurueck === ex.vorher)
      zeile('   in Ordnung, ' + ex.vorher + ' Zeilen, Suche filtert auf ' + ex.leer + ' und stellt wieder her');
  }

  // --- 5 Sammelleiste ---------------------------------------------------
  zeile('\n5 Sammelleiste');
  const sam = await page.evaluate(async () => {
    const t = document.querySelector('textarea[data-frage]');
    const bar = document.getElementById('sammeln');
    const z = document.getElementById('sammelzahl');
    if (!t || !bar || !z) return { fehlt: true, t: !!t, bar: !!bar, z: !!z };
    const vorher = bar.className;
    t.value = 'Pruefeingabe';
    t.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 200));
    const an = bar.classList.contains('an');
    const text = z.textContent;
    t.value = '';
    t.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 200));
    return { vorher, an, text, aus: !bar.classList.contains('an') };
  });
  if (sam.fehlt) befund('Sammelleiste unvollstaendig: Feld ' + sam.t + ', Leiste ' + sam.bar + ', Zaehler ' + sam.z);
  else {
    if (!sam.an) befund('die Sammelleiste geht bei einer Eingabe nicht an');
    if (!/1 Antwort/.test(sam.text)) befund('der Zaehler zeigt „' + sam.text + '“ statt „1 Antwort“');
    if (!sam.aus) befund('die Sammelleiste geht nach dem Leeren nicht wieder aus');
    if (sam.an && /1 Antwort/.test(sam.text) && sam.aus)
      zeile('   in Ordnung, Leiste schaltet an und aus, Zaehler meldet „' + sam.text + '“');
  }

  // --- 6 Mobile Breite ---------------------------------------------------
  zeile('\n6 Mobile Breite, 390 Pixel');
  const mobil = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const m = await mobil.newPage();
  await m.goto(seiteUrl, { waitUntil: 'load' });
  await m.waitForTimeout(900);
  const ueber = await m.evaluate(() => {
    const w = document.documentElement.clientWidth;
    // Ein Element, das in einem seitlich scrollbaren Kasten steckt, darf breiter
    // sein als der Schirm. Das ist bei der Quellentabelle Absicht. Gemeldet wird
    // nur, was ohne solchen Kasten hinausragt und damit die Seite selbst schiebt.
    // Ein Element, das in einem seitlich scrollbaren Kasten steckt, darf breiter
    // sein als der Schirm. Das ist bei der Quellentabelle Absicht, sie laesst
    // sich im Kasten schieben. Zulaessig sind deshalb nur auto und scroll.
    // overflow-x: hidden gilt nicht als Ausnahme, von Klaus am 23.09.2026
    // gesetzt: es schneidet den Inhalt ab, ohne eine bedienbare Scrollmoeglich-
    // keit zu geben. Was dort hinausragt, ist fuer den Leser schlicht weg.
    const imKasten = (e) => {
      for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
        const ox = getComputedStyle(p).overflowX;
        if (ox === 'auto' || ox === 'scroll') return true;
      }
      return false;
    };
    const raus = [...document.querySelectorAll('body *')].filter(e => {
      const r = e.getBoundingClientRect();
      return r.width > 0 && r.right > w + 2 && !imKasten(e);
    }).slice(0, 8).map(e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
        (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : '') +
        ' bis ' + Math.round(e.getBoundingClientRect().right) + 'px');
    return { w, scroll: document.documentElement.scrollWidth, raus };
  });
  if (ueber.scroll > ueber.w + 2) befund('die Seite ist bei 390px ' + ueber.scroll + 'px breit und laesst sich seitlich schieben');
  ueber.raus.forEach(r => befund('ragt bei 390px hinaus: ' + r));
  if (ueber.scroll <= ueber.w + 2 && !ueber.raus.length)
    zeile('   in Ordnung, kein seitliches Schieben, nichts ragt hinaus');

  await browser.close();

  zeile('');
  const ergebnis = befunde.length ? 'nicht bestanden' : 'bestanden';
  zeile(befunde.length ? ('NICHT BESTANDEN: ' + befunde.length + ' Befunde') : 'BESTANDEN');

  if (protokoll) {
    fs.writeFileSync(protokoll, JSON.stringify({
      _zweck: 'Pruefprotokoll der Browserpruefung. Der Push-Haken vergleicht sha256 mit der Seite und pruefer_sha256 mit pruefe_browser.js. Aendert sich eines von beiden, wird dieses Protokoll ungueltig und die Browserpruefung muss neu laufen.',
      seite: path.basename(seite), sha256: sha, pruefer_sha256: pruefer_sha, ergebnis: ergebnis,
      befunde: befunde, zeitpunkt: new Date().toISOString(),
      werkzeug: 'pruefe_browser.js'
    }, null, 1) + '\n', 'utf-8');
    zeile('Protokoll geschrieben: ' + protokoll);
  }
  process.exit(befunde.length ? 1 : 0);
})();
