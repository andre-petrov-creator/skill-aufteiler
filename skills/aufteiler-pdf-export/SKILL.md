---
name: aufteiler-pdf-export
description: Form-Skill für den PDF-Export von Modul 6 (aufteiler-modul-6-deal-bewertung). Verbindliche reportlab-Layout-Regeln — Spaltenbreiten, Farben, Word-Wrap, KeepTogether, kein Emoji, Hyperlinks. Wird ausschließlich von Modul 6 aufgerufen.
---

# Aufteiler PDF-Export Form-Skill

Dieser Skill ist die **verbindliche Quelle** für PDF-Layout in Modul 5. Wenn ein generiertes PDF gegen eine der hier spezifizierten Regeln verstößt, ist der Skill nicht angewendet worden — neu generieren.

Der Skill ergänzt `aufteiler-modul-5-deal-bewertung`. Modul 5 bleibt für **Inhalt** zuständig (Sektionen, Daten, Workflow). Dieser Skill regelt **Form** (Spaltenbreiten, Farben, Umbrüche, Schriften, Word-Wrap).

---

## 1. Pflicht-Regeln (alle gleichermaßen verbindlich)

### R1 — Word-Wrap statt Overflow

Tabellenzellen mit langem Text MÜSSEN als `Paragraph(text, style)` geschrieben werden, NICHT als nackte Strings. reportlab umbricht Paragraphs automatisch innerhalb der Spaltenbreite. Nackte Strings laufen über.

Falsch: `["1", "BORIS.NRW Bodenrichtwert für Prosperstr. 59 verifizieren", "boris.nrw.de/borisplus", "Notar"]`
Richtig: `["1", Paragraph("BORIS.NRW Bodenrichtwert ...", CELL), Paragraph('<link href="https://boris.nrw.de/borisplus">boris.nrw.de/borisplus</link>', CELL_LINK), Paragraph("Notar", CELL)]`

### R2 — KeepTogether für Tabellen

Jede Tabelle wird in `KeepTogether([heading, intro_paragraph, table, legend])` gewrappt. Lieber leere Restseite als Tabelle, die mitten zwischen zwei Zeilen umgebrochen wird. Ausnahme: Tabellen mit > 25 Zeilen → `LongTable` mit `repeatRows=1`.

### R3 — Spaltenbreiten-Summe = textWidth

Die Summe aller `colWidths` muss exakt der nutzbaren Seitenbreite entsprechen (`A4.width − leftMargin − rightMargin = 17 cm`). Spaltenbreiten in Zentimetern, klare Verteilung. Standardraster:

- 4-Spalten-Tabellen: `1, 8.5, 4, 3.5` cm (Nr, Lange Beschreibung, Quelle/Link, Status)
- 5-Spalten-Tabellen: `5.5, 3.5, 2.5, 2.5, 3` cm
- 2-Spalten Key-Value: `5.5, 11.5` cm

### R4 — Farbpalette

```python
NAVY    = colors.HexColor("#1f2937")  # ungenutzt seit v1.1 (frueher Tabellen-Header)
ACCENT  = colors.HexColor("#0d6efd")  # Akzente, Links
GREEN   = colors.HexColor("#16a34a")  # GO, OK
GREEN_BG= colors.HexColor("#d1fae5")
YELLOW  = colors.HexColor("#eab308")
YELLOW_BG=colors.HexColor("#fef3c7")
ORANGE  = colors.HexColor("#f97316")  # v1.1: Tabellen-Header (vorher NAVY)
ORANGE_BG=colors.HexColor("#ffedd5")
RED     = colors.HexColor("#dc2626")
RED_BG  = colors.HexColor("#fee2e2")
GRAY    = colors.HexColor("#9ca3af")
GRAY_BG = colors.HexColor("#f5f7fa")  # Zebra, Key-Cells
INK     = colors.HexColor("#1a3d6e")  # Headlines (H1/H2/H3)
```

**Anwendungsregel Tabellen-Header (v1.1):**
- `BACKGROUND = ORANGE` (`#f97316`)
- `TEXTCOLOR = white`
- `FONTNAME = Helvetica-Bold`

Gilt für **alle** Tabellen im PDF. INK bleibt für H1/H2/H3-Sektions-Titel im Body. NAVY ist seit v1.1 nicht mehr aktiv im Layout — bleibt nur als Reverenz-Konstante in der Palette.

