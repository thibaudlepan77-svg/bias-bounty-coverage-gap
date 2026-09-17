# -*- coding: utf-8 -*-
"""Le rapport tribal contre non tribal, calcule sur la note puis sur le desaccord.

La fiche de biais que la place rend avec chaque depot met les terres tribales
en tete de ses neuf indicateurs, `Tribal vs Non-Tribal`, rapport 2,902, soit
190 pour cent de plus. Ce nombre se calcule sur l ecart NOTE. Le meme rapport
calcule sur le desaccord REEL entre les deux jeux dit autre chose.

    python fiche_biais.py
"""
import sys

import duckdb

from score import REGIONS


def main():
    print("  region             groupe        tracts   ecart note   desaccord")
    total = {}
    for region in (sys.argv[1:] or REGIONS):
        con = duckdb.connect(f"score_{region}.duckdb")
        con.execute(f"""
            create or replace table fb as
            select s.building_gap, b.n_bat::double / nullif(r.n, 0) as rapport,
                   abs(1 - b.n_bat::double / nullif(r.n, 0)) as desaccord,
                   coalesce(st.tribal_any, false) as tribal, st.pop_total
            from score s
            join provenance b on b.GEOID = s.GEOID
            join n_ms_bat r on r.GEOID = s.GEOID
            join read_parquet('data/{region}/{region}-strata-tract-table.parquet') st
                 on st.GEOID = s.GEOID
            where s.building_defined and r.n > 100
        """)
        lignes = dict((t, (n, g, d)) for t, n, g, d in con.execute("""
            select tribal, count(*), avg(building_gap), avg(desaccord)
            from fb group by 1""").fetchall())
        for tribal in (True, False):
            if tribal not in lignes:
                continue
            n, g, d = lignes[tribal]
            print(f"  {region:18} {'tribal' if tribal else 'non tribal':11}  "
                  f"{n:6}     {g:.4f}      {d:.4f}")
            total.setdefault(tribal, []).append((n, g, d))
        if True in lignes and False in lignes:
            gt, gf = lignes[True][1], lignes[False][1]
            dt, df = lignes[True][2], lignes[False][2]
            print(f"  {'':18} rapport sur la note      {gt / gf:5.2f}"
                  f"      sur le desaccord {dt / df:5.2f}")
        con.close()

    print("\n  les quatre regions ensemble")
    for tribal in (True, False):
        n = sum(x[0] for x in total[tribal])
        g = sum(x[0] * x[1] for x in total[tribal]) / n
        d = sum(x[0] * x[2] for x in total[tribal]) / n
        total[tribal] = (n, g, d)
        print(f"  {'tribal' if tribal else 'non tribal':11} {n:6} tracts"
              f"   note {g:.4f}   desaccord {d:.4f}")
    print(f"  rapport sur la note      {total[True][1] / total[False][1]:5.2f}")
    print(f"  rapport sur le desaccord {total[True][2] / total[False][2]:5.2f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
