# RND, AfA und Kaufpreisaufteilung — Wissensbasis (DIMBEG)

Quelle: DIMBEG / Nutzungsdauer, Deep-Dive im Immobilien-Club DERIC am 2026-10-15
(Modernisierungsmatrix als Folie, Meeting-Zusammenfassung). DIMBEG erstellt selbst
RND-Gutachten und Kaufpreisaufteilungen. Die Matrix bildet deshalb ab, wie ein Gutachter
tatsächlich Punkte vergibt. Sie ersetzt seit Modul 3 v2.0 die früheren Hausregeln R03/R04
(15/25-Jahres-Stufen).

Gilt für: Modul-3-Berechnung (Sektion 3) UND jede Ersteinschätzung oder Wissensfrage zu
RND/AfA, auch ohne Objekt und ohne State.

============================================================

## 1. Modernisierungsmatrix (Punkte je Gewerk und Alter der Maßnahme)

Alter der Maßnahme = Jahre zwischen Abschluss der Maßnahme und Bewertungsstichtag
(Übergang Nutzen und Lasten).

| Gewerk | Max | < 5 J. | 5 bis < 10 J. | 10 bis < 15 J. | 15 bis 20 J. | > 20 J. |
|---|---|---|---|---|---|---|
| Dacherneuerung inkl. Dämmung | 4 | 4,0 | 3,0 | 2,0 | 1,0 | 0 |
| Wärmedämmung der Außenwände | 4 | 4,0 | 3,0 | 2,0 | 1,0 | 0 |
| Fenster und Außentüren | 2 | 2,0 | 2,0 | 1,0 | 0 | 0 |
| Heizungsanlage | 2 | 2,0 | 2,0 | 1,0 | 0 | 0 |
| Leitungssysteme (Strom, Gas, Wasser, Abwasser) | 2 | 2,0 | 2,0 | 2,0 | 1,0 | 0 |
| Bäder | 2 | 2,0 | 1,0 | 0 | 0 | 0 |
| Innenausbau (Decken, Böden, Treppen) | 2 | 2,0 | 2,0 | 2,0 | 1,0 | 0 |
| Verbesserung der Grundrissgestaltung | 2 | 2,0 | 1,5 | 1,0 | 0,5 | 0 |

Summe Max = 20 Punkte.

