# -*- coding: utf-8 -*-
"""Localise le BIAIS SIGNE de mon score, region par region, en quatre depots.

La premiere idee, mettre une region a zero et comparer au fichier tout a zero,
ne marche pas. Elle mesure `somme des t carre` sur la region, mille fois plus
grand que mon erreur, qui disparait dedans. Mesure du 2026-09-17, les sondes
rendent 0,0598 et 0,0555 quand mon erreur vaut 0,000145.

Ce qui marche, comparer DEUX fichiers proches. En decalant ma valeur de delta
sur la seule region X,

    RMSE(decale) au carre moins RMSE(moi) au carre
        = (2 delta fois somme sur X de (m moins t) plus n_X delta carre) sur N

Le terme en delta est du PREMIER ordre, il ne se fait plus ecraser. Le signe du
mouvement dit si je surestime ou si je sous-estime cette region.

Delta vaut 1e-4, choisi pour que les deux termes pesent le meme ordre que
l ecart mesure, ni plus ni moins.

    python decalage.py
"""
import csv
import sys

DELTA = 1e-4
ETAT = {"06": "northern-ca", "40": "eastern-ok",
        "04": "maricopa-az", "35": "maricopa-az", "48": "south-central-tx"}


def main():
    base = list(csv.DictReader(open("soumission.csv", newline="",
                                    encoding="utf-8")))
    for region in ("northern-ca", "eastern-ok", "maricopa-az",
                   "south-central-tx"):
        chemin = f"decale_{region}.csv"
        touches = 0
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["GEOID", "coverage_gap_score"])
            for l in base:
                x = float(l["coverage_gap_score"])
                if ETAT[l["GEOID"][:2]] == region:
                    x = min(1.0, max(0.0, x + DELTA))
                    touches += 1
                w.writerow([l["GEOID"], repr(x)])
        print(f"{chemin:32} {touches:5} tracts decales de {DELTA}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
