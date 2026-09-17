# -*- coding: utf-8 -*-
"""Provenance amont des points d interet Overture, par tract.

Les points d interet ne viennent PAS des memes producteurs que les batiments.
Aucun d eux ne vient d OpenStreetMap, releve du 2026-09-17 sur la Californie du
Nord, ils viennent de meta, Microsoft, BrightQuery, Foursquare, AllThePlaces et
DAC. C est ce qui rend la mesure interessante, si la part OpenStreetMap des
BATIMENTS predit l ecart sur les POINTS D INTERET, alors ce n est pas un defaut
d un pipeline, c est un biais que des producteurs independants partagent.

    python provenance_poi.py
"""
import sys
import time

import duckdb

from score import REGIONS, centre, couche

JEUX = ["meta", "Microsoft", "BrightQuery", "Foursquare", "AllThePlaces", "DAC"]


def poser(con, region):
    con.execute("LOAD spatial;")
    con.execute("SET memory_limit='10GB';")
    con.execute(f"""
        create or replace table tracts as
        select GEOID, geometry as geom
        from read_parquet('{couche(region, "strata", "census-tracts")}')
    """)
    colonnes = ",\n               ".join(
        f"count(*) filter (jeu = '{j}') as n_{j.lower()}" for j in JEUX)
    con.execute(f"""
        create or replace table poi_brut as
        select t.GEOID, racine.dataset as jeu
        from (select bbox,
                     list_filter(sources, x -> x.property = '')[1] as racine
              from read_parquet('{couche(region, "reference", "overture-pois")}')) b
        join tracts t on ST_Within({centre()}, t.geom)
    """)
    con.execute(f"""
        create or replace table provenance_poi as
        select GEOID, count(*) as n_poi, {colonnes}
        from poi_brut group by GEOID
    """)
    con.execute("drop table poi_brut")


def main():
    for region in (sys.argv[1:] or REGIONS):
        debut = time.time()
        con = duckdb.connect(f"score_{region}.duckdb")
        poser(con, region)
        total = con.execute("select sum(n_poi) from provenance_poi").fetchone()[0]
        parts = con.execute(
            "select " + ", ".join(f"sum(n_{j.lower()})::double / sum(n_poi)"
                                  for j in JEUX) + " from provenance_poi").fetchone()
        print(f"{region:18} {total:8} points  {time.time() - debut:5.0f} s")
        print("   " + "  ".join(f"{j} {p:.3f}" for j, p in zip(JEUX, parts)))
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
