# -*- coding: utf-8 -*-
"""Le millesime gele, et la preuve qu il fabrique un ecart de couverture.

Overture transporte un lot Microsoft fige, 2023-09-08 en Californie du Nord,
2023-09-01 a Maricopa, 2024-02-22 au Texas. La couche Microsoft contre
laquelle le concours note est le rafraichissement de fevrier 2026. Tout
batiment sorti de terre entre les deux apparait donc en lacune de couverture
sans que personne ait mal cartographie quoi que ce soit.

La contribution benevole rattrape ce retard la ou elle est active, puisque
OpenStreetMap monte jusqu au 2026-08-01 dans le meme jeu. Le motif attendu est
donc tres precis. Dans les tracts que la contribution benevole ne couvre pas,
l ecart batiment doit valoir la CROISSANCE DU BATI depuis le gel, et il doit
s effacer la ou la contribution est vive.

Deux controles, parce que la part OpenStreetMap monte avec la densite et que
la densite baisse l ecart pour des raisons qui n ont rien a voir.

    python millesime.py
"""
import sys

import duckdb

from score import REGIONS

GEL = {"northern-ca": "2023-09-08", "maricopa-az": "2023-09-01",
       "south-central-tx": "2024-02-22", "eastern-ok": "?"}


def poser(con, region):
    con.execute(f"""
        create or replace table terrain as
        select s.GEOID, s.building_gap, s.poi_gap, s.building_defined,
               p.n_bat, p.n_osm, p.n_ms,
               p.n_osm::double / nullif(p.n_bat, 0) as part_osm,
               r.n as n_ms_ref,
               st.ur_class, st.pop_total, st.svi_overall,
               st.tribal_any, st.ALAND
        from score s
        join provenance p on p.GEOID = s.GEOID
        join n_ms_bat r on r.GEOID = s.GEOID
        join read_parquet('data/{region}/{region}-strata-tract-table.parquet') st
             on st.GEOID = s.GEOID
        where s.building_defined
    """)


def controle(con, region):
    print(f"\n### {region}, part OpenStreetMap en quintiles, DANS chaque classe")
    print("  classe   q      n   part OSM   ecart batiment   ecart POI")
    for cl, q, n, po, eb, ep in con.execute("""
        with x as (select case when ur_class ilike 'rural%' then 'Rural' else 'Urbain' end as classe,
                          part_osm, building_gap, poi_gap from terrain
                   where part_osm is not null)
        select classe, ntile(5) over (partition by classe order by part_osm) as q,
               part_osm, building_gap, poi_gap from x
    """).df().groupby(["classe", "q"]).agg(
            n=("part_osm", "size"), po=("part_osm", "mean"),
            eb=("building_gap", "mean"), ep=("poi_gap", "mean")
    ).reset_index().itertuples(index=False):
        print(f"  {cl:7}  {q}  {n:5}     {po:.3f}        {eb:.4f}        {ep:.4f}")


def desert(con, region):
    """Les tracts ou Overture n est QUE le lot Microsoft gele."""
    ligne = con.execute("""
        select count(*), avg(building_gap), avg(part_osm),
               sum(n_ms_ref), sum(n_bat)
        from terrain where part_osm < 0.02 and n_bat > 50
    """).fetchone()
    vif = con.execute("""
        select count(*), avg(building_gap), avg(part_osm)
        from terrain where part_osm > 0.90 and n_bat > 50
    """).fetchone()
    print(f"\n### {region}, gel du {GEL[region]}")
    print(f"  contribution benevole quasi nulle, part OSM sous 0,02")
    print(f"    {ligne[0]:5} tracts, ecart batiment moyen {ligne[1]:.4f}")
    print(f"  contribution benevole vive, part OSM au-dessus de 0,90")
    print(f"    {vif[0]:5} tracts, ecart batiment moyen {vif[1]:.4f}")
    if ligne[1] and vif[1]:
        print(f"  rapport {ligne[1] / vif[1]:.1f}")


def pires(con, region):
    print(f"\n### {region}, les dix tracts les plus touches par le gel")
    print("  GEOID          n Overture  n Microsoft  ecart   part OSM  population")
    for g, nb, nr, eb, po, pop in con.execute("""
        select GEOID, n_bat, n_ms_ref, building_gap, part_osm, pop_total
        from terrain where part_osm < 0.02 and n_ms_ref > 200
        order by building_gap desc limit 10
    """).fetchall():
        print(f"  {g}  {nb:9}  {nr:11}  {eb:.4f}   {po:.3f}   {pop or 0:8}")


def main():
    for region in (sys.argv[1:] or REGIONS):
        con = duckdb.connect(f"score_{region}.duckdb")
        if not con.execute("""select count(*) from duckdb_tables()
                              where table_name = 'provenance'""").fetchone()[0]:
            con.close()
            continue
        poser(con, region)
        controle(con, region)
        desert(con, region)
        pires(con, region)
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
