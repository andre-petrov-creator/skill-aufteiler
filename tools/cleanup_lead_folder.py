#!/usr/bin/env python3
"""
cleanup_lead_folder.py - Bringt einen Lead-/Objektordner in die Soll-Struktur.

Standard ab 2026-06-15 (loest die "Datenmuell-Streuung" im Objektordner):

  <lead>/
  |- Exposé.<ext> · Energieausweis.<ext> · Mietaufstellung.<ext> · Modernisierungsliste.<ext>
  |- Kalkulation_*.xlsx · Aufteiler_*.pdf      (Ergebnisse, falls vorhanden)
  |- README.md · quickcheck.md                 (max. Uebersichts-MDs)
  |- Unterlagen/                               (Original-Material, Bucket b)
  |- Bilder/                                   (Galerie-Fotos - SICHTBAR)
  |- .aufteiler/                               (VERSTECKT: aller Arbeits-/Zwischenkram,
  |                                             inkl. state.json, objektdaten.json,
  |                                             modul-*-output.md, scraper-Dateien, *.py)

Idempotent: beliebig oft aufrufbar. Verschiebt nur, loescht keine Inhalte.
Migriert auch Alt-Ordner (Cloud/ -> .aufteiler/, Cloud/bilder/ -> Bilder/).

state.json + objektdaten.json (Pipeline-Drehscheibe) bleiben im Root, SOLANGE der
Lead aktiv ist (Modul 0 liest state.json nach Modul 1 fuers Supabase-Update). Erst
der FINALE Aufruf mit --final verschiebt auch sie nach .aufteiler/ (von Modul 0 nach
Supabase bzw. vom Orchestrator nach Sequenz-Ende). Bei Wiederaufnahme holt der
Orchestrator state.json/objektdaten.json aus .aufteiler/ zurueck ins Root.

Aufruf:
  python tools/cleanup_lead_folder.py "<lead-ordner-pfad>"            # Zwischen-Cleanup
  python tools/cleanup_lead_folder.py "<lead-ordner-pfad>" --final    # State mitverschieben
  python tools/cleanup_lead_folder.py "<lead-ordner-pfad>" --dry-run
"""
import sys
import os
import shutil
import fnmatch
import subprocess

# --- Was SICHTBAR im Root bleibt ---------------------------------------------
# Schluessel-Dokumente (Basename exakt, beliebige Endung)
KEEP_DOC_BASENAMES = {"Exposé", "Energieausweis", "Mietaufstellung", "Modernisierungsliste"}
# Uebersichts-Markdown (genau diese Namen)
KEEP_EXACT_NAMES = {"README.md", "quickcheck.md"}
# State-Dateien: bleiben im Root, bis der FINALE Cleanup (--final) sie nach
# .aufteiler/ verschiebt. Vorher braucht Modul 0 state.json im Root (Supabase).
KEEP_STATE_NAMES = {"state.json", "objektdaten.json"}
# Ergebnis-Dateien (Glob)
KEEP_GLOBS = ["Kalkulation*.xls*", "Aufteiler_*.pdf"]
# Unterordner, die nie automatisch weggeraeumt werden
KEEP_DIRS = {"Unterlagen", "Bilder", ".aufteiler"}

SAMMEL = ".aufteiler"


def keep_in_root(name: str, final: bool) -> bool:
    base, _ext = os.path.splitext(name)
    if base in KEEP_DOC_BASENAMES:
        return True
    if name in KEEP_EXACT_NAMES:
        return True
    if not final and name in KEEP_STATE_NAMES:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in KEEP_GLOBS)


def unique_dst(dst: str) -> str:
    if not os.path.exists(dst):
        return dst
    base, ext = os.path.splitext(os.path.basename(dst))
    return os.path.join(os.path.dirname(dst), f"{base}_dup{ext}")


def same_path(a: str, b: str) -> bool:
    """Case-insensitiver Pfadvergleich (Windows: Bilder == bilder)."""
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def try_rmdir(path: str):
    """Leeren Ordner entfernen; OneDrive-Lock (PermissionError) ist nicht fatal."""
    try:
        if os.path.isdir(path) and not os.listdir(path):
            os.rmdir(path)
    except OSError:
        pass


def move(src: str, dst: str, actions: list, dry: bool):
    if same_path(src, dst):
        return
    dst = unique_dst(dst)
    actions.append(f"  {os.path.basename(src)}  ->  {os.path.relpath(dst, os.path.dirname(src))}")
    if not dry:
        shutil.move(src, dst)


def main(lead: str, dry: bool, final: bool):
    lead = os.path.abspath(lead)
    if not os.path.isdir(lead):
        print(f"FEHLER: kein Ordner: {lead}")
        sys.exit(1)

    sammel = os.path.join(lead, SAMMEL)
    cloud = os.path.join(lead, "Cloud")
    bilder_ziel = os.path.join(lead, "Bilder")
    actions: list = []

    # 1. Alt-Migration: Cloud/ -> .aufteiler/
    if os.path.isdir(cloud):
        if not os.path.isdir(sammel):
            actions.append("  Cloud/  ->  .aufteiler/")
            if not dry:
                os.rename(cloud, sammel)
        else:
            for f in os.listdir(cloud):
                move(os.path.join(cloud, f), os.path.join(sammel, f), actions, dry)
            if not dry:
                try_rmdir(cloud)

    if not dry:
        os.makedirs(sammel, exist_ok=True)

    # 2. Bilder SICHTBAR machen: .aufteiler/bilder/ oder bilder/ -> Bilder/
    for src_dir in (os.path.join(sammel, "bilder"), os.path.join(lead, "bilder")):
        if os.path.isdir(src_dir) and not same_path(src_dir, bilder_ziel):
            if not dry:
                os.makedirs(bilder_ziel, exist_ok=True)
            for f in os.listdir(src_dir):
                move(os.path.join(src_dir, f), os.path.join(bilder_ziel, f), actions, dry)
            if not dry:
                try_rmdir(src_dir)

    # 3. Root-Arbeitskram (nur Dateien) -> .aufteiler/
    for entry in os.listdir(lead):
        full = os.path.join(lead, entry)
        if os.path.isdir(full):
            continue
        if keep_in_root(entry, final):
            continue
        move(full, os.path.join(sammel, entry), actions, dry)

    # 4. .aufteiler/ verstecken (Windows)
    if not dry and os.name == "nt" and os.path.isdir(sammel):
        subprocess.run(["attrib", "+h", sammel], check=False)

    head = "DRY-RUN (nichts verschoben)" if dry else "AUFGERAEUMT"
    print(f"{head}: {lead}")
    if actions:
        print("\n".join(actions))
    else:
        print("  (bereits sauber - nichts zu tun)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    final = "--final" in sys.argv
    if not args:
        print('Usage: python cleanup_lead_folder.py "<lead-ordner>" [--final] [--dry-run]')
        sys.exit(1)
    main(args[0], dry, final)
