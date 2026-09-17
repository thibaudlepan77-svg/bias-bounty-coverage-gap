# -*- coding: utf-8 -*-
"""Les deux motifs de disparite que la grille du concours ne peut pas voir.

La notation automatique croise cinq metriques fixes avec des strates fixes,
urbain contre rural, vulnerabilite sociale, vulnerabilite climatique, terres
tribales, exposition chaleur feu secheresse. Aucune de ces strates ne porte la
PROVENANCE AMONT d un batiment Overture, ni l HISTOIRE du feu, seulement
l exposition. Les deux motifs ci-dessous vivent exactement la.

    python decouverte.py                 les regions dont la provenance est posee
"""
import sys

import duckdb

from score import REGIONS

FAIT = []


def table(con, region):
    """Score, provenance, ruralite et histoire du feu sur une seule ligne."""
    con.execute(f"""
        create or replace table terrain as
        select s.GEOID, s.transport_gap, s.building_gap, s.poi_gap,
               s.coverage_gap_score, s.building_defined, s.poi_defined,
               p.n_bat, p.n_osm, p.n_ms, p.ms_maj_max,
               p.n_osm::double / nullif(p.n_bat, 0) as part_osm,
               st.ur_class, st.pop_total, st.ALAND,
               st.svi_overall, st.tribal_any,
               u.usgs_wildfire_ever, u.usgs_years_since_last_fire,
               u.usgs_last_year_burned, u.usgs_wildfire_burned_pct_area
        from score s
        join provenance p on p.GEOID = s.GEOID
        join read_parquet('data/{region}/{region}-strata-tract-table.parquet') st
             on st.GEOID = s.GEOID
        left join read_parquet('data/{region}/{region}-usgs-combined-tract-table.parquet') u
             on u.GEOID = s.GEOID
    """)


def quintiles(con, region):
    print(f"\n### {region}, quintiles de la part OpenStreetMap")
    print("  q     n   part OSM   ecart batiment   ecart POI")
    for q, n, po, eb, ep in con.execute("""
        select ntile(5) over (order by part_osm) as q, count(*) over () as z,
               part_osm, building_gap, poi_gap from terrain
        where part_osm is not null
    """).df().groupby("q").agg(
            n=("part_osm", "size"), po=("part_osm", "mean"),
            eb=("building_gap", "mean"), ep=("poi_gap", "mean")
    ).reset_index().itertuples(index=False):
        print(f"  {q}  {n:5}     {po:.3f}        {eb:.4f}        {ep:.4f}")


def croisement(con, region):
    print(f"\n### {region}, ruralite croisee avec l histoire du feu")
    print("  classe  feu           n   part OSM   ecart batiment   ecart POI")
    for cl, feu, n, po, eb, ep in con.execute("""
        select case when ur_class ilike 'rural%' then 'Rural' else 'Urbain' end as classe,
               case when coalesce(usgs_wildfire_ever, false) then 'brule' else 'non brule' end as feu,
               count(*), avg(part_osm), avg(building_gap), avg(poi_gap)
        from terrain where part_osm is not null
        group by 1, 2 order by 1, 2
    """).fetchall():
        print(f"  {cl:7} {feu:10} {n:5}     {po:.3f}        {eb:.4f}        {ep:.4f}")


def anciennete(con, region):
    print(f"\n### {region}, ecart batiment par anciennete du dernier feu")
    print("  derniere annee brulee     n   part OSM   ecart batiment")
    for tranche, n, po, eb in con.execute("""
        select case when usgs_last_year_burned is null then 'jamais'
                    when usgs_last_year_burned >= 2020 then '2020 et apres'
                    when usgs_last_year_burned >= 2010 then '2010 a 2019'
                    when usgs_last_year_burned >= 2000 then '2000 a 2009'
                    else 'avant 2000' end as tranche,
               count(*), avg(part_osm), avg(building_gap)
        from terrain where part_osm is not null
        group by 1 order by 1
    """).fetchall():
        print(f"  {tranche:20} {n:6}     {po:.3f}        {eb:.4f}")


def main():
    regions = sys.argv[1:] or REGIONS
    for region in regions:
        con = duckdb.connect(f"score_{region}.duckdb")
        if not con.execute("""select count(*) from duckdb_tables()
                              where table_name = 'provenance'""").fetchone()[0]:
            print(f"\n{region}, provenance absente, region sautee")
            con.close()
            continue
        table(con, region)
        quintiles(con, region)
        croisement(con, region)
        anciennete(con, region)
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