### R5 — KEINE Emoji-Glyphs

Helvetica/DejaVu Sans haben keine Emoji-Glyphs. Statt 🔴/🟡/🟢/✅/⚠️/🔥 nutze **farbig hinterlegte Status-Zellen** mit Klartext (`PFLICHT`, `OK`, `WARNUNG`, `STOP`).

```python
# Status-Cell-Style:
("BACKGROUND", (col, row), (col, row), RED_BG)
("TEXTCOLOR",  (col, row), (col, row), RED)
("FONTNAME",   (col, row), (col, row), "Helvetica-Bold")
```

### R6 — URLs als klickbare Links

Jede URL als `Paragraph('<link href="...">text</link>', LINK)`. Nie nackt. Wenn URL > Spaltenbreite: linkText kürzen (`boris.nrw.de` statt voller Pfad).

### R7 — Schriftgrößen

| Element | Größe | Font |
|---------|-------|------|
| H1 (Sektion-Titel) | 18 pt | Helvetica-Bold, INK |
| H2 (Unter-Sektion) | 14 pt | Helvetica-Bold, INK |
| H3 (Block-Titel) | 11 pt | Helvetica-Bold, ACCENT |
| Body | 9.5 pt | Helvetica, leading 13 |
| Tabellen-Body | 9 pt | Helvetica, leading 11 |
| Tabellen-Header | 9 pt | Helvetica-Bold |
| Small/Disclaimer | 8 pt | Helvetica, GRAY |

### R8 — Seitenränder + Format

- A4 Hochformat, `leftMargin=2cm, rightMargin=2cm, topMargin=1.8cm, bottomMargin=1.8cm`
- Nutzbar: 17 cm × 25.4 cm
- Footer: Seitenzahl rechts unten + Adresse links unten (`onPage`-Callback)

### R9 — Seiten füllen, nicht splitten

Reihenfolge:
1. **Erst** die Tabelle/Block versuchen, fortlaufend zu rendern (`Spacer 0.3cm` zwischen Blöcken)
2. **Wenn** ein Block nicht mehr passt → ganzer Block auf neue Seite (PageBreak vor `KeepTogether(block)`)
3. Niemals Block in der Mitte splitten

Folgerung: keine `PageBreak()` zwischen jedem Mini-Block. Nur zwischen logischen Sektionen oder wenn ein Block nicht mehr passt.

### R10 — Tabellen-Padding (Lesbarkeit)

```python
("TOPPADDING",    (0,0), (-1,-1), 5),
("BOTTOMPADDING", (0,0), (-1,-1), 5),
("LEFTPADDING",   (0,0), (-1,-1), 5),
("RIGHTPADDING",  (0,0), (-1,-1), 5),
```

Für dichte Tabellen (>10 Zeilen) auf 3 reduzieren.

### R11 — Zebra-Streifen für lange Listen

Tabellen ab 4 Zeilen Body bekommen Zebra:
```python
("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, GRAY_BG])
```

### R12 — Numerische Spalten rechtsbündig

```python
("ALIGN", (col_first_num, 1), (col_last_num, -1), "RIGHT")
```

### R13 — Vertikal-Alignment in Tabellen

```python
("VALIGN", (0,0), (-1,-1), "MIDDLE")  # default
```

Bei Spalten mit unterschiedlich langem Text (Word-Wrap aktiv) → `"TOP"`.

---

## 2. Code-Bausteine (kopieren, anpassen)

### 2.1 Setup

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether, Image,
                                LongTable)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# Farbpalette (siehe R4)
NAVY = colors.HexColor("#1f2937")
INK  = colors.HexColor("#1a3d6e")
ACCENT = colors.HexColor("#0d6efd")
GREEN = colors.HexColor("#16a34a"); GREEN_BG = colors.HexColor("#d1fae5")
YELLOW = colors.HexColor("#eab308"); YELLOW_BG = colors.HexColor("#fef3c7")
ORANGE = colors.HexColor("#f97316"); ORANGE_BG = colors.HexColor("#ffedd5")
RED = colors.HexColor("#dc2626"); RED_BG = colors.HexColor("#fee2e2")
GRAY = colors.HexColor("#9ca3af"); GRAY_BG = colors.HexColor("#f5f7fa")

