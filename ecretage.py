# -*- coding: utf-8 -*-
"""Ce que la metrique JETTE, et ou elle le jette.

L ecart batiment vaut `1 - min(1, n_overture / n_microsoft)`. Il est a SENS
UNIQUE. Un tract ou Overture compte trente pour cent de batiments EN TROP est
note zero, exactement comme un tract ou les deux jeux tombent d accord au
batiment pres. Le desaccord existe, la note le jette.

On compare donc deux quantites sur les memes tracts.

    ecart note        1 - min(1, rapport)       ce que le concours mesure
    desaccord         abs(1 - rapport)          ce que les deux jeux disent

La difference entre les deux est ce que l ecretage retire. Si elle etait
repartie au hasard ce ne serait qu une perte de finesse. Elle ne l est pas.

    python ecretage.py
"""
import sys

import duckdb

from score import REGIONS


def main():
    for region in (sys.argv[1:] or REGIONS):
        con = duckdb.connect(f"score_{region}.duckdb")
        con.execute(f"""
            create or replace table ecr as
            select s.GEOID, s.building_gap,
                   b.n_osm::double / nullif(b.n_bat, 0) as part_osm,
                   b.n_bat::double / nullif(r.n, 0) as rapport,
                   abs(1 - b.n_bat::double / nullif(r.n, 0)) as desaccord,
                   st.pop_total, st.tribal_any, st.svi_overall,
                   case when st.ur_class ilike 'rural%' then 'Rural' else 'Urbain' end as classe
            from score s
            join provenance b on b.GEOID = s.GEOID
            join n_ms_bat r on r.GEOID = s.GEOID
            join read_parquet('data/{region}/{region}-strata-tract-table.parquet') st
                 on st.GEOID = s.GEOID
            where s.building_defined and r.n > 100
        """)
        print(f"\n### {region}")
        print("  part OSM              n   ecart note   desaccord reel"
              "   part jetee   tracts ecretes")
        for tr, n, eb, des, ecr in con.execute("""
            select case when part_osm < 0.05 then 'sous 0,05'
                        when part_osm < 0.50 then '0,05 a 0,50'
                        when part_osm < 0.90 then '0,50 a 0,90'
                        else 'au-dessus de 0,90' end as tr,
                   count(*), avg(building_gap), avg(desaccord),
                   avg(case when rapport > 1 then 1.0 else 0 end)
            from ecr group by 1 order by min(part_osm)
        """).fetchall():
            print(f"  {tr:17} {n:5}     {eb:.4f}       {des:.4f}"
                  f"       {1 - eb / des if des else 0:.2f}        {ecr:.3f}")

        print("\n  qui vit dans les tracts que l ecretage protege, rapport"
              " au-dessus de 1")
        for cond, etiquette in (("rapport > 1", "note zero par ecretage"),
                                ("rapport <= 1", "note sur son deficit")):
            n, pop, tri, svi, des = con.execute(f"""
                select count(*), sum(pop_total),
                       avg(case when tribal_any then 1.0 else 0 end),
                       avg(svi_overall), avg(desaccord)
                from ecr where {cond}""").fetchone()
            print(f"    {etiquette:24} {n:5} tracts  {pop or 0:9} hab"
                  f"  tribal {tri:.3f}  SVI {svi or 0:.3f}"
                  f"  desaccord {des:.4f}")
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
