import sys
from pathlib import Path

# Make tools/marktdaten-fallback importable as a package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
