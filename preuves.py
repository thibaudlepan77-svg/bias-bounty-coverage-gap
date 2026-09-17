# -*- coding: utf-8 -*-
"""Toutes les preuves du dossier, en une commande et dans l ordre du texte.

Ce que produit ce fichier est exactement ce que le texte de methode affirme.
Un juge qui le lance doit retrouver chaque nombre cite, a la decimale pres, et
rien d autre ne doit etre a chercher ailleurs.

Prealables, dans cet ordre.
    python score.py <region>              pour les quatre regions
    python provenance.py                  provenance des batiments
    python provenance_poi.py              provenance des points d interet
    python preuves.py > preuves.txt

    python preuves.py
"""
import sys

import duckdb

from score import REGIONS

GEL = {"northern-ca": "2023-09-08", "eastern-ok": "2024-07-01",
       "maricopa-az": "2023-09-01", "south-central-tx": "2024-02-22"}


def terrain(con, region):
    con.execute(f"""
        create or replace table terrain as
        select s.GEOID, s.building_gap, s.poi_gap, s.coverage_gap_score,
               s.building_defined, s.poi_defined,
               b.n_bat, b.n_osm, b.n_ms, b.n_esri, r.n as n_ms_ref,
               b.n_osm::double / nullif(b.n_bat, 0) as part_osm,
               b.n_esri::double / nullif(b.n_bat, 0) as part_esri,
               1 - least(1, b.n_ms::double / nullif(r.n, 0)) as derive_ms,
               q.n_poi, q.n_meta::double / nullif(q.n_poi, 0) as part_meta,
               case when st.ur_class ilike 'rural%' then 'Rural' else 'Urbain' end as classe,
               st.pop_total, st.svi_overall, st.tribal_any, st.COUNTYFP
        from score s
        join provenance b on b.GEOID = s.GEOID
        join provenance_poi q on q.GEOID = s.GEOID
        join n_ms_bat r on r.GEOID = s.GEOID
        join read_parquet('data/{region}/{region}-strata-tract-table.parquet') st
             on st.GEOID = s.GEOID
    """)


def melange(cons):
    print("## 1. Le melange amont varie d une region a l autre, d un facteur cinq\n")
    print("  region             batiments      OSM      Microsoft   Esri"
          "   gel Microsoft")
    for region, con in cons.items():
        n, o, m, e = con.execute("""
            select sum(n_bat), sum(n_osm)::double / sum(n_bat),
                   sum(n_ms)::double / sum(n_bat), sum(n_esri)::double / sum(n_bat)
            from terrain""").fetchone()
        print(f"  {region:18} {n:9}    {o:.3f}      {m:.3f}    {e:.3f}"
              f"   {GEL[region]}")
    print("\n  La couche Microsoft de reference du concours est celle de fevrier")
    print("  2026. Aucun lot Microsoft transporte par Overture n atteint 2025.")


def quartiles(cons):
    print("\n\n## 2. L ecart suit la part OpenStreetMap, et il la suit DANS chaque"
          " classe\n")
    for region, con in cons.items():
        print(f"  {region}")
        print("    classe   q      n   part OSM   ecart batiment   ecart POI")
        cadre = con.execute("""
            select classe, part_osm, building_gap, poi_gap,
                   ntile(4) over (partition by classe order by part_osm) as q
            from terrain where part_osm is not null and building_defined
        """).df()
        for cl, q, n, po, eb, ep in cadre.groupby(["classe", "q"]).agg(
                n=("part_osm", "size"), po=("part_osm", "mean"),
                eb=("building_gap", "mean"), ep=("poi_gap", "mean")
        ).reset_index().itertuples(index=False):
            print(f"    {cl:7}  {q}  {n:5}     {po:.3f}        {eb:.4f}"
                  f"        {ep:.4f}")
        print()


