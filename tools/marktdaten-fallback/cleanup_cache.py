"""Cache-Cleanup: loescht aelteste Files wenn Soft-Cap 500 MB ueberschritten."""

from pathlib import Path
import sys

CACHE_DIR = Path(__file__).resolve().parent / "cache"
SOFT_CAP_BYTES = 500 * 1024 * 1024


def cache_size_bytes() -> int:
    return sum(f.stat().st_size for f in CACHE_DIR.glob("*") if f.is_file())


def cleanup():
    if not CACHE_DIR.exists():
        print("Cache-Dir existiert nicht — nichts zu tun.")
        return 0
    total = cache_size_bytes()
    print(f"Cache-Groesse: {total / 1024 / 1024:.1f} MB / Soft-Cap {SOFT_CAP_BYTES / 1024 / 1024:.0f} MB")
    if total <= SOFT_CAP_BYTES:
        print("Unter Cap — kein Cleanup noetig.")
        return 0
    files = sorted(CACHE_DIR.glob("*"), key=lambda f: f.stat().st_mtime)
    deleted = 0
    while total > SOFT_CAP_BYTES and files:
        f = files.pop(0)
        sz = f.stat().st_size
        f.unlink()
        total -= sz
        deleted += 1
        print(f"  geloescht: {f.name} ({sz / 1024 / 1024:.1f} MB)")
    print(f"Cleanup done: {deleted} Dateien geloescht, neue Groesse {total / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(cleanup())
