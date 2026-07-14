# Cohort

The target study cohort is 200 standalone end-user tools curated from at least the 300 most downloaded Bioconda package names in the frozen period. The active development cohort is a ten-package pilot.

For each included package, SeeCode selects the most recent non-prerelease version available at the freeze date and prefers an exact `linux-64` build, falling back to `noarch`. Every excluded candidate remains in the cohort table with a reason code and note.