def poi_independant(cons):
    print("\n## 3. La part OSM des BATIMENTS predit l ecart sur les POINTS"
          " D INTERET,\n   qui ne doivent rien a OpenStreetMap\n")
    print("  region             q1 ecart POI   q4 ecart POI   rapport"
          "   part meta q1   part meta q4")
    for region, con in cons.items():
        cadre = con.execute("""
            select part_osm, poi_gap, part_meta,
                   ntile(4) over (order by part_osm) as q
            from terrain where part_osm is not null and poi_defined
        """).df().groupby("q").agg(ep=("poi_gap", "mean"),
                                   pm=("part_meta", "mean"))
        a, d = cadre.loc[1, "ep"], cadre.loc[4, "ep"]
        print(f"  {region:18}     {a:.4f}         {d:.4f}     {a / d:5.2f}"
              f"        {cadre.loc[1, 'pm']:.3f}          {cadre.loc[4, 'pm']:.3f}")


def source_unique(cons):
    print("\n\n## 4. Les tracts qu une seule source amont porte, et leur ecart\n")
    print("  region             tracts a source unique   habitants   ecart"
          "   ecart ailleurs")
    for region, con in cons.items():
        k, pop, eb = con.execute("""
            select count(*), sum(pop_total), avg(building_gap) from terrain
            where building_defined and n_bat > 50
              and greatest(n_osm, n_ms, n_esri)::double / n_bat > 0.95""").fetchone()
        autre = con.execute("""
            select avg(building_gap) from terrain
            where building_defined and n_bat > 50
              and greatest(n_osm, n_ms, n_esri)::double / n_bat <= 0.95""").fetchone()[0]
        print(f"  {region:18} {k:20}   {pop or 0:9}   {eb:.4f}   {autre:.4f}")


def derive(cons):
    print("\n\n## 5. La derive de millesime, la ou elle est lisible\n")
    print("  Lisible seulement sous une part OSM faible. Ailleurs Overture")
    print("  REMPLACE l empreinte Microsoft par celle du benevole, et la mesure")
    print("  ne parlerait plus du temps.\n")
    print("  region             tracts   derive   ecart note   habitants")
    for region, con in cons.items():
        k, d, g, pop = con.execute("""
            select count(*), avg(derive_ms), avg(building_gap), sum(pop_total)
            from terrain where part_osm < 0.05 and n_ms_ref > 100
              and building_defined""").fetchone()
        print(f"  {region:18} {k:6}   {d:.4f}   {g:.4f}   {pop or 0:9}")


def nommer(cons):
    print("\n\n## 6. Les tracts nommes, ecart batiment le plus fort sous une part"
          " OSM faible\n")
    for region, con in cons.items():
        print(f"  {region}")
        print("    GEOID        comte   Overture   Microsoft   ecart   habitants")
        for g, c, nb, nr, eb, pop in con.execute("""
            select GEOID, COUNTYFP, n_bat, n_ms_ref, building_gap, pop_total
            from terrain where part_osm < 0.05 and n_ms_ref > 200
              and building_defined
            order by building_gap desc limit 8""").fetchall():
            print(f"    {g}     {c}   {nb:8}   {nr:9}   {eb:.4f}   {pop or 0:8}")
        print()


def vulnerabilite(cons):
    print("\n## 7. Qui vit dans ces tracts, vulnerabilite sociale et terres"
          " tribales\n")
    print("  region             part OSM sous 0,05          reste")
    print("                     SVI moyen   tribal      SVI moyen   tribal")
    for region, con in cons.items():
        bas = con.execute("""
            select avg(svi_overall), avg(case when tribal_any then 1.0 else 0 end)
            from terrain where part_osm < 0.05 and building_defined""").fetchone()
        haut = con.execute("""
            select avg(svi_overall), avg(case when tribal_any then 1.0 else 0 end)
            from terrain where part_osm >= 0.05 and building_defined""").fetchone()
        print(f"  {region:18}    {bas[0] or 0:.3f}     {bas[1]:.3f}"
              f"         {haut[0] or 0:.3f}     {haut[1]:.3f}")


def main():
    cons = {}
    for region in REGIONS:
        con = duckdb.connect(f"score_{region}.duckdb")
        terrain(con, region)
        cons[region] = con
    melange(cons)
    quartiles(cons)
    poi_independant(cons)
    source_unique(cons)
    derive(cons)
    nommer(cons)
    vulnerabilite(cons)
    for con in cons.values():
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
