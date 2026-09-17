# -*- coding: utf-8 -*-
"""Score de lacune de couverture par tract, reimplemente clause par clause.

Chaque regle ci-dessous vient d une phrase de la page d evaluation ou du README
du jeu de donnees. Rien n est devine. Les endroits ou le texte laisse un choix
sont rassembles dans CONVENTIONS, pour qu on puisse les faire varier et
comparer les scores au lieu d en discuter.

Le composite est la moyenne des composantes DEFINIES, le diviseur vaut donc 1,
2 ou 3 selon le tract et jamais 3 par defaut. Une composante indefinie s ecrit
0 avec son drapeau a faux, ce qui veut dire rien a comparer et surtout pas
parfaitement couvert.

    python score.py northern-ca
"""
import os
import sys
import urllib.request

import duckdb

REGIONS = ["northern-ca", "eastern-ok", "maricopa-az", "south-central-tx"]

# Verbatim de la page d evaluation.
TIGER_AUTOROUTES = ("S1100", "S1200")
OVERTURE_AUTOROUTES = ("motorway", "trunk", "primary", "secondary")
# Verbatim du README. Les hopitaux sont volontairement absents, Overture en
# compte environ douze fois trop et le terme ne mordrait jamais.
CATEGORIES_HIFLD = {
    "fire": ("fire_department",),
    "ems": ("ambulance_and_ems_services",),
    "schools": ("elementary_school", "middle_school", "high_school",
                "school", "private_school", "public_school"),
}
COUCHE_HIFLD = {"fire": "hifld-fire-stations", "ems": "hifld-ems-stations",
                "schools": "hifld-schools"}

# Part de tracts ayant AU MOINS UNE composante indefinie, donnee par la page
# d evaluation. C est le seul controle externe de la chaine.
PART_INDEFINIE = {"eastern-ok": 0.21, "northern-ca": 0.37,
                  "south-central-tx": 0.28, "maricopa-az": 0.55}

CONVENTIONS = {
    # Un batiment est rattache au tract qui contient son centroide. L autre
    # lecture possible serait l intersection, qui compterait deux fois un
    # batiment a cheval.
    "rattachement_batiment": "centroide",
    # Une route est coupee au tract et on mesure la portion interieure.
    "rattachement_route": "intersection",
    # Projection metrique. always_xy sinon chaque geometrie revient a l infini
    # sans lever d erreur.
    "projection": "EPSG:5070",
}


DEPOT = ("https://data.source.coop/humane-intelligence/"
         "bias-bounty-mapping-equity-challenge")
_tailles = {}


def couche(region, dossier, nom):
    """Le fichier local s il est COMPLET, sinon le distant.

    Un parquet a moitie rapatrie a une taille non nulle et pas de pied de page,
    DuckDB le refuse alors avec `No magic bytes found`. Et comme le format est
    en colonnes, lire a distance la seule colonne dont on a besoin coute moins
    que d attendre la fin du telechargement, mesure du 2026-09-11, six minutes
    contre cent dix pour les deux couches de batiments.
    """
    distant = f"{DEPOT}/{dossier}/{region}/{region}-{nom}.parquet"
    local = os.path.join("data", region, f"{region}-{nom}.parquet")
    if not os.path.exists(local):
        return distant
    if distant not in _tailles:
        try:
            req = urllib.request.Request(distant, method="HEAD",
                                         headers={"User-Agent": "Mozilla/5.0"})
            _tailles[distant] = int(urllib.request.urlopen(req, timeout=45)
                                    .headers.get("Content-Length", 0))
        except Exception:
            return distant
    return local if os.path.getsize(local) == _tailles[distant] else distant


def metres(expr):
    return (f"ST_Length(ST_Transform({expr}, 'EPSG:4326', 'EPSG:5070', "
            f"always_xy := true))")


def poser_tracts(con, region):
    con.execute(f"""
        create or replace table tracts as
        select GEOID, ALAND, pop_total, ur_class, geometry as geom
        from read_parquet('{couche(region, "strata", "census-tracts")}')
    """)