**Umfang (Spalten „100 % / 10 %" im Original):** Die Folie nennt je Zelle den Wert bei
100 % und bei 10 % Umfang (z. B. Dach < 5 J.: 4,0 / 0,4). Die 10-%-Werte sind exakt ein
Zehntel. Umsetzung daher linear:

```
punkte_gewerk = matrixwert(gewerk, altersstufe) × umfang_anteil   # umfang_anteil 0,1 … 1,0
```

`umfang_anteil` = Anteil des Bauteils, der erneuert wurde (z. B. 6 von 12 Fenstern = 0,5;
eine von vier Außenwänden gedämmt = 0,25). **Nie pauschal volle Punkte geben**, nur weil ein
Gewerk „gemacht" wurde. Genau das war der Fehler der alten RND-Matrix: Sie hat pauschal Max-Punkte
vergeben, und die Ergebnisse passten am Ende nie zum Gutachten. Umfang je Gewerk konkret erheben
(Zähl-Tabelle in Modul 3, R08). Bleibt er unklar, gilt der niedrigste plausible Anteil.
Diese Lesart ist aus den Zahlen abgeleitet, nicht von DIMBEG schriftlich bestätigt. Bei der
nächsten Gelegenheit bei DIMBEG gegenprüfen.

**Grundriss-Zeile:** Hier stehen keine 100/10-Werte, sondern feste Stufen 100 / 75 / 50 / 25 %
der 2 Punkte nach Alter. Kein zusätzlicher Umfang-Faktor.

**Stufengrenzen:** Die Folie schreibt „5–10" und „10–15" (Grenzwert doppelt). Festlegung:
genau 5, 10, 15 Jahre fallen in die ältere Stufe; genau 20 Jahre zählt noch zur Stufe
„15 bis 20". Liegt ein Sanierungsjahr unscharf an einer Grenze, ist das eine Weiche
(Modul 3, Sektion 1a).

## 2. Was zählt, was nicht

- **Zählt nicht:** rein optische Maßnahmen (Streichen, Tapeten, neue Küche, neue
  Bodenbeläge ohne Unterbau). Nur echte Erneuerung der Bausubstanz und Technik zählt.
- **Volle Punkte bei Dach und Fassade** nur, wenn komplett durchgeführt. Teilflächen über
  `umfang_anteil`.
- **Fehlende Angabe = 0 Punkte** (R02, nie positiv schätzen).
- **Älter als 20 Jahre = 0 Punkte.** Für den Steuerhebel gut: weniger Punkte, kürzere RND,
  höhere AfA.
- **Kernsanierung** (alles bis auf die Grundmauern neu): Das Gebäude gilt als Quasi-Neubau.
  Die RND startet neu (bis zu 50 Jahre), ein RND-Gutachten ist dann sinnlos. AfA nach
  Neubau-Regeln mit dem Steuerberater klären.

## 3. RND und AfA

- Kürzere RND = höherer jährlicher AfA-Satz (AfA % = 100 / RND).
- Aus den Punkten wird die RND nach dem **amtlichen Modell** berechnet (ImmoWertV 2021
  Anlage 2): `RND = a × Alter² / GND − b × Alter + c × GND`, a/b/c aus Tabelle 3 je
  Punktzahl. Unterhalb des relativen Mindestalters gilt `RND = GND − Alter`. Die RND ist auf
  höchstens 70 % der GND begrenzt. Formel und Tabelle stehen in Modul 3, Sektion 3b.
- **Mindest-RND 12 Jahre** bei Wohnimmobilien (DIMBEG-Praxiswert). Das deckt sich mit dem
  amtlichen Modell: Ein nicht modernisiertes MFH (GND 80) landet ab Alter 80 bei rund 12
  Jahren. Kürzer setzt kein Gutachter an, also rechnet Modul 3 nie unter 12 Jahren.
- **Besonders attraktiv:** energetisch schlechte, wenig modernisierte Altbauten. Dort lässt
  sich oft eine kurze RND nachweisen.
- **Bewertungsstichtag** = Übergang von Nutzen und Lasten (nicht Kaufvertrag, nicht heute).

## 4. Kaufpreisaufteilung und Kohärenz

- Ein Kaufpreisaufteilungs-Gutachten hebt den Gebäudeanteil gegenüber der BMF-Arbeitshilfe
  im Schnitt um rund 34 % (DIMBEG-Erfahrungswert).
- **RND und Kaufpreisaufteilung müssen zusammenpassen** („Orange und Blau müssen passen").
  Ein Gebäude mit sehr kurzer RND ist weitgehend verbraucht. Wer gleichzeitig einen sehr
  hohen Gebäudeanteil ansetzt, liefert dem Finanzamt einen Widerspruch, und dann kippt es
  eher die Aufteilung. Deshalb in jeder Einschätzung RND und Gebäudeanteil nebeneinander
  zeigen und den Widerspruch offen benennen.
- Vor dem Kauf beide Ersteinschätzungen holen: RND und Kaufpreisaufteilung.

## 5. Finanzamt

- **Besichtigung** durch den Gutachter-Dienstleister stärkt die Argumentation deutlich.
  Gutachten ohne Besichtigung sind angreifbar.
- **Einspruch:** DIMBEG stellt kostenlose Einspruchs-Textvorlagen und Rechtsbeihilfe bis
  zum Finanzgericht (Stand Meeting 2026-10-15).
- **15-%-Regel (anschaffungsnahe Herstellungskosten, § 6 Abs. 1 Nr. 1a EStG):**
  Renovierungskosten in den ersten drei Jahren nach Anschaffung bis 15 % der
  Gebäude-Anschaffungskosten (netto) sofort als Werbungskosten absetzbar. Darüber werden
  sie zu Herstellungskosten und nur über die AfA abgeschrieben.

## 6. Risiken (Stand 2026-10-15)

- **Bundesrats-Vorschlag:** RND-Gutachten für Bestandsgebäude abschaffen. Noch kein Gesetz,
  Erfolgsaussicht laut DIMBEG gering. In jeder Einschätzung als Risiko nennen.
- **Empfehlung für Kunden und Investoren:** offene Steuererklärungen für Jahre vor 2026
  zügig einreichen, um das geltende Recht zu sichern.
- Rechtsgrundlage: Nachweis einer kürzeren Nutzungsdauer nach § 7 Abs. 4 Satz 2 EStG, BFH
  IX R 7/23. Eine Vorprüfung ersetzt kein Gutachten, und der Steuerberater gehört vor den Kauf.

## 7. Häufige Fragen (Antwortmuster)

| Frage | Kurzantwort |
|---|---|
| Lohnt sich ein RND-Gutachten? | Ja, wenn die Vorprüfung AfA ≥ 3 % ergibt (RND ≤ 33 J.). Unter 2,5 % meist nicht. |
| Warum bringt eine alte Sanierung nichts? | Über 20 Jahre alte Maßnahmen geben 0 Punkte, die RND bleibt kurz. Das ist gut für die AfA. |
| Neue Küche, frisch gestrichen, zählt das? | Nein, rein optisch. |
| Haus kernsaniert? | Quasi-Neubau, RND-Gutachten sinnlos, Neubau-AfA mit dem Steuerberater klären. |
| Welcher Stichtag? | Übergang von Nutzen und Lasten. |
| Wie viel Reno sofort absetzbar? | Bis 15 % der Gebäude-AK netto in 3 Jahren, darüber über die AfA. |
| Gebäudeanteil hochziehen und RND kurz? | Geht nur, wenn beides zusammenpasst. Sonst kippt das Finanzamt die Aufteilung. |
| Wird das abgeschafft? | Vorschlag des Bundesrats, kein Gesetz. Erklärungen vor 2026 zügig einreichen. |
