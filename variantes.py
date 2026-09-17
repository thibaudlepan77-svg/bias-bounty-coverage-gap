# -*- coding: utf-8 -*-
"""Combien coute chaque convention laissee libre par le texte du concours.

Vingt-neuf concurrents sont empiles sur la valeur unique 3,010e-6 de RMSE et
deux seulement sont a zero. Une erreur partagee par vingt-neuf personnes n est
pas une etourderie, c est une lecture raisonnable du texte qui differe de celle
de l organisateur sur UN point.

Je ne connais pas la verite, je ne peux donc pas mesurer ma distance a elle.
Mais je peux mesurer la distance entre MES PROPRES variantes, et ne retenir
comme suspects que les choix dont l effet a le bon ORDRE DE GRANDEUR. Un choix
qui deplace le score de 1e-2 n est pas ce qui separe le plateau du plafond, un
choix qui le deplace de 1e-6 l est peut-etre.

    python variantes.py northern-ca
"""
import itertools
import math
import sys

import duckdb

# Le classement public ne porte que 30 pour cent du jeu de test. Une difference
# sur un seul tract se lit donc divisee par la racine de cet effectif-la.
PART_PUBLIQUE = 0.30


def rmse(con, a, b):
    v = con.sql(f"""
        select avg(pow(x.{a} - x.{b}, 2)) from variantes x
        where x.{a} is not null and x.{b} is not null
    """).fetchone()[0]
    return math.sqrt(v) if v is not None else None


def main():
    region = sys.argv[1] if len(sys.argv) > 1 else "northern-ca"
    con = duckdb.connect(f"score_{region}.duckdb")
    con.execute("LOAD spatial;")
    con.execute("SET memory_limit='8GB';")
    couche = f"data/{region}/{region}"

    # Variante A, la reference actuelle, deja dans la table score.
    # Variante B, le rattachement des batiments par ST_Intersects au lieu du
    # centre de bbox. Un batiment a cheval sur une limite compte alors deux
    # fois.
    con.execute(f"""
        create or replace table n_ovt_inter as
        select t.GEOID, count(*) as n
        from read_parquet('{couche}-overture-buildings.parquet') b
        join tracts t on ST_Intersects(b.geometry, t.geom) group by t.GEOID
    """)
    con.execute(f"""
        create or replace table n_ms_inter as
        select t.GEOID, count(*) as n
        from read_parquet('{couche}-microsoft-buildings.parquet') b
        join tracts t on ST_Intersects(b.geometry, t.geom) group by t.GEOID
    """)
    # Variante C, la moitie CBP calculee sur les seuls etablissements
    # d entreprise plutot que sur le total.
    con.execute(f"""
        create or replace table cbp_bus as
        select GEOID, cbp_estab_bus as etablissements
        from read_parquet('{couche}-census-cbp.parquet')
    """)

    con.execute("""
        create or replace table variantes as
        select s.GEOID, s.coverage_gap_score as v_reference,
               list_avg(list_filter([
                   case when s.transport_defined then s.transport_gap end,
                   case when coalesce(mi.n, 0) > 0
                        then 1 - least(1, coalesce(oi.n, 0) / mi.n::double) end,
                   case when s.poi_defined then s.poi_gap end], x -> x is not null))
                 as v_intersects,
               list_avg(list_filter([
                   case when s.transport_defined then s.transport_gap end,
                   case when s.building_defined then s.building_gap end,
                   case when cb.etablissements > 0
                        then 1 - least(1, coalesce(p.n, 0) / cb.etablissements) end],
                   x -> x is not null)) as v_cbp_entreprise,
               round(s.coverage_gap_score, 6) as v_arrondi6,
               round(s.coverage_gap_score, 4) as v_arrondi4
        from score s
        left join n_ovt_inter oi on oi.GEOID = s.GEOID
        left join n_ms_inter mi on mi.GEOID = s.GEOID
        left join cbp_bus cb on cb.GEOID = s.GEOID
        left join (select GEOID, count(*) n from pois group by GEOID) p on p.GEOID = s.GEOID
    """)

    colonnes = ["v_reference", "v_intersects", "v_cbp_entreprise",
                "v_arrondi6", "v_arrondi4"]
    n = con.sql("select count(*) from variantes").fetchone()[0]
    effectif_public = max(1, round(n * PART_PUBLIQUE))
    print(f"{region}, {n} tracts, classement public estime a {effectif_public}\n")
    print(f"{'paire':<40}{'RMSE':>12}   ordre")
    for a, b in itertools.combinations(colonnes, 2):
        e = rmse(con, a, b)
        if e is None or e == 0:
            print(f"{a + ' / ' + b:<40}{'identique':>12}")
            continue
        print(f"{a + ' / ' + b:<40}{e:>12.3e}   1e{round(math.log10(e))}")

    print(f"\nEcart sur UN seul tract qui donnerait 3,010e-6 sur le public   "
          f"{3.010e-6 * math.sqrt(effectif_public):.3e}")
    con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
