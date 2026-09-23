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
pip install duckdb pandas numpy
```

`pandas` is used only to group a few result tables for printing, and `numpy`
only by the permutation test.

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

## How each component is computed, and what happens at the edges

This section answers the documentation prize checklist in its own order. Every
count below is printed by `cas_limites.py`, whose run is committed as
`cas_limites.txt`.

### Sources

All layers come from the challenge bucket on source.coop, pulled by `tirer.py`.
Tracts and their attributes come from `strata/<region>-census-tracts`. The
reference and comparison layers come from `reference/`, namely
`census-tiger-roads`, `overture-roads`, `microsoft-buildings`,
`overture-buildings`, `overture-pois`, `hifld-fire-stations`,
`hifld-ems-stations`, `hifld-schools` and `census-cbp`. Hospitals are left out
on purpose, as the dataset README asks, because Overture counts roughly twelve
times too many of them and the term would never bite.

### The three components

**Transport.** Kilometres of TIGER roads with MTFCC `S1100` or `S1200`, clipped
to the tract and measured in EPSG:5070, against kilometres of Overture roads of
class `motorway`, `trunk`, `primary` or `secondary`, clipped the same way. The
gap is `1 - min(1, overture_km / tiger_km)`. It is undefined when the tract has
no TIGER highway at all.

**Buildings.** Footprints are assigned to the tract that contains the centre of
their bounding box, so a building on a boundary is counted once. The gap is
`1 - min(1, overture / microsoft)`, undefined when Microsoft has no footprint in
the tract.

**Points of interest.** Two halves. The HIFLD half takes fire stations, EMS
stations and schools separately, compares each with the matching Overture
categories (listed in `CATEGORIES_HIFLD` in `score.py`), and averages the
families that have at least one HIFLD record. The CBP half compares all Overture
places in the tract with the total establishment count, `cbp_estab`. The
component is the mean of the halves that are defined.

**Composite.** The mean of the components that are defined, so the divisor is
1, 2 or 3 depending on the tract, never 3 by default. The only external check
available is the share of tracts with at least one undefined component that
the evaluation page publishes. For northern-ca the pipeline gives 218 of 591,
36.9 percent, against the published 37 percent.

### Edge cases

**Zero population tracts.** There are 0, 1, 11 and 21 of them in northern-ca,
eastern-ok, maricopa-az and south-central-tx. Population does not enter the
formula, so they are scored like any other tract whenever a reference layer has
something in them. 1, 11 and 14 of them get a score, with means of 0.188, 0.009
and 0.221.

**Water tracts.** Nine tracts have no land area at all (`ALAND = 0`), all in
south-central-tx, all with a GEOID ending in `990000`. Seven have nothing in any
reference layer, get no score, and are absent from the sample submission, which
is how `assembler.py` drops them. The other two are scored, and that is worth
flagging. `48039990000` holds one Microsoft footprint and `48057990000` holds
48, with no Overture building in either. Their building gap is 1, their
composite is 1.0, the highest value the metric can give, for tracts with no land
and no residents. I kept them because the text gives no rule to exclude them,
but anyone using the scores for preparedness should drop them first.

**Tracts with no Overture data.** A missing Overture feature never makes a
component undefined. Only the reference side decides that. When the reference
has something and Overture has nothing, the component is 1, a full gap. The two
water tracts above are the only tracts in the four regions with no Overture road
and no Overture building while a reference layer is present.

**How many components each tract has.** Three, two, one and zero defined
components respectively, 373 / 216 / 2 / 0 in northern-ca, 938 / 253 / 1 / 0 in
eastern-ok, 719 / 863 / 11 / 0 in maricopa-az and 4294 / 1696 / 13 / 7 in
south-central-tx.

### Alternative weightings, and why I did not use them

**A fixed divisor of 3**, an undefined component counted as zero. The evaluation
page rules it out, and it barely matters here. The mean absolute change is
0.003, 0.0009, 0.0037 and 0.002 by region and the rank correlation with the
submitted composite stays at 0.998 or above. Most gaps are small, so dividing
by three instead of two moves few tracts past their neighbours.

**Weighting tracts by population** is not a choice the submission can make, the
score is per tract. For reading the results it does matter a little. The
population weighted mean is lower than the plain mean in three regions out of
four (0.0615 against 0.0656 in northern-ca), eastern-ok being the exception.
The rural mean is 1.8 to 2.9 times the urban mean depending on the region.

**The conventions the text leaves open**, measured by `variantes.py` on
northern-ca. Assigning buildings by intersection instead of bounding box centre
moves the composite by an RMS of 9.0e-5. Rounding to four decimals moves it by
2.5e-5. Using only business establishments from CBP instead of the total moves
it by 0.055, with a maximum of 0.25 on one tract. That last one is the only
convention that changes the answer materially, and the evaluation page settles
it by naming all establishments.

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

`permutation.py` shuffles the tribal label within each region and recomputes the
ratio, twenty thousand draws on a fixed seed, plus a region stratified bootstrap
for the interval. `permutation.txt` is the run the writeup quotes. It needs
`numpy`.

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
