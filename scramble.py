"""SCRAMBLE (Konami, 1981) — main Python launcher.

Windows: double-click ``Play Scramble.bat``.
Terminal: ``py scramble.py``; extra options: ``py scramble.py --help``.

Native gameplay, two-player cabinet handling, high-score rankings and authentic
MAME-captured sound are included. Use --artwork bezel for the optional
Konami cabinet front plate, or --debug for development diagnostics.
Frame-perfect MAME parity is not claimed.
"""

from scramble_game import main


if __name__ == "__main__":
    main()
