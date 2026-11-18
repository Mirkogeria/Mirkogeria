"""Crea i font ridotti (subset) che le card SVG incorporano.

Si lancia una volta sola, in locale (serve `pip install fonttools brotli`):

    python3 scripts/build_fonts.py JetBrainsMono[wght].ttf

I file sorgente si scaricano da github.com/google/fonts (licenza OFL).
Il risultato finisce in assets/fonts/ e va committato: cosi la GitHub Action
non ha bisogno di nessuna dipendenza.
"""

import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "fonts"

# ASCII stampabile + lettere accentate italiane + i pochi simboli usati nelle card
CHARS = "".join(chr(c) for c in range(0x20, 0x7F)) + "àèéìòùÀÈÉÌÒÙ·•→←↑↓▸▶●○■□█▌▍│─┌┐└┘├┤…✓✗°×"


def save_subset(font: TTFont, name: str) -> None:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt"]
    opts.name_IDs = ["*"]
    sub = subset.Subsetter(opts)
    sub.populate(text=CHARS)
    sub.subset(font)
    path = OUT / f"{name}.woff2"
    font.flavor = "woff2"
    font.save(path)
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} KB")


def main() -> None:
    jetbrains = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for weight, name in ((400, "mono-400"), (700, "mono-700")):
        f = instancer.instantiateVariableFont(TTFont(jetbrains), {"wght": weight})
        save_subset(f, name)


if __name__ == "__main__":
    main()
