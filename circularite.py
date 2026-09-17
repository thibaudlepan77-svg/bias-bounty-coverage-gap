# -*- coding: utf-8 -*-
"""L objection qu un juge posera en premier, et la mesure qui y repond.

L ecart batiment vaut `1 - n_overture / n_microsoft`. La part OpenStreetMap se
calcule sur le meme `n_overture`. Un juge dira donc que le lien entre les deux
est mecanique, plus il y a de batiments benevoles, plus le numerateur monte,
moins l ecart est grand, et ca ne prouverait rien du tout.

Ce qui departage les deux lectures est le RAPPORT `n_overture / n_microsoft`
la ou les benevoles sont actifs.

    s il depasse largement 1      Overture compte des objets que Microsoft
                                  ignore, l ecart tombe par gonflement du
                                  numerateur, et l objection est fondee
    s il se tient autour de 1     les deux jeux tombent d accord sur le meme
                                  bati, l ecart tombe parce qu il n y a plus
                                  rien a rattraper, et l objection tombe

    python circularite.py
"""
import sys

import duckdb

from score import REGIONS


def main():
    print("  region             part OSM              n   rapport Overture sur"
          " Microsoft")
    print("                                              median    q1      q9  "
          "  part au-dessus de 1,05")
    for region in (sys.argv[1:] or REGIONS):
        con = duckdb.connect(f"score_{region}.duckdb")
        con.execute(f"""
            create or replace table rap as
            select s.GEOID, s.building_gap,
                   b.n_osm::double / nullif(b.n_bat, 0) as part_osm,
                   b.n_bat::double / nullif(r.n, 0) as rapport
            from score s
            join provenance b on b.GEOID = s.GEOID
            join n_ms_bat r on r.GEOID = s.GEOID
            where s.building_defined and r.n > 100
        """)
        for tr, n, med, q1, q9, gonfle in con.execute("""
            select case when part_osm < 0.05 then 'sous 0,05'
                        when part_osm < 0.50 then '0,05 a 0,50'
                        when part_osm < 0.90 then '0,50 a 0,90'
                        else 'au-dessus de 0,90' end as tr,
                   count(*), median(rapport),
                   quantile_cont(rapport, 0.1), quantile_cont(rapport, 0.9),
                   avg(case when rapport > 1.05 then 1.0 else 0 end)
            from rap group by 1 order by min(part_osm)
        """).fetchall():
            print(f"  {region:18} {tr:17} {n:5}   {med:5.3f}  {q1:5.3f}  {q9:5.3f}"
                  f"     {gonfle:.3f}")
        con.close()
        print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
