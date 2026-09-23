# -*- coding: utf-8 -*-
"""Les trois cas limites que nomme le prix de documentation, et deux ponderations.

Tracts sans population, tracts ou l eau domine, tracts sans aucune donnee
Overture. Pour chacun, combien il y en a et ce que score.py leur donne. Puis ce
que deviendrait le composite avec un diviseur fixe a 3, ou pondere par la
population, mesure sur le rang des tracts et pas seulement sur la moyenne.

Lecture seule sur les fichiers score_<region>.duckdb laisses par score.py et sur
la couche des tracts deja rapatriee par tirer.py.

    python cas_limites.py > cas_limites.txt
"""
import sys

import duckdb

REGIONS = ["northern-ca", "eastern-ok", "maricopa-az", "south-central-tx"]


def ligne(titre, valeur):
    print(f"  {titre:<58}{valeur}")


def region(nom):
    con = duckdb.connect(f"score_{nom}.duckdb", read_only=True)
    con.execute(f"""create temp view t as
        select s.*, x.pop_total, x.ALAND, x.ur_class from score s
        join read_parquet('data/{nom}/{nom}-census-tracts.parquet') x using (GEOID)""")
    n = con.sql("select count(*) from t").fetchone()[0]
    print(f"\n{nom}, {n} tracts")

    sans_pop, def_sans_pop, moy_sans_pop = con.sql("""
        select count(*),
               count(*) filter (where transport_defined or building_defined or poi_defined),
               round(avg(coverage_gap_score), 4)
        from t where coalesce(pop_total, 0) = 0""").fetchone()
    ligne("population nulle", sans_pop)
    ligne("  dont au moins une composante definie", def_sans_pop)
    ligne("  score moyen de ces tracts", moy_sans_pop)

    sans_terre, rien_defini = con.sql("""
        select count(*) filter (where coalesce(ALAND, 0) = 0),
               count(*) filter (where coalesce(ALAND, 0) = 0
                                and not transport_defined and not building_defined
                                and not poi_defined)
        from t""").fetchone()
    ligne("surface terrestre nulle (ALAND = 0)", sans_terre)
    ligne("  dont aucune composante definie", rien_defini)

    vide, vide_score = con.sql("""
        select count(*), round(avg(coverage_gap_score), 4)
        from t
        join c_transport using (GEOID) join c_batiment using (GEOID)
        where overture_km = 0 and ovt_bat = 0""").fetchone()
    ligne("ni route ni batiment Overture", vide)
    ligne("  score moyen de ces tracts", vide_score)
    trois, deux, un, zero = con.sql("""
        select count(*) filter (where k = 3), count(*) filter (where k = 2),
               count(*) filter (where k = 1), count(*) filter (where k = 0)
        from (select transport_defined::int + building_defined::int
                     + poi_defined::int as k from t)""").fetchone()
    ligne("composantes definies, 3 / 2 / 1 / 0", f"{trois} / {deux} / {un} / {zero}")

    # Diviseur fixe a 3, une composante indefinie comptee 0, lecture que la page
    # d evaluation exclut mais que plusieurs concurrents ont essayee.
    ecart3, rho3 = con.sql("""
        with v as (
            select coverage_gap_score as ref,
                   (case when transport_defined then transport_gap else 0 end
                    + case when building_defined then building_gap else 0 end
                    + case when poi_defined then poi_gap else 0 end) / 3 as fixe
            from t where coverage_gap_score is not null)
        select round(avg(abs(ref - fixe)), 4), round(corr(r1, r2), 3)
        from (select ref, fixe, rank() over (order by ref) r1,
                     rank() over (order by fixe) r2 from v)""").fetchone()
    ligne("diviseur fixe 3, ecart moyen absolu au composite", ecart3)
    ligne("diviseur fixe 3, correlation des rangs", rho3)

    urbain, rural = con.sql("""
        select round(avg(coverage_gap_score) filter (where ur_class = 'Urban'), 4),
               round(avg(coverage_gap_score) filter (where ur_class = 'Rural'), 4)
        from t""").fetchone()
    pond = con.sql("""
        select round(sum(coverage_gap_score * pop_total) / sum(pop_total), 4)
        from t where coverage_gap_score is not null and pop_total > 0""").fetchone()[0]
    moyen = con.sql("select round(avg(coverage_gap_score), 4) from t").fetchone()[0]
    ligne("moyenne par tract / ponderee par la population", f"{moyen} / {pond}")
    ligne("moyenne urbain / rural", f"{urbain} / {rural}")
    con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for nom in REGIONS:
        region(nom)
