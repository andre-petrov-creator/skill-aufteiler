# skill-aufteiler

Aufteiler-Analyse für Mehrfamilienhäuser (NRW): Orchestrator + Modul 1 bis 6, PDF-Export, Marktdaten-Fallback.
Ohne Modul 0 (Akquise-Mailpipeline), das braucht man für die Analyse nicht.

## Installation (automatische Updates)
In Claude Code:

    /plugin marketplace add andre-petrov-creator/skill-aufteiler
    /plugin install aufteiler@skill-aufteiler

Danach unter `/plugin` → Marketplaces → `skill-aufteiler` das **Auto-Update einschalten**.

## Voraussetzungen
- Python 3 mit `pip install openpyxl reportlab`
- Die Skills rufen Skripte unter `tools/` und die Excel-Vorlage `template/` dieses Repos auf.
  Die Pfade in den SKILL.md gehen vom Projekt-Wurzelverzeichnis aus. Klone dieses Repo daher zusätzlich nach
  `C:\meine-projekte\Immobilien\Aufteiler\` oder passe die Pfade an.
- Marktdaten (Mietspiegel NRW, Grundstücksmarktbericht) liest der Skill zuerst aus einer privaten Notion-Datenbank des Autors.
  Ohne Zugriff greift der Fallback auf offizielle Quellen (BORIS NRW, Stadt-Webseiten).

Dieses Repo ist ein automatisch erzeugter Spiegel. Änderungen nur im Quell-Repo.
