# -*- coding: utf-8 -*-
"""La derive de millesime, la ou elle est lisible, et ce qui la masque ailleurs.

Le lot Microsoft transporte par Overture est fige. La couche Microsoft de
reference est celle de fevrier 2026. Comparer les deux dans le meme tract,
`1 - n_ms / n_ms_ref`, donne la derive de millesime.

CETTE QUANTITE N EST LISIBLE QUE LA OU OVERTURE PORTE ENCORE LE LOT MICROSOFT.
Premiere lecture fausse, corrigee le 2026-09-17. Dans un tract cartographie par
les benevoles, Overture remplace l empreinte Microsoft par celle
d OpenStreetMap, et `1 - n_ms / n_ms_ref` y vaut 0,96 sans que le temps y soit
pour quoi que ce soit. Le chiffre ne parle de duree que sous une part
OpenStreetMap faible, il n est donc publie que la.

Ce qui reste vrai quelle que soit la lecture, et c est le motif. La
contribution benevole monte jusqu au 2026-08-01 dans le meme jeu. Elle rebouche
le trou la ou elle est vive et le laisse ouvert la ou elle est absente. L ecart
note ne classe donc pas les territoires par qualite de carte, il les classe par
activite des benevoles.

    python derive.py
"""
import sys

import duckdb

from score import REGIONS

TRANCHES = ["sous 0,05", "0,05 a 0,50", "0,50 a 0,90", "au-dessus de 0,90"]


def poser(con, region):
    con.execute(f"""
        create or replace table derive as
        select s.GEOID, s.building_gap, p.n_bat, p.n_osm, p.n_ms, r.n as n_ms_ref,
               p.n_osm::double / nullif(p.n_bat, 0) as part_osm,
               1 - least(1, p.n_ms::double / nullif(r.n, 0)) as derive_ms,
               st.pop_total, st.ur_class, st.svi_overall, st.tribal_any,
               st.COUNTYFP
        from score s
        join provenance p on p.GEOID = s.GEOID
        join n_ms_bat r on r.GEOID = s.GEOID
        join read_parquet('data/{region}/{region}-strata-tract-table.parquet') st
             on st.GEOID = s.GEOID
        where s.building_defined and r.n > 100
    """)


def tableau(con, region):
    n, g = con.execute(
        "select count(*), avg(building_gap) from derive").fetchone()
    print(f"\n### {region}, {n} tracts d au moins cent batiments de reference")
    print(f"  ecart batiment note sur toute la region   {g:.4f}")
    print("\n  part OSM             n   ecart note   derive de millesime")
    for tr, k, gg, dd in con.execute(f"""
        select case when part_osm < 0.05 then '{TRANCHES[0]}'
                    when part_osm < 0.50 then '{TRANCHES[1]}'
                    when part_osm < 0.90 then '{TRANCHES[2]}'
                    else '{TRANCHES[3]}' end as tr,
               count(*), avg(building_gap), avg(derive_ms)
        from derive group by 1 order by min(part_osm)
    """).fetchall():
        lu = f"{dd:.4f}" if tr == TRANCHES[0] else "illisible"
        print(f"  {tr:17} {k:5}      {gg:.4f}      {lu}")

    pop, kt = con.execute("""
        select sum(pop_total), count(*) from derive
        where part_osm < 0.05 and derive_ms > 0.02
    """).fetchone()
    print(f"\n  derive ouverte, part OSM sous 0,05 et derive au-dessus de 0,02")
    print(f"    {kt} tracts, {pop or 0} habitants")


def comtes(con, region):
    print(f"\n  les comtes les plus touches, part OSM sous 0,05, dix tracts au moins")
    print("  comte     tracts   habitants   derive   ecart note")
    for c, k, pop, dd, gg in con.execute("""
        select COUNTYFP, count(*), sum(pop_total), avg(derive_ms), avg(building_gap)
        from derive where part_osm < 0.05
        group by 1 having count(*) >= 10 order by avg(derive_ms) desc limit 8
    """).fetchall():
        print(f"  {c:7} {k:7}   {pop or 0:9}   {dd:.4f}   {gg:.4f}")


def main():
    for region in (sys.argv[1:] or REGIONS):
        con = duckdb.connect(f"score_{region}.duckdb")
        if not con.execute("""select count(*) from duckdb_tables()
                              where table_name = 'provenance'""").fetchone()[0]:
            con.close()
            continue
        poser(con, region)
        tableau(con, region)
        comtes(con, region)
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
