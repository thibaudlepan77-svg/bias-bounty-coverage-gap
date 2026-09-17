# -*- coding: utf-8 -*-
"""Provenance amont des batiments Overture, par tract, sur les quatre regions.

Chaque batiment Overture porte le jeu de donnees dont il vient et la date de
mise a jour de cet enregistrement. C est la matiere de la decouverte, et la
grille de notation du concours ne la regarde nulle part.

Le tract d un batiment est celui qui contient le centre de sa boite englobante,
exactement la convention de `score.py`. Deux mesures sur la meme convention se
comparent, deux mesures sur deux conventions ne se comparent pas.

Un batiment porte plusieurs entrees de provenance, une pour l empreinte et une
par attribut renseigne ailleurs, la hauteur surtout. Seule l entree de racine,
`property` vide, dit d ou vient l empreinte, et elle est unique par batiment.
Compter les autres gonfle le total au-dela du nombre de batiments et melange la
provenance d une empreinte avec celle d une hauteur.

L entree de racine se prend par `list_filter` et non par `unnest`. Un unnest
avant la jointure spatiale multiplie les lignes par un virgule quatre avant de
les projeter une par une, mesure du 2026-09-17, plus de huit minutes sur la
plus petite des quatre regions.

    python provenance.py                  les quatre regions
    python provenance.py eastern-ok       une seule
"""
import sys
import time

import duckdb

from score import REGIONS, centre, couche


def poser(con, region):
    con.execute("LOAD spatial;")
    con.execute("SET memory_limit='10GB';")
    con.execute(f"""
        create or replace table tracts as
        select GEOID, geometry as geom
        from read_parquet('{couche(region, "strata", "census-tracts")}')
    """)
    con.execute(f"""
        create or replace table prov_brut as
        select t.GEOID, racine.dataset as jeu, racine.update_time as maj
        from (select bbox,
                     list_filter(sources, x -> x.property = '')[1] as racine
              from read_parquet('{couche(region, "reference", "overture-buildings")}')) b
        join tracts t on ST_Within({centre()}, t.geom)
    """)
    con.execute("""
        create or replace table provenance as
        select GEOID,
               count(*) as n_bat,
               count(*) filter (jeu = 'OpenStreetMap') as n_osm,
               count(*) filter (jeu = 'Microsoft ML Buildings') as n_ms,
               count(*) filter (jeu = 'Esri Community Maps') as n_esri,
               max(maj) filter (jeu = 'Microsoft ML Buildings') as ms_maj_max,
               max(maj) filter (jeu = 'OpenStreetMap') as osm_maj_max
        from prov_brut group by GEOID
    """)
    con.execute("drop table prov_brut")


def main():
    regions = sys.argv[1:] or REGIONS
    for region in regions:
        debut = time.time()
        con = duckdb.connect(f"score_{region}.duckdb")
        poser(con, region)
        n, bat = con.execute(
            "select count(*), sum(n_bat) from provenance").fetchone()
        print(f"{region:18} {n:5} tracts  {bat:9} batiments"
              f"  {time.time() - debut:6.0f} s")
        for jeu, part in con.execute("""
                select 'osm', sum(n_osm) / sum(n_bat) from provenance
                union all select 'ms', sum(n_ms) / sum(n_bat) from provenance
                union all select 'esri', sum(n_esri) / sum(n_bat) from provenance
                """).fetchall():
            print(f"    {jeu:5} {part:.3f}")
        print("    millesime Microsoft le plus recent",
              con.execute("select max(ms_maj_max) from provenance").fetchone()[0])
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
