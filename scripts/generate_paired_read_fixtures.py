#!/usr/bin/env python3
"""Generate deterministic paired FASTQ fixtures with enough coverage for assemblers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = {
    1: ROOT / "fixtures/core/reads_R1.fastq",
    2: ROOT / "fixtures/core/reads_R2.fastq",
}


def _lcg(seed: int):
    value = seed
    while True:
        value = (1_664_525 * value + 1_013_904_223) & 0xFFFFFFFF
        yield value


def _reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def main() -> None:
    values = _lcg(470)
    genome = "".join("ACGT"[(next(values) >> 16) % 4] for _ in range(800))
    starts = [(next(values) >> 8) % (len(genome) - 250) for _ in range(160)]

    for side, output in OUTPUTS.items():
        records: list[str] = []
        for index, start in enumerate(starts, start=1):
            fragment = genome[start : start + 250]
            sequence = fragment[:100] if side == 1 else _reverse_complement(fragment[-100:])
            records.extend(
                [
                    f"@synthetic_assembly_pair_{index}/{side}",
                    sequence,
                    "+",
                    "I" * len(sequence),
                ]
            )
        output.write_text("\n".join(records) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
