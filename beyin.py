"""Portable SourceNest entry point; Python 3.11 or newer."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from beyin import main

if __name__ == "__main__":
    main()
