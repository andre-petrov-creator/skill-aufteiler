# skill-aufteiler

Aufteiler-Analyse für Mehrfamilienhäuser (NRW): Orchestrator + Modul 1 bis 6, PDF-Export, Marktdaten-Fallback.
Ohne Modul 0 (Akquise-Mailpipeline), das braucht man für die Analyse nicht.

Marktdaten (Mietspiegel NRW, Grundstücksmarktbericht) liest der Skill zuerst aus einer privaten Notion-Datenbank des Autors.
Ohne Zugriff greift der Fallback auf offizielle Quellen (BORIS NRW, Stadt-Webseiten).

## Installation (mit automatischen Updates)
Den folgenden Text komplett in Claude Code einfügen und Enter drücken:

```
Richte mir die Claude-Code-Skills von André Petrov ein: Aufteiler, Exposé-Builder, Claude-Code-Blueprint. Quelle sind drei öffentliche GitHub-Repos, kein Login nötig. Die Skills sollen sich bei jedem Start von Claude Code automatisch auf den neuesten Stand ziehen. Arbeite alles selbst ab, ohne Rückfragen. Stopp nur, wenn ein Schritt fehlschlägt, und sag mir dann genau, was los ist.

1. Klonen. Ist der Zielordner schon ein Git-Klon desselben Repos: dort stattdessen `git pull --ff-only`. Existiert er mit anderem Inhalt: nichts überschreiben, abbrechen und melden.
   - https://github.com/andre-petrov-creator/skill-aufteiler -> C:\meine-projekte\Immobilien\Aufteiler
   - https://github.com/andre-petrov-creator/skill-expose-builder -> C:\meine-projekte\skill-repos\skill-expose-builder
   - https://github.com/andre-petrov-creator/skill-claude-code-blueprint -> C:\meine-projekte\skill-repos\skill-claude-code-blueprint
   Der Aufteiler muss genau unter diesem Pfad liegen, seine Skills rufen dort Skripte auf.

2. Verknüpfen. Für jeden Unterordner in `<Klon>\skills\` eine Verzeichnis-Junction anlegen:
   `%USERPROFILE%\.claude\skills\<Ordnername>` -> `<Klon>\skills\<Ordnername>`
   (PowerShell: `New-Item -ItemType Junction -Path <Ziel> -Target <Quelle>`). Gibt es dort schon einen echten Ordner gleichen Namens: nicht anfassen, melden.

3. Auto-Update. In `%USERPROFILE%\.claude\settings.json` (anlegen, falls nicht vorhanden; vorhandene Einstellungen und Hooks unverändert lassen; als UTF-8 ohne BOM speichern) unter `hooks.SessionStart` diesen Eintrag ergänzen:
   {"hooks": [
     {"type": "command", "timeout": 30, "command": "git -C \"C:/meine-projekte/Immobilien/Aufteiler\" pull --ff-only -q"},
     {"type": "command", "timeout": 30, "command": "git -C \"C:/meine-projekte/skill-repos/skill-expose-builder\" pull --ff-only -q"},
     {"type": "command", "timeout": 30, "command": "git -C \"C:/meine-projekte/skill-repos/skill-claude-code-blueprint\" pull --ff-only -q"}
   ]}

4. Python-Pakete: `python -m pip install openpyxl reportlab`. Fehlt Python: melden, den Rest trotzdem fertig machen.

5. Prüfen und melden: Jede Junction zeigt auf eine vorhandene SKILL.md, settings.json ist gültiges JSON, die drei `git pull`-Befehle laufen fehlerfrei. Dann: „Fertig. Claude Code einmal neu starten."

Mac/Linux: gleiche Struktur unter `~/meine-projekte/...`, Symlinks statt Junctions, Hook-Pfade entsprechend.
```

Dieses Repo ist ein automatisch erzeugter Spiegel. Änderungen nur im Quell-Repo.
