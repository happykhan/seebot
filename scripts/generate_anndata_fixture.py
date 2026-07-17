#!/usr/bin/env python3
"""Generate the compact AnnData fixture used by scanpy-scripts probes."""

from __future__ import annotations

from pathlib import Path

import anndata
import numpy
import pandas

OUTPUT = Path(__file__).resolve().parents[1] / "fixtures/scanpy/example.h5ad"
EMPTY_OUTPUT = Path(__file__).resolve().parents[1] / "fixtures/scanpy/empty.h5ad"


def main() -> None:
    matrix = numpy.asarray([[1, 0, 3], [0, 2, 1], [4, 1, 0]], dtype=numpy.float32)
    observations = pandas.DataFrame(index=["cell_1", "cell_2", "cell_3"])
    variables = pandas.DataFrame(index=["gene_1", "gene_2", "gene_3"])
    data = anndata.AnnData(X=matrix, obs=observations, var=variables)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    data.write_h5ad(OUTPUT)
    empty = anndata.AnnData(
        X=numpy.empty((0, 3), dtype=numpy.float32),
        obs=pandas.DataFrame(index=[]),
        var=variables.copy(),
    )
    empty.write_h5ad(EMPTY_OUTPUT)


if __name__ == "__main__":
    main()
