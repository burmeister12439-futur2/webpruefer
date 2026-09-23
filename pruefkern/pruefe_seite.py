#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefe_seite.py — die statische Pruefung, die am 22.09.2026 gefehlt hat.

Anlass: Bei der Umschaltung auf die Gliederung A bis I stand ein schliessendes
</details> an der falschen Stelle. Die Fragen zu Abschnitt D lagen dadurch in
einem zugeklappten Fenster und waren fuer jeden Leser unsichtbar. Keine unserer
Pruefungen hat das gefunden, weil alle gezaehlt haben. Fuenf <details> zu fuenf
</details>, sechzehn Felder, alle Zahlen richtig. Falsch war die Position.

Der Grundsatz: Eine Zaehlung ist keine Pruefung. Jede Zahl wird deshalb gegen
einen hinterlegten Sollbestand gehalten, nicht gegen sich selbst.

Geprueft wird:
  1 Verschachtelung, mit einem Stapel statt mit einer Summe.
  2 Sichtbarkeit ohne Klick. Kein Antwortfeld und keine Fragen-Ueberschrift im
    geschlossenen <details>, nichts per hidden oder inline-CSS versteckt.
  3 Verdrahtung. Jedes Antwortfeld braucht eindeutige id, eindeutiges
    data-frage und ein label[for] mit Text. Jedes textarea muss ein
    Antwortfeld sein. Jedes andere Eingabeelement muss im Sollbestand als
    Bedienfeld stehen.
  4 Vollstaendigkeit gegen den Sollbestand, je Abschnitt und in der Summe.
  5 Leseblick, Soll gegen Ist, zum Ansehen.
  6 Tote Sprungmarken.
  7 Doppelte Kennungen.