def transport(con, region):
    con.execute(f"""
        create or replace table tiger as select geometry as geom
        from read_parquet('{couche(region, "reference", "census-tiger-roads")}')
        where MTFCC in {TIGER_AUTOROUTES}
    """)
    con.execute(f"""
        create or replace table overture_r as select geometry as geom
        from read_parquet('{couche(region, "reference", "overture-roads")}')
        where class in {OVERTURE_AUTOROUTES}
    """)
    for nom in ("tiger", "overture_r"):
        con.execute(f"""
            create or replace table km_{nom} as
            select t.GEOID, sum({metres('ST_Intersection(r.geom, t.geom)')}) / 1000 as km
            from tracts t join {nom} r on ST_Intersects(r.geom, t.geom)
            group by t.GEOID
        """)
    con.execute("""
        create or replace table c_transport as
        select t.GEOID,
               coalesce(a.km, 0) as tiger_km, coalesce(b.km, 0) as overture_km,
               coalesce(a.km, 0) > 0 as transport_defined,
               case when coalesce(a.km, 0) > 0
                    then 1 - least(1, coalesce(b.km, 0) / a.km) else 0 end as transport_gap
        from tracts t
        left join km_tiger a on a.GEOID = t.GEOID
        left join km_overture_r b on b.GEOID = t.GEOID
    """)


def centre(p="b"):
    return (f"ST_Point(({p}.bbox.xmin + {p}.bbox.xmax) / 2, "
            f"({p}.bbox.ymin + {p}.bbox.ymax) / 2)")


def compter(con, region, nom, sortie):
    con.execute(f"""
        create or replace table {sortie} as
        select t.GEOID, count(*) as n
        from read_parquet('{couche(region, "reference", nom)}') b
        join tracts t on ST_Within({centre()}, t.geom)
        group by t.GEOID
    """)


def batiment(con, region):
    compter(con, region, "overture-buildings", "n_ovt_bat")
    compter(con, region, "microsoft-buildings", "n_ms_bat")
    con.execute("""
        create or replace table c_batiment as
        select t.GEOID, coalesce(o.n, 0) as ovt_bat, coalesce(m.n, 0) as ms_bat,
               coalesce(m.n, 0) > 0 as building_defined,
               case when coalesce(m.n, 0) > 0
                    then 1 - least(1, coalesce(o.n, 0) / m.n::double) else 0 end as building_gap
        from tracts t
        left join n_ovt_bat o on o.GEOID = t.GEOID
        left join n_ms_bat m on m.GEOID = t.GEOID
    """)


def poi(con, region):
    con.execute(f"""
        create or replace table pois as
        select t.GEOID, b.categories.primary as categorie
        from read_parquet('{couche(region, "reference", "overture-pois")}') b
        join tracts t on ST_Within({centre()}, t.geom)
    """)
    morceaux = []
    for famille, cats in CATEGORIES_HIFLD.items():
        con.execute(f"""
            create or replace table hifld_{famille} as
            select t.GEOID, count(*) as n
            from read_parquet('{couche(region, "reference", COUCHE_HIFLD[famille])}') h
            join tracts t on ST_Within(h.geometry, t.geom)
            group by t.GEOID
        """)
        con.execute(f"""
            create or replace table gap_{famille} as
            select t.GEOID,
                   coalesce(h.n, 0) > 0 as defini,
                   case when coalesce(h.n, 0) > 0
                        then 1 - least(1, coalesce(o.n, 0) / h.n::double) end as gap
            from tracts t
            left join hifld_{famille} h on h.GEOID = t.GEOID
            left join (select GEOID, count(*) n from pois
                       where categorie in {cats} group by GEOID) o on o.GEOID = t.GEOID
        """)
        morceaux.append(famille)

    con.execute(f"""
        create or replace table poi_hifld as
        select t.GEOID,
               list_avg(list_filter([{', '.join(f'g_{m}.gap' for m in morceaux)}],
                                    x -> x is not null)) as gap_hifld
        from tracts t
        {' '.join(f'left join gap_{m} g_{m} on g_{m}.GEOID = t.GEOID' for m in morceaux)}
    """)
    # La table CBP est deja clef par tract, aucune jointure spatiale a faire.
    # Elle porte trois colonnes, le total et sa ventilation residentiel contre
    # entreprise. La page d evaluation dit `all Overture places against Census
    # County Business Patterns establishment counts`, donc le total.
    con.execute(f"""
        create or replace table cbp as
        select GEOID, cbp_estab as etablissements
        from read_parquet('{couche(region, "reference", "census-cbp")}')
    """)
    con.execute("""
        create or replace table poi_cbp as
        select t.GEOID,
               case when coalesce(c.etablissements, 0) > 0
                    then 1 - least(1, coalesce(p.n, 0) / c.etablissements) end as gap_cbp
        from tracts t
        left join cbp c on c.GEOID = t.GEOID
        left join (select GEOID, count(*) n from pois group by GEOID) p on p.GEOID = t.GEOID
    """)
    con.execute("""
        create or replace table c_poi as
        select t.GEOID,
               list_avg(list_filter([h.gap_hifld, c.gap_cbp], x -> x is not null)) as poi_gap_brut
        from tracts t
        left join poi_hifld h on h.GEOID = t.GEOID
        left join poi_cbp c on c.GEOID = t.GEOID
    """)


