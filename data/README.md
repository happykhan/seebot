# Data storage policy

Committed data is limited to frozen cohort tables, reviewed manifests, normalized pilot results, small fixtures, and checksum/location manifests. Large raw download data, complete third-party sources, execution environments, and bulky raw evidence are stored externally and referenced by immutable hashes.

`data/raw/` and `evidence/` are ignored locally. A public release must provide an artifact manifest sufficient to retrieve and verify every external object.

