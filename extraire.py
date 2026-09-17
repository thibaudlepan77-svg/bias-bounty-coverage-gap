# -*- coding: utf-8 -*-
"""Agregats par tract tires DIRECTEMENT des parquets distants, sans rapatrier.

Le lien de cette machine plafonne a 0,04 Mo/s, mesure a un fil comme a huit.
Rapatrier les 5 Go du concours demanderait trente-cinq heures. Or les fichiers
sont en colonnes, tries en Hilbert, et portent une colonne `bbox` faite pour la
lecture par plages. Compter des batiments ne demande donc pas la geometrie
complete, seulement la bbox, et DuckDB ne va chercher que les pages de cette
colonne-la.

Mesure du 2026-09-11 sur les 1 164 724 batiments Overture de Californie du
Nord, comptage filtre sur bbox en 62 s contre 54 minutes de telechargement.

Le centre de bbox n est PAS le centroide de la geometrie. Pour un batiment
l ecart est metrique et sans effet sur un comptage par tract, sauf pour celui
qui est a cheval sur une limite. C est bon pour explorer et pour le prix de la
decouverte, ca reste a refaire sur la geometrie vraie avant une soumission
notee.

    python extraire.py northern-ca
"""
import os
import sys
import time
import urllib.request

import duckdb

DEPOT = ("https://data.source.coop/humane-intelligence/"
         "bias-bounty-mapping-equity-challenge")
CATEGORIES_HIFLD = {
    "fire": ("fire_department",),
    "ems": ("ambulance_and_ems_services",),
    "schools": ("elementary_school", "middle_school", "high_school",
                "school", "private_school", "public_school"),
}


def source(region, dossier, nom):
    """Le fichier local s il est COMPLET, sinon le distant.

    Un fichier en cours de rapatriement a une taille non nulle et pas de pied
    de page, DuckDB le refuse alors avec `No magic bytes found`. On compare
    donc a la taille annoncee par le depot au lieu de se fier a la presence.
    """
    distant = f"{DEPOT}/{dossier}/{region}/{region}-{nom}.parquet"
    local = os.path.join("data", region, f"{region}-{nom}.parquet")
    if not os.path.exists(local):
        return distant
    try:
        req = urllib.request.Request(distant, method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0"})
        attendu = int(urllib.request.urlopen(req, timeout=45)
                      .headers.get("Content-Length", 0))
    except Exception:
        return distant
    return local if os.path.getsize(local) == attendu else distant


def centre(prefixe="b"):
    return (f"ST_Point(({prefixe}.bbox.xmin + {prefixe}.bbox.xmax) / 2, "
            f"({prefixe}.bbox.ymin + {prefixe}.bbox.ymax) / 2)")


def compter_points(con, region, nom, dossier="reference", filtre="true"):
    """Points par tract, via le centre de bbox. Une seule lecture de colonne."""
    depart = time.time()
    con.execute(f"""
        create or replace table n_{nom.replace('-', '_')} as
        select t.GEOID, count(*) as n
        from read_parquet('{source(region, dossier, nom)}') b
        join tracts t on ST_Within({centre()}, t.geom)
        where {filtre}
        group by t.GEOID
    """)
    total = con.sql(f"select sum(n) from n_{nom.replace('-', '_')}").fetchone()[0]
    print(f"  {nom:<24}{total or 0:>10}  en {time.time() - depart:>6.1f} s", flush=True)


def main():
    region = sys.argv[1] if len(sys.argv) > 1 else "northern-ca"
    con = duckdb.connect(f"extraits_{region}.duckdb")
    con.execute("LOAD spatial;")
    con.execute("SET memory_limit='6GB';")

    print(f"{region}, tracts", flush=True)
    con.execute(f"""
        create or replace table tracts as
        select GEOID, ALAND, pop_total, ur_class, geometry as geom
        from read_parquet('{source(region, "strata", "census-tracts")}')
    """)
    print(f"  {con.sql('select count(*) from tracts').fetchone()[0]} tracts\n", flush=True)

    compter_points(con, region, "overture-buildings")
    compter_points(con, region, "microsoft-buildings")
    compter_points(con, region, "overture-pois")

    # Les points d interet portent leur categorie dans une structure imbriquee.
    depart = time.time()
    con.execute(f"""
        create or replace table pois_categorie as
        select t.GEOID, b.categories.primary as categorie, count(*) as n
        from read_parquet('{source(region, "reference", "overture-pois")}') b
        join tracts t on ST_Within({centre()}, t.geom)
        group by t.GEOID, b.categories.primary
    """)
    print(f"  {'pois par categorie':<24}"
          f"{con.sql('select count(*) from pois_categorie').fetchone()[0]:>10}"
          f"  en {time.time() - depart:>6.1f} s", flush=True)

    for famille, cats in CATEGORIES_HIFLD.items():
        con.execute(f"""
            create or replace table overture_{famille} as
            select GEOID, sum(n) as n from pois_categorie
            where categorie in {cats} group by GEOID
        """)
        n = con.sql(f"select coalesce(sum(n), 0) from overture_{famille}").fetchone()[0]
        print(f"  {'overture ' + famille:<24}{n:>10}")

    con.close()
    print(f"\nextraits_{region}.duckdb ecrit")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