# Styles
H1   = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=INK, spaceAfter=8)
H2   = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=INK, spaceBefore=10, spaceAfter=6)
H3   = ParagraphStyle("H3", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=ACCENT, spaceBefore=6, spaceAfter=3)
BODY = ParagraphStyle("Body", fontName="Helvetica", fontSize=9.5, leading=13)
CELL = ParagraphStyle("Cell", fontName="Helvetica", fontSize=9, leading=11)
CELL_BOLD = ParagraphStyle("CellBold", parent=CELL, fontName="Helvetica-Bold")
CELL_LINK = ParagraphStyle("CellLink", parent=CELL, textColor=ACCENT)
SMALL = ParagraphStyle("Small", fontName="Helvetica", fontSize=8, leading=10, textColor=GRAY)

# Doc
doc = SimpleDocTemplate(
    pdf_path, pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=1.8*cm, bottomMargin=1.8*cm,
    title=f"Analyse zur Aufteiler-Kalkulation {adresse}",  # v1.1: vorher "Aufteiler-Verdict"
    author="Aufteiler-Skill",
)
TEXT_W = A4[0] - 4*cm  # 17 cm nutzbar
```

### 2.2 Tabelle mit Word-Wrap (Standardvorlage)

```python
def make_todo_table(rows):
    """rows = [(nr, beschreibung, link_text, link_url, status_label, status_color)]"""
    header = [
        Paragraph("Nr", CELL_BOLD),
        Paragraph("Aufgabe", CELL_BOLD),
        Paragraph("Quelle / Tool", CELL_BOLD),
        Paragraph("Priorität", CELL_BOLD),
    ]
    body = [header]
    for nr, beschr, ltxt, lurl, slabel, scolor in rows:
        link_para = Paragraph(f'<link href="{lurl}">{ltxt}</link>', CELL_LINK) if lurl else Paragraph(ltxt, CELL)
        body.append([
            Paragraph(str(nr), CELL),
            Paragraph(beschr, CELL),
            link_para,
            Paragraph(slabel, CELL_BOLD),
        ])
    t = Table(body, colWidths=[1.0*cm, 8.5*cm, 4.0*cm, 3.5*cm], repeatRows=1)
    style = TableStyle([
        # Header (v1.1: Tabellen-Header Orange, vorher NAVY)
        ("BACKGROUND", (0,0), (-1,0), ORANGE),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        # Body
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (0,0), (0,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, GRAY_BG]),
        # Padding
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        # Border
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
    ])
    # Status-Spalte einfärben (R5: kein Emoji, nur Hintergrund)
    for ri, (_, _, _, _, _, scolor) in enumerate(rows, start=1):
        if scolor == "RED":
            style.add("BACKGROUND", (3, ri), (3, ri), RED_BG)
            style.add("TEXTCOLOR", (3, ri), (3, ri), RED)
        elif scolor == "YELLOW":
            style.add("BACKGROUND", (3, ri), (3, ri), YELLOW_BG)
            style.add("TEXTCOLOR", (3, ri), (3, ri), colors.HexColor("#854d0e"))
        elif scolor == "GREEN":
            style.add("BACKGROUND", (3, ri), (3, ri), GREEN_BG)
            style.add("TEXTCOLOR", (3, ri), (3, ri), colors.HexColor("#065f46"))
    t.setStyle(style)
    return t
```

### 2.3 Verdict-Badge (statt Emoji)

```python
def verdict_badge(label, kind="GO"):
    bg = {"GO": GREEN, "GRENZ": YELLOW, "STOP": RED}[kind]
    inner = Paragraph(f'<para alignment="center"><font name="Helvetica-Bold" size="22" color="white">{label}</font></para>', BODY)
    box = Table([[inner]], colWidths=[16*cm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("BOX", (0,0), (-1,-1), 1.5, bg),
    ]))
    return box
```

### 2.4 KeepTogether-Block (Sektion + Tabelle + Legende)

```python
def section_block(heading_text, intro_text, table, legend_text=None):
    parts = [
        Paragraph(heading_text, H1),
        Paragraph(intro_text, BODY),
        Spacer(1, 0.2*cm),
        table,
    ]
    if legend_text:
        parts.append(Spacer(1, 0.2*cm))
        parts.append(Paragraph(legend_text, SMALL))
    return KeepTogether(parts)
```

### 2.5 Footer mit Seitenzahl

```python
def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(2*cm, 1*cm, adresse)
    canvas.drawRightString(A4[0]-2*cm, 1*cm, f"Seite {doc.page}")
    canvas.restoreState()

doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
```

---

## 3. Charts (matplotlib)

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": "#9ca3af",
    "axes.linewidth": 0.5,
})
PALETTE = ["#1f2937", "#0d6efd", "#16a34a", "#eab308", "#f97316", "#dc2626"]
```

- DPI 150
- Standardgröße: `(7.5, 3.8)` Zoll → ergibt im PDF ca. 16 × 8 cm
- Komplexe Charts: `(7.5, 5.5)` Zoll → 16 × 11 cm
- Charts in PDF einbinden: `Image(path, width=16*cm, height=8*cm)`
- Vor Image: `Spacer(1, 0.3*cm)`. Danach: `Spacer(1, 0.3*cm)`
- Chart-Image immer in `KeepTogether` mit dem zugehörigen Heading.

---

## 4. PDF-Aufbau-Reihenfolge (Default Modul 5)

Reihenfolge bleibt dem Modul-5-`<pdf_struktur>`-Block überlassen. Wenn der User in der Anfrage eine **abweichende Reihenfolge** wünscht (z.B. To-Do's nach oben, Modernisierungsliste vorziehen, Szenario-Block hinzufügen), wird die Reihenfolge angepasst — die Layout-Regeln (R1–R13) bleiben unverändert verbindlich.

---

## 5. Self-Check vor `doc.build()`

Vor dem Build durchgehen:

| Check | Erfüllt wenn |
|-------|--------------|
| R1 Word-Wrap | Jeder Tabellen-Cell-Text mit > 30 Zeichen ist Paragraph, nicht String |
| R2 KeepTogether | Jede Tabelle ist in KeepTogether oder LongTable |
| R3 Spaltenbreiten | Σ colWidths == 17 cm (oder 16 cm bei Indent) |
| R4 Farben | Tabellen-Header BG = ORANGE (`#f97316`) + textcolor weiss + Helvetica-Bold; INK Sektions-Titel; Status-BG aus Palette |
| R5 Keine Emojis | grep "🔴|🟢|🟡|✅|⚠️|🔥" im PDF-Skript = leer |
| R6 Links | Alle URLs als `<link href="...">` Paragraph |
| R7 Schriften | H1=18, H2=14, H3=11, Body=9.5, Cell=9, Small=8 |
| R8 Margins | leftMargin=rightMargin=2cm, top=bottom=1.8cm |
| R9 Page-Breaks | PageBreak nur zwischen logischen Sektionen oder vor zu großem Block |
| R10 Padding | TOP/BOTTOM/LEFT/RIGHT-PADDING ≥ 4 |
| R11 Zebra | Listen ab 4 Zeilen mit ROWBACKGROUNDS |
| R12 Zahlen rechts | ALIGN RIGHT auf Zahlen-Spalten |
| R13 VALIGN | TOP bei Word-Wrap, MIDDLE bei kurzen Strings |

Falls **eine** Regel verletzt: PDF nicht ausliefern, neu bauen.

---

## 6. Validierungs-Vorschlag

Nach Build: PDF mit `pdftotext -layout` öffnen oder visuell scrollen. Wenn Text in Tabellen abgeschnitten oder überlappt → R1/R3 verletzt. Neu bauen mit größerer Spalte oder Paragraph-Wrap.

---

## 7. Versionshistorie

| Datum | Änderung |
|-------|----------|
| 2026-05-12 | v1.2 — Migration aus `archive/skill_pdf_export.md` (alt: type/version-Frontmatter) zum Skill-Suite-Namespace `skills/aufteiler-pdf-export/SKILL.md`. Frontmatter angepasst: aus type/version (alt) → Standard-Skill-Frontmatter (name/description). Inhaltliche Regeln R1–R13 unverändert. |
| 2026-05-07 | v1.1 — Tabellen-Header von NAVY (`#1f2937`) auf ORANGE (`#f97316`) umgestellt; R4-Anwendungsregel ergänzt; Code-Baustein 2.2 aktualisiert (Plan: `plans/2026-05-07-modul5-pdf-export-anpassung.md`) |
| 2026-04-27 | v1.0 — initiale Skill-Datei aus Layout-Problemen Prosperstr. 59 (Spalten-Overflow, Emoji-Glyphs, mittige Tabellen-Splits) abgeleitet |
