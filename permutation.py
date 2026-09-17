# -*- coding: utf-8 -*-
"""Le rapport tribal tient-il autre chose que du hasard, sur les deux mesures.

Un concurrent de ce concours accompagne sa decouverte d un test de permutation
et d un intervalle de bootstrap, et il a raison. Un rapport de 4,50 sur 805
tracts contre 377 se defend, un rapport de 0,19 aussi, mais ni l un ni l autre
ne se defend en le disant.

Le test. On melange l etiquette tribale A L INTERIEUR de chaque region, ce qui
casse le lien avec l etiquette sans toucher aux differences entre regions, puis
on recalcule le rapport. La p-valeur est la part des melanges qui produisent un
rapport au moins aussi extreme que l observe, du cote observe.

    python permutation.py
    python permutation.py 50000
"""
import sys

import duckdb
import numpy as np

from score import REGIONS

TIRAGES = 20000
GRAINE = 20260917


def charger():
    morceaux = []
    for region in REGIONS:
        con = duckdb.connect(f"score_{region}.duckdb", read_only=True)
        cadre = con.execute(f"""
            select s.building_gap as note,
                   abs(1 - b.n_bat::double / nullif(r.n, 0)) as desaccord,
                   coalesce(st.tribal_any, false) as tribal
            from score s
            join provenance b on b.GEOID = s.GEOID
            join n_ms_bat r on r.GEOID = s.GEOID
            join read_parquet('data/{region}/{region}-strata-tract-table.parquet') st
                 on st.GEOID = s.GEOID
            where s.building_defined and r.n > 100
        """).df()
        cadre["region"] = region
        morceaux.append(cadre)
        con.close()
    import pandas as pd
    return pd.concat(morceaux, ignore_index=True)


def rapport(valeurs, tribal):
    haut = valeurs[tribal].mean()
    bas = valeurs[~tribal].mean()
    return haut / bas if bas else np.nan


def tester(cadre, colonne, tirages, rng):
    valeurs = cadre[colonne].to_numpy(float)
    tribal = cadre["tribal"].to_numpy(bool)
    regions = cadre["region"].to_numpy()
    observe = rapport(valeurs, tribal)

    blocs = [np.where(regions == r)[0] for r in np.unique(regions)]
    extremes = 0
    for _ in range(tirages):
        melange = tribal.copy()
        for bloc in blocs:
            melange[bloc] = rng.permutation(tribal[bloc])
        simule = rapport(valeurs, melange)
        if np.isnan(simule):
            continue
        if (observe >= 1 and simule >= observe) or (observe < 1 and simule <= observe):
            extremes += 1
    return observe, (extremes + 1) / (tirages + 1)


def bootstrap(cadre, colonne, tirages, rng):
    """Intervalle a 95 pour cent, reechantillonnage des tracts dans la region."""
    valeurs = cadre[colonne].to_numpy(float)
    tribal = cadre["tribal"].to_numpy(bool)
    regions = cadre["region"].to_numpy()
    blocs = [np.where(regions == r)[0] for r in np.unique(regions)]
    tire = []
    for _ in range(tirages):
        pris = np.concatenate([rng.choice(b, len(b), replace=True) for b in blocs])
        valeur = rapport(valeurs[pris], tribal[pris])
        if not np.isnan(valeur):
            tire.append(valeur)
    return np.percentile(tire, [2.5, 97.5])


def main():
    tirages = int(sys.argv[1]) if len(sys.argv) > 1 else TIRAGES
    rng = np.random.default_rng(GRAINE)
    cadre = charger()
    print(f"{len(cadre)} tracts, dont {int(cadre['tribal'].sum())} tribaux,"
          f" {tirages} tirages, graine {GRAINE}\n")

    for etiquette, sous in (("les quatre regions", cadre),
                            ("Oklahoma orientale seule",
                             cadre[cadre.region == "eastern-ok"])):
        print(f"  {etiquette}, {len(sous)} tracts")
        for colonne, nom in (("note", "ecart note"),
                             ("desaccord", "desaccord reel")):
            observe, p = tester(sous, colonne, tirages, rng)
            bas, haut = bootstrap(sous, colonne, min(tirages, 5000), rng)
            print(f"    {nom:16} rapport {observe:5.2f}"
                  f"   p {p:.2e}   intervalle [{bas:.2f}, {haut:.2f}]")
        print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