def composer(con):
    con.execute("""
        create or replace table score as
        select t.GEOID,
               tr.transport_gap, tr.transport_defined,
               ba.building_gap, ba.building_defined,
               coalesce(po.poi_gap_brut, 0) as poi_gap,
               po.poi_gap_brut is not null as poi_defined,
               list_avg(list_filter([
                   case when tr.transport_defined then tr.transport_gap end,
                   case when ba.building_defined then ba.building_gap end,
                   po.poi_gap_brut], x -> x is not null)) as coverage_gap_score
        from tracts t
        join c_transport tr on tr.GEOID = t.GEOID
        join c_batiment ba on ba.GEOID = t.GEOID
        left join c_poi po on po.GEOID = t.GEOID
    """)


def controler(con, region):
    n, sans_t, sans_b, sans_p, au_moins_un, nul = con.sql("""
        select count(*),
               count(*) filter (where not transport_defined),
               count(*) filter (where not building_defined),
               count(*) filter (where not poi_defined),
               count(*) filter (where not transport_defined or not building_defined
                                   or not poi_defined),
               count(*) filter (where coverage_gap_score is null)
        from score
    """).fetchone()
    attendu = PART_INDEFINIE[region]
    print(f"\n{region}, {n} tracts")
    print(f"  transport indefini              {sans_t:>6}  {sans_t / n:>6.1%}")
    print(f"  batiment indefini               {sans_b:>6}  {sans_b / n:>6.1%}")
    print(f"  points d interet indefinis      {sans_p:>6}  {sans_p / n:>6.1%}")
    print(f"  au moins une indefinie          {au_moins_un:>6}  {au_moins_un / n:>6.1%}"
          f"   attendu {attendu:.0%}")
    print(f"  score absent                    {nul:>6}   (doit etre 0)")
    ecart = abs(au_moins_un / n - attendu)
    print(f"  ecart au controle publie        {ecart:>6.1%}"
          f"   {'OK' if ecart <= 0.02 else 'A CREUSER'}")
    print(con.sql("""select round(avg(coverage_gap_score), 4) moyenne,
                            round(median(coverage_gap_score), 4) mediane,
                            round(max(coverage_gap_score), 4) maxi from score""").df()
          .to_string(index=False))


def main():
    region = sys.argv[1] if len(sys.argv) > 1 else "northern-ca"
    con = duckdb.connect(f"score_{region}.duckdb")
    con.execute("LOAD spatial;")
    con.execute("SET memory_limit='8GB';")
    poser_tracts(con, region)
    for etape, fonction in (("transport", transport), ("batiment", batiment),
                            ("points d interet", poi)):
        print(f"  {etape}...", flush=True)
        fonction(con, region)
    composer(con)
    controler(con, region)
    # Meme jeu de colonnes que le fichier d exemple de la region. Les
    # composantes sont facultatives, mais toute colonne incluse doit etre
    # remplie sur CHAQUE ligne, une cellule vide fait rejeter la soumission.
    con.execute(f"""copy (select GEOID, transport_gap, building_gap, poi_gap,
                                 coverage_gap_score
                          from score order by GEOID)
                    to 'soumission_{region}.csv' (header)""")
    print(f"\nsoumission_{region}.csv et score_{region}.duckdb ecrits")
    con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
