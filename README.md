# Bias Bounty Mapping Equity Challenge, reproduction code

Entry of `thibaudlepan` for the Zindi Bias Bounty Mapping Equity Challenge.
Everything the writeup claims is produced by the scripts in this repository.
Nothing is quoted there that is not printed by one of them.

The writeup itself is posted on the competition discussion board, thread 34844.

Source comments and docstrings are in French, the author's language. The SQL and
the variable names carry the logic, and this file carries the walkthrough.

## What you need

Python 3.13 and DuckDB with the `spatial` extension. Nothing else. No model, no
seed, no randomness anywhere, so two runs give the same numbers.

```
pip install duckdb pandas
```

`pandas` is used only to group a few result tables for printing.

## Getting the data

```
python tirer.py                       all four regions, about 5 GB
python tirer.py northern-ca           one region
```

It reads the S3 inventory rather than guessing file names, resumes a partial
file with a `Range` request, and refuses a response whose `Content-Range` does
not start exactly at the byte it asked for. That last check matters, the bucket
returned a full body with a 206 status on 2026-09-11 and silently corrupted a
271 MB file.

If a download does not finish, nothing breaks. `score.py` compares the local
size against the remote `Content-Length` and falls back to reading the parquet
remotely, column pruned, which for a single column is faster than waiting for
the whole file.

## Producing the submission

```
python score.py northern-ca
python score.py eastern-ok
python score.py maricopa-az
python score.py south-central-tx
python assembler.py                   writes soumission.csv, 9 379 rows
```

`score.py` writes one DuckDB file per region holding every intermediate table,
so nothing has to be recomputed to check a number later.

Every rule in it comes from a sentence of the evaluation page or of the dataset
README. The places where the text leaves a choice are collected in the
`CONVENTIONS` dictionary at the top rather than buried in a query, so they can
be varied and compared instead of argued about. `variantes.py` measures what
each one costs.

`assembler.py` refuses to write a file whose GEOID set does not match the
region's `<region>-sample-submission.csv` exactly. That is how the seven
south-central-tx water tracts get dropped, they exist in the tract layer and not
in the scored list.

**Submit two columns, `GEOID` and `coverage_gap_score`, and nothing else.** The
evaluation page says component scores may be included as optional columns. The
scorer reads the second column whatever it is. The five column version of this
exact computation scored 0.082233846 and the two column version scored
0.000145466.

## Producing the evidence in the writeup

```
python provenance.py                  building provenance per tract
python provenance_poi.py              POI provenance per tract
python ecretage.py > ecretage.txt     what the one sided metric discards
python circularite.py                 the test the first correlation failed
python preuves.py > preuves.txt       the remaining tables
```

`provenance.py` counts, for every tract, how many Overture buildings come from
OpenStreetMap, from the Microsoft batch and from Esri, and the newest update
date of each upstream. Two things are worth knowing before rerunning it.

A building carries several provenance entries, one for the footprint and one per
individually sourced attribute, mostly height. Only the entry whose `property`
is empty describes where the footprint came from, and it is unique per building.
Counting the others pushes the total past the number of buildings and mixes the
provenance of a footprint with that of a height.

Take that entry with `list_filter`, not with `unnest`. An `unnest` placed before
the spatial join multiplies rows by 1.4 and then projects them one at a time.
Over eight minutes on the smallest region, against thirty four seconds for the
same result.

`ecretage.py` prints the table the discovery rests on. For each tract it puts
the scored gap, `1 - min(1, overture / microsoft)`, next to the plain
disagreement, `abs(1 - overture / microsoft)`, and reports the share of the
second that the first discards, broken out by how much of the tract is volunteer
mapped and by which side of the clip the tract falls on.

`fiche_biais.py` recomputes the tribal against non tribal ratio, first on the
scored gap and then on the plain disagreement, on the same tracts. The two
answers do not agree on the sign, which is the point of the last section of the
writeup.

`circularite.py` is the test that killed the result I started with. The scored
gap is computed on the same Overture count that the volunteer share is computed
from, so a correlation between them can be mechanical. Restricting to tracts
where the ratio is at most one, where no surplus can be clipped, is what settles
it. It did not settle it in my favour.

## The exploratory scripts, kept because two of them failed

`decouverte.py` and `millesime.py` carry the wildfire hypothesis and the
vintage hypothesis. The wildfire one holds in Northern California and dies in
the other three regions, and the writeup says so. They are here so that claim
can be checked rather than believed.

`derive.py` measures the vintage drift and carries, in its docstring, the reason
that quantity is only readable where the volunteer share is low. My first
version of it was wrong and the docstring says how.

`sondes.py` and `decalage.py` build leaderboard probe files. The first design,
zeroing one region and comparing against an all zero file, does not work, it
measures the sum of squared truth on that region, a thousand times larger than
the error being looked for. The second design, shifting one region by a small
delta and comparing two nearby files, keeps the term of interest at first order.
The docstrings carry the algebra.

`transport.py` and `extraire.py` are earlier scaffolding, kept so the history
of the pipeline is not rewritten after the fact.

## Outputs committed here

`preuves.txt` and `ecretage.txt` are the runs of 2026-09-17 that the writeup
quotes. Rerunning should reproduce them line for line.

## One number that is not in any script

The public leaderboard allows five submissions per day and two hundred in total,
measured on the interface on 2026-09-17 after the fifth. The rules page says ten
and three hundred.
