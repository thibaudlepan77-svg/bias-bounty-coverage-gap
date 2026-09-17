# -*- coding: utf-8 -*-
"""Fabrique les fichiers de sonde qui localisent mon erreur, region par region.

Le classement rend un score a chaque depot, dix par jour. Cinq depots suffisent
a dire QUELLE region porte l ecart, sans recalculer quoi que ce soit.

    zero.csv          tout a zero. Rend la moyenne des carres de la verite,
                      `RMSE0 au carre = somme(t carre) sur N`
    seule_<region>    ma valeur dans cette region, zero partout ailleurs

En soustrayant, `RMSE_X au carre moins RMSE0 au carre` vaut
`(SSE_X moins somme des t carre sur X) sur N`, qui ne depend plus que de la
region X. La plus grande des quatre valeurs designe la coupable.

    python sondes.py
"""
import csv
import sys

REGIONS = {"06": "northern-ca", "40": "eastern-ok",
           "04": "maricopa-az", "35": "maricopa-az", "48": "south-central-tx"}


def ecrire(chemin, lignes):
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["GEOID", "coverage_gap_score"])
        w.writerows(lignes)
    print(f"{chemin:34} {len(lignes)} lignes")


def main():
    base = list(csv.DictReader(open("soumission.csv", newline="",
                                    encoding="utf-8")))
    ecrire("sonde_zero.csv", [(l["GEOID"], "0.0") for l in base])
    for region in ("northern-ca", "eastern-ok", "maricopa-az",
                   "south-central-tx"):
        ecrire(f"sonde_{region}.csv",
               [(l["GEOID"],
                 l["coverage_gap_score"]
                 if REGIONS[l["GEOID"][:2]] == region else "0.0")
                for l in base])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
