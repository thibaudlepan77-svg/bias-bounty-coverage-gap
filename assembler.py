# -*- coding: utf-8 -*-
"""Assemble les quatre regions en une soumission, et refuse de l ecrire si elle
ne colle pas exactement a la liste de tracts notes.

La liste faisant foi est `reference/<region>/<region>-sample-submission.csv`,
pas la couche des tracts. South-central-tx compte sept tracts d eau qui sont
dans la couche et pas dans la liste, et une ligne de trop suffit a faire
rejeter le depot.

    python assembler.py                     pleine precision
    python assembler.py 5                   arrondi a cinq decimales
"""
import csv
import os
import sys

REGIONS = ["northern-ca", "eastern-ok", "maricopa-az", "south-central-tx"]
COLONNES = ["GEOID", "transport_gap", "building_gap", "poi_gap", "coverage_gap_score"]


def lire(chemin):
    with open(chemin, newline="", encoding="utf-8") as f:
        return {l["GEOID"]: l for l in csv.DictReader(f)}


def main():
    decimales = int(sys.argv[1]) if len(sys.argv) > 1 else None
    lignes = []
    for region in REGIONS:
        attendus = list(lire(os.path.join("data", region,
                                          f"{region}-sample-submission.csv")))
        calcules = lire(f"soumission_{region}.csv")
        manquants = [g for g in attendus if g not in calcules]
        surplus = [g for g in calcules if g not in set(attendus)]
        print(f"{region:18} attendus {len(attendus):5}  calcules {len(calcules):5}"
              f"  manquants {len(manquants)}  en trop {len(surplus)}")
        if manquants:
            sys.exit(f"ARRET, {len(manquants)} tracts sans score, {manquants[:5]}")
        if surplus:
            print(f"    {len(surplus)} ecartes, hors liste notee, {surplus[:8]}")
        for geoid in attendus:
            ligne = calcules[geoid]
            valeurs = [geoid]
            for col in COLONNES[1:]:
                x = float(ligne[col])
                if x != x or x < 0 or x > 1:
                    sys.exit(f"ARRET, {geoid} {col} vaut {x}, hors de zero un")
                valeurs.append(repr(round(x, decimales) if decimales else x))
            lignes.append(valeurs)

    sortie = f"soumission_{decimales}dec.csv" if decimales else "soumission.csv"
    with open(sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLONNES)
        w.writerows(lignes)
    print(f"\n{sortie}, {len(lignes)} lignes, {os.path.getsize(sortie)} octets")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
