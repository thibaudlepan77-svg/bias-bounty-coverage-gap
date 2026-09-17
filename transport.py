"""Composante transport du score de lacune, et son invariant publie.

La page d evaluation donne la clause en une phrase, comparer la longueur de
route Overture par tract a celle de TIGER, classes d autoroute nommee
seulement. Elle donne aussi de quoi se controler, la part de tracts ou au moins
une composante est indefinie, 21 pour cent en Oklahoma oriental, 37 en
Californie du Nord, 28 au Texas, 55 a Maricopa.

On mesure donc deux choses distinctes que j avais confondues dans ma premiere
version, les tracts SANS autoroute nommee TIGER, et les tracts ou au moins une
composante est indefinie. La seconde inclut la premiere et vaut plus.

    python transport.py northern-ca
"""
import sys

import duckdb

DEPOT = ("https://data.source.coop/humane-intelligence/"
         "bias-bounty-mapping-equity-challenge")
TIGER_AUTOROUTES = ("S1100", "S1200")
OVERTURE_AUTOROUTES = ("motorway", "trunk", "primary", "secondary")

# Part de tracts avec au moins une composante indefinie, verbatim de la page
# d evaluation, et effectif scores du README.
ATTENDU = {
    "eastern-ok": (0.21, 1192),
    "northern-ca": (0.37, 591),
    "south-central-tx": (0.28, 6003),
    "maricopa-az": (0.55, 1593),
}


def couche(region, dossier, nom):
    return f"{DEPOT}/{dossier}/{region}/{region}-{nom}.parquet"


def metres(expr):
    """EPSG:5070 en metres. always_xy sinon chaque geometrie revient a l infini,
    sans lever, et la somme finit en inf."""
    return f"ST_Length(ST_Transform({expr}, 'EPSG:4326', 'EPSG:5070', always_xy := true))"


def main():
    region = sys.argv[1] if len(sys.argv) > 1 else "northern-ca"
    con = duckdb.connect()
    con.execute("LOAD spatial;")
    con.execute("SET memory_limit='8GB';")

    con.execute(f"""
        create table tracts as
        select GEOID, ALAND, pop_total, ur_class, geometry as geom
        from read_parquet('{couche(region, "strata", "census-tracts")}')
    """)
    con.execute(f"""
        create table tiger as
        select geometry as geom
        from read_parquet('{couche(region, "reference", "census-tiger-roads")}')
        where MTFCC in {TIGER_AUTOROUTES}
    """)
    con.execute(f"""
        create table overture as
        select geometry as geom
        from read_parquet('{couche(region, "reference", "overture-roads")}')
        where class in {OVERTURE_AUTOROUTES}
    """)

    for nom in ("tracts", "tiger", "overture"):
        print(f"  {nom:<9} {con.sql(f'select count(*) from {nom}').fetchone()[0]:>8}")

    # Une route traverse plusieurs tracts, on mesure la portion interieure et
    # jamais la longueur entiere du troncon.
    for source in ("tiger", "overture"):
        con.execute(f"""
            create table long_{source} as
            select t.GEOID,
                   sum({metres('ST_Intersection(r.geom, t.geom)')}) / 1000.0 as km
            from tracts t join {source} r on ST_Intersects(r.geom, t.geom)
            group by t.GEOID
        """)

    con.execute("""
        create table transport as
        select t.GEOID,
               coalesce(lt.km, 0) as tiger_km,
               coalesce(lo.km, 0) as overture_km,
               coalesce(lt.km, 0) > 0 as transport_defined,
               case when coalesce(lt.km, 0) > 0
                    then 1 - least(1, coalesce(lo.km, 0) / lt.km)
                    else 0 end as transport_gap
        from tracts t
        left join long_tiger lt on lt.GEOID = t.GEOID
        left join long_overture lo on lo.GEOID = t.GEOID
    """)

    n, sans, moyenne = con.sql("""
        select count(*), count(*) filter (where not transport_defined),
               avg(transport_gap) filter (where transport_defined)
        from transport
    """).fetchone()
    part, effectif = ATTENDU[region]
    print(f"\n{region}")
    print(f"  tracts scores            {n:>6}   attendu {effectif}")
    print(f"  sans autoroute TIGER     {sans:>6}   {sans / n:>6.1%}")
    print(f"  borne publiee, au moins une composante indefinie   {part:>5.0%}")
    print(f"  gap transport moyen      {moyenne:>6.3f}")

    nan = con.sql("select count(*) from transport where isnan(tiger_km) or isinf(tiger_km)").fetchone()[0]
    print(f"  longueurs non finies     {nan:>6}   (doit etre 0, sinon always_xy)")
    con.execute(f"copy transport to 'transport_{region}.csv' (header)")
    print(f"  ecrit transport_{region}.csv")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
