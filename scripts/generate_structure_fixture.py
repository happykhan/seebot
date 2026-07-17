#!/usr/bin/env python3
"""Generate a deterministic, compact protein-backbone PDB fixture."""

from __future__ import annotations

import math
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "fixtures/structures/example.pdb"
RESIDUES = ("ALA", "GLY", "SER", "LEU", "THR", "VAL")


def main() -> None:
    lines = ["HEADER    SYNTHETIC ALPHA-HELIX BACKBONE"]
    serial = 1
    for residue_number in range(1, 21):
        angle = math.radians((residue_number - 1) * 100)
        ca = (2.3 * math.cos(angle), 2.3 * math.sin(angle), 1.5 * (residue_number - 1))
        atoms = (
            ("N", (ca[0] - 0.7, ca[1] - 0.3, ca[2] - 0.5), "N"),
            ("CA", ca, "C"),
            ("C", (ca[0] + 0.7, ca[1] + 0.3, ca[2] + 0.5), "C"),
            ("O", (ca[0] + 1.2, ca[1] + 0.5, ca[2] + 1.1), "O"),
        )
        residue = RESIDUES[(residue_number - 1) % len(RESIDUES)]
        for atom, (x, y, z), element in atoms:
            lines.append(
                f"ATOM  {serial:5d} {atom:^4s} {residue:3s} A{residue_number:4d}    "
                f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {element:>2s}"
            )
            serial += 1
    lines.extend(("TER", "END"))
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