Aufruf:  python3 _werkzeug/pruefe_seite.py [seite] [sollbestand.json]
Rueckgabe: 0 bestanden, 1 Befunde. Nur Standardbibliothek, kein Browser.
Die Browserpruefung ist ein eigenes Werkzeug, siehe _werkzeug/00_AKTUELL.md.
"""
import sys, os, json, re
from html.parser import HTMLParser

LEER = {"area","base","br","col","embed","hr","img","input","link","meta",
        "param","source","track","wbr"}
EINGABE = {"textarea","input","select"}
VERSTECKT_CSS = re.compile(r"(display\s*:\s*none|visibility\s*:\s*hidden)", re.I)


class Seite(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stapel = []
        self.fehler = []
        self.ids = {}
        self.anker = []
        self.abschnitte = []
        self.felder = []      # dicts: tag,zeile,id,frage,abschnitt,fenster,versteckt
        self.bloecke = []     # dicts: zeile,text,abschnitt,fenster
        self.labels = {}      # for -> (zeile, text)
        self._h = None; self._htext = ""
        self._lab = None; self._labtext = ""

    def _fenster(self):
        for tag, z, a in reversed(self.stapel):
            if tag == "details" and "open" not in a:
                return a.get("id") or ("Zeile %d" % z)
        return None

    def _versteckt(self, a):
        """Statisch erkennbares Verstecken am Element oder an einem Vorfahren."""
        ketten = [(a, "am Element selbst")] + \
                 [(at, "<%s> aus Zeile %d" % (t, z)) for t, z, at in reversed(self.stapel)]
        for attrs, wo in ketten:
            if "hidden" in attrs:
                return "hidden-Attribut %s" % wo
            st = attrs.get("style", "")
            if st and VERSTECKT_CSS.search(st):
                return "inline-CSS %s" % wo
        return None

    def _abschnitt(self):
        for tag, z, a in reversed(self.stapel):
            if tag == "section":
                return a.get("id") or ("Zeile %d" % z)
        return "(ausserhalb)"

    def handle_starttag(self, tag, attrs):
        z = self.getpos()[0]
        a = {k: (v if v is not None else "") for k, v in attrs}
        if "id" in a:
            self.ids.setdefault(a["id"], []).append(z)
        if tag == "a" and a.get("href", "").startswith("#") and len(a["href"]) > 1:
            self.anker.append((a["href"][1:], z))
        if tag == "section":
            self.abschnitte.append((a.get("id") or str(z), z))
        if tag == "label":
            self._lab = (a.get("for", ""), z); self._labtext = ""
        if tag in EINGABE:
            self.felder.append({
                "tag": tag, "zeile": z, "id": a.get("id", ""),
                "frage": a.get("data-frage", ""), "abschnitt": self._abschnitt(),
                "fenster": self._fenster(), "versteckt": self._versteckt(a),
                "typ": a.get("type", ""),
            })
        if tag in ("h2", "h3", "h4"):
            self._h = (tag, z, self._fenster(), self._abschnitt()); self._htext = ""
        if tag not in LEER:
            self.stapel.append((tag, z, a))

    def handle_data(self, d):
        if self._h is not None: self._htext += d
        if self._lab is not None: self._labtext += d

    def handle_endtag(self, tag):
        z = self.getpos()[0]
        if self._lab is not None and tag == "label":
            f, lz = self._lab
            if f: self.labels.setdefault(f, (lz, " ".join(self._labtext.split())))
            self._lab = None
        if self._h is not None and tag == self._h[0]:
            name, zeile, fenster, absch = self._h
            t = " ".join(self._htext.split())
            if t.startswith("Fragen zu") or t.startswith("Weitere Fragen zu"):
                self.bloecke.append({"zeile": zeile, "text": t, "abschnitt": absch,
                                     "fenster": fenster})
            elif name == "h2":
                self.bloecke.append({"zeile": zeile, "text": t, "abschnitt": absch,
                                     "fenster": fenster, "h2": True})
            self._h = None
        if tag in LEER: return
        if not self.stapel:
            self.fehler.append("Zeile %d: </%s> ohne oeffnendes Element" % (z, tag)); return
        if self.stapel[-1][0] == tag:
            self.stapel.pop(); return
        for i in range(len(self.stapel) - 1, -1, -1):
            if self.stapel[i][0] == tag:
                offen = ", ".join("<%s> aus Zeile %d" % (t, l) for t, l, _ in self.stapel[i+1:])
                self.fehler.append("Zeile %d: </%s> schliesst, obwohl noch offen ist: %s"
                                   % (z, tag, offen))
                del self.stapel[i:]; return
        self.fehler.append("Zeile %d: </%s> ohne oeffnendes Element" % (z, tag))


def lade_soll(sollpfad, seitenname):
    """Nimmt ein Pruefprofil (mehrere Seiten) oder einen alten Sollbestand (eine Seite).

    Das Profil ist die neue Form: eine Datei je Projekt, darin eine Liste seiten.
    Der alte Sollbestand bleibt lesbar, damit die Ablosung nachweisbar gleichwertig
    laeuft und nicht an der Vergangenheit scheitert.
    """
    with open(sollpfad, encoding="utf-8") as f:
        d = json.load(f)
    if "seiten" not in d:
        return d, "Sollbestand"
    for eintrag in d["seiten"]:
        if os.path.basename(eintrag.get("datei", "")) == os.path.basename(seitenname):
            return eintrag, "Pruefprofil %s" % d.get("projekt", "(ohne Namen)")
    raise SystemExit("Die Seite %s steht nicht im Pruefprofil %s. Entweder gehoert sie nicht\n"
                     "zum geprueften Bestand, oder das Profil ist unvollstaendig. Beides muss\n"
                     "entschieden und nicht uebergangen werden." % (seitenname, sollpfad))


def pruefe(pfad, sollpfad):
    with open(pfad, encoding="utf-8") as f:
        roh = f.read()
    soll, herkunft = lade_soll(sollpfad, pfad)
    s = Seite(); s.feed(roh); s.close()

    befunde = []
    def befund(text, gruppe):
        print("   BEFUND  " + text); befunde.append(gruppe)

    print("=" * 74)
    print("PRUEFUNG  %s   gegen  %s" % (pfad, os.path.basename(sollpfad)))
    print("=" * 74)

    print("\n1 Verschachtelung")
    for f in s.fehler: befund(f, "Verschachtelung")
    for t, z, _ in s.stapel: befund("<%s> aus Zeile %d wird nie geschlossen" % (t, z), "Verschachtelung")
    if not s.fehler and not s.stapel: print("   in Ordnung, der Stapel geht auf")

    bedien_soll = soll.get("bedienfelder", {})
    # Ein Bedienfeld kann auch ein textarea sein, etwa die Eingabe eines
    # Bedienablaufs. Es ist dann kein Antwortfeld und braucht kein data-frage.
    # Sichtbarkeit im Ausgangszustand und richtiges Verhalten nach einer
    # Interaktion sind zweierlei; das Verhalten prueft die Browserpruefung.
    antwort = [f for f in s.felder if f["tag"] == "textarea" and f["id"] not in bedien_soll]

    print("\n2 Sichtbarkeit ohne Klick")
    ok2 = True
    for f in antwort:
        if f["fenster"]:
            befund("Antwortfeld %s in Zeile %d steckt im geschlossenen Fenster „%s“"
                   % (f["id"] or f["frage"] or "(ohne id)", f["zeile"], f["fenster"]), "Sichtbarkeit"); ok2 = False
        if f["versteckt"]:
            befund("Antwortfeld %s in Zeile %d ist versteckt: %s"
                   % (f["id"] or "(ohne id)", f["zeile"], f["versteckt"]), "Sichtbarkeit"); ok2 = False
    for f in s.felder:
        if f["id"] in bedien_soll and (f["fenster"] or f["versteckt"]):
            grund = ("steckt im geschlossenen Fenster „%s“" % f["fenster"]) if f["fenster"] \
                    else ("ist versteckt: %s" % f["versteckt"])
            befund("Bedienfeld %s in Zeile %d %s" % (f["id"], f["zeile"], grund), "Sichtbarkeit"); ok2 = False
    for b in s.bloecke:
        if b.get("h2"): continue
        if b["fenster"]:
            befund("Ueberschrift „%s“ in Zeile %d steckt im geschlossenen Fenster „%s“"
                   % (b["text"], b["zeile"], b["fenster"]), "Sichtbarkeit"); ok2 = False
    if ok2: print("   in Ordnung, %d Antwortfelder, %d Bedienfelder und alle Fragenbloecke sind ohne Klick sichtbar"
                  % (len(antwort), len(bedien_soll)))

    print("\n3 Verdrahtung")
    ok3 = True
    gesehen_id, gesehen_frage = {}, {}
    for f in antwort:
        wo = "Zeile %d" % f["zeile"]
        if not f["id"]:
            befund("Antwortfeld in %s hat keine id" % wo, "Verdrahtung"); ok3 = False
        elif f["id"] in gesehen_id:
            befund("id=\"%s\" in %s ist schon in Zeile %d vergeben" % (f["id"], wo, gesehen_id[f["id"]]), "Verdrahtung"); ok3 = False
        else: gesehen_id[f["id"]] = f["zeile"]
        if not f["frage"]:
            befund("Antwortfeld %s in %s hat kein data-frage und liegt damit ausserhalb der Sammellogik"
                   % (f["id"] or "(ohne id)", wo), "Verdrahtung"); ok3 = False
        elif f["frage"] in gesehen_frage:
            befund("data-frage=\"%s\" in %s ist schon in Zeile %d vergeben" % (f["frage"], wo, gesehen_frage[f["frage"]]), "Verdrahtung"); ok3 = False
        else: gesehen_frage[f["frage"]] = f["zeile"]
        if f["id"]:
            lab = s.labels.get(f["id"])
            if not lab:
                befund("Antwortfeld %s in %s hat kein label[for=\"%s\"]. Die Sammellogik traegt dann die Kennung statt der Frage ein."
                       % (f["id"], wo, f["id"]), "Verdrahtung"); ok3 = False
            elif not lab[1]:
                befund("das label zu %s in Zeile %d ist leer" % (f["id"], lab[0]), "Verdrahtung"); ok3 = False
    for f in s.felder:
        if f["tag"] == "textarea": continue
        if f["tag"] == "input" and f["typ"].lower() in ("hidden", "submit", "button"): continue
        if f["id"] not in bedien_soll:
            befund("%s %s in Zeile %d ist weder Antwortfeld noch im Sollbestand als Bedienfeld gefuehrt"
                   % (f["tag"], f["id"] or "(ohne id)", f["zeile"]), "Verdrahtung"); ok3 = False
    if ok3: print("   in Ordnung, alle %d Antwortfelder haben eindeutige id, eindeutiges data-frage und ein Label" % len(antwort))

    print("\n4 Vollstaendigkeit gegen den Sollbestand")
    ist_f, ist_b = {}, {}
    for f in antwort:
        ist_f[f["abschnitt"]] = ist_f.get(f["abschnitt"], 0) + 1
    for b in s.bloecke:
        if b.get("h2"): continue
        ist_b[b["abschnitt"]] = ist_b.get(b["abschnitt"], 0) + 1
    sf = soll["antwortfelder_je_abschnitt"]; sb = soll.get("fragenbloecke_je_abschnitt", {})
    ok4 = True
    for absch in sorted(set(list(sf) + list(ist_f))):
        s_ = sf.get(absch); i_ = ist_f.get(absch, 0)
        if s_ is None:
            befund("Abschnitt %s hat %d Antwortfelder, steht aber nicht im Sollbestand" % (absch, i_), "Vollstaendigkeit"); ok4 = False
        elif s_ != i_:
            befund("Abschnitt %s: Soll %d Antwortfelder, gefunden %d" % (absch, s_, i_), "Vollstaendigkeit"); ok4 = False
    for absch in sorted(set(list(sb) + list(ist_b))):
        s_ = sb.get(absch); i_ = ist_b.get(absch, 0)
        if s_ is None:
            befund("Abschnitt %s hat %d Fragenbloecke, steht aber nicht im Sollbestand" % (absch, i_), "Vollstaendigkeit"); ok4 = False
        elif s_ != i_:
            befund("Abschnitt %s: Soll %d Fragenbloecke, gefunden %d" % (absch, s_, i_), "Vollstaendigkeit"); ok4 = False
    gesamt = len(antwort)
    if gesamt != soll["antwortfelder_gesamt"]:
        befund("Summe: Soll %d Antwortfelder, gefunden %d" % (soll["antwortfelder_gesamt"], gesamt), "Vollstaendigkeit"); ok4 = False
    if ok4: print("   in Ordnung, %d Antwortfelder, je Abschnitt wie hinterlegt" % gesamt)

    print("\n5 Leseblick, Soll gegen Ist")
    print("   %-8s %-44s %-9s %-9s" % ("Abschn.", "Ueberschrift", "Felder", "Bloecke"))
    h2 = {b["abschnitt"]: b["text"] for b in s.bloecke if b.get("h2") and not b["fenster"]}
    for absch, _z in s.abschnitte:
        if absch not in sf and absch not in ist_f and absch not in ist_b: 
            print("   %-8s %-44s %-9s %-9s" % (absch, h2.get(absch, "")[:44], "-", "-")); continue
        print("   %-8s %-44s %-9s %-9s" % (
            absch, h2.get(absch, "")[:44],
            "%d von %s" % (ist_f.get(absch, 0), sf.get(absch, "?")),
            "%d von %s" % (ist_b.get(absch, 0), sb.get(absch, "?"))))

    print("\n6 Tote Sprungmarken")
    tot = sorted({n for n, z in s.anker if n not in s.ids})
    for n in tot: befund("#%s zeigt auf nichts" % n, "Sprungmarken")
    if not tot: print("   in Ordnung, alle %d Sprungmarken finden ihr Ziel" % len(s.anker))

    print("\n7 Doppelte Kennungen")
    dop = {k: v for k, v in s.ids.items() if len(v) > 1}
    for k, v in sorted(dop.items()):
        befund("id=\"%s\" steht in den Zeilen %s" % (k, ", ".join(map(str, v))), "Kennungen")
    if not dop: print("   in Ordnung, alle %d Kennungen sind eindeutig" % len(s.ids))

    print()
    if befunde:
        gr = []
        for g in befunde:
            if g not in gr: gr.append(g)
        print("NICHT BESTANDEN: %d Befunde in %s" % (len(befunde), ", ".join(gr)))
        return 1
    print("BESTANDEN")
    return 0


if __name__ == "__main__":
    seite = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    sollp = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sollbestand.json")
    if not os.path.exists(seite):
        print("Seite fehlt: %s" % seite); sys.exit(1)
    if not os.path.exists(sollp):
        print("Sollbestand fehlt: %s" % sollp); sys.exit(1)
    sys.exit(pruefe(seite, sollp))
