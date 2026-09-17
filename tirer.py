"""Rapatrie les couches du concours depuis le depot public Source Cooperative.

Aucune authentification. Le depot expose un listing S3, donc on ne devine aucun
nom de fichier, on lit l inventaire et on filtre dessus. La version precedente
devinait, et elle demandait `census-tracts` dans `reference/` alors que la
couche est dans `strata/`.

On laisse de cote les archives `bulk-downloads`, qui sont les memes octets en
double, et les routes `-unfiltered`, que la page d evaluation n utilise pas.

Reprend un fichier partiel plutot que de le refaire, la connexion d ici tombe
assez souvent pour que ca compte.

    python tirer.py                tout, les quatre regions
    python tirer.py northern-ca    une seule region
"""
import os
import re
import sys
import time
import urllib.error
import urllib.request

DEPOT = "https://data.source.coop/humane-intelligence"
PREFIXE = "bias-bounty-mapping-equity-challenge"
REGIONS = ["northern-ca", "eastern-ok", "maricopa-az", "south-central-tx"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# Le CSV et le parquet portent la meme donnee. On prend le parquet, sauf pour
# les tables de strates ou le CSV sert de controle de lecture des colonnes.
def retenu(cle, regions):
    if "/bulk-downloads/" in cle:
        return False
    if "-unfiltered" in cle:
        return False
    if cle.endswith("/README.md") or "/boundaries/" in cle:
        return True
    if not cle.endswith(".parquet") and not cle.endswith("sample-submission.csv"):
        return False
    return any(f"/{r}/" in cle for r in regions)


def inventaire():
    url = f"{DEPOT}/{PREFIXE}/?list-type=2&max-keys=1000"
    xml = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90
    ).read().decode()
    return [(c, int(t)) for c, t in
            re.findall(r"<Key>(.*?)</Key>.*?<Size>(\d+)</Size>", xml, re.S)]


def local(cle):
    reste = cle[len(PREFIXE) + 1:]
    morceaux = reste.split("/")
    if len(morceaux) == 3:
        _, region, nom = morceaux
        return os.path.join("data", region, nom)
    return os.path.join("data", *morceaux)


def tirer(cle, attendu, essais=5):
    url = f"{DEPOT}/{cle}"
    chemin = local(cle)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    if os.path.exists(chemin) and os.path.getsize(chemin) == attendu:
        return "deja la"
    # Un fichier PLUS GROS que la taille annoncee est faux et ne se repare pas
    # par reprise, la boucle sortait dessus sans rien faire et le laissait
    # casser un lecteur de parquet trois jours plus tard. On repart de zero.
    if os.path.exists(chemin) and os.path.getsize(chemin) > attendu:
        os.remove(chemin)
    for essai in range(essais):
        depart = os.path.getsize(chemin) if os.path.exists(chemin) else 0
        if depart >= attendu:
            break
        entetes = {"User-Agent": UA}
        if depart:
            entetes["Range"] = f"bytes={depart}-"
        try:
            req = urllib.request.Request(url, headers=entetes)
            with urllib.request.urlopen(req, timeout=120) as r:
                # Le depot sert parfois la reponse ENTIERE malgre l en-tete
                # Range. Ajouter ce corps a un fichier partiel le gonfle
                # au-dela de sa taille reelle et le corrompt en silence.
                # Le code 206 seul ne suffit pas a se proteger, il a ete
                # renvoye avec un corps complet le 2026-09-11 sur
                # eastern-ok-microsoft-buildings, 284 194 643 octets ecrits
                # pour 271 611 731 attendus. On exige donc que l en-tete
                # Content-Range annonce EXACTEMENT l octet demande.
                plage = r.headers.get("Content-Range", "")
                reprise = bool(depart) and r.status == 206 and \
                    plage.startswith(f"bytes {depart}-")
                with open(chemin, "ab" if reprise else "wb") as f:
                    while True:
                        bloc = r.read(1 << 20)
                        if not bloc:
                            break
                        f.write(bloc)
            if os.path.getsize(chemin) > attendu:
                # Ceinture et bretelles. Un fichier trop gros est faux, et le
                # garder ferait echouer un lecteur de parquet trois heures plus
                # tard, loin de la cause.
                os.remove(chemin)
                continue
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print(f"    reprise {essai + 1}/{essais} apres {type(e).__name__}", flush=True)
            time.sleep(3 * (essai + 1))
    taille = os.path.getsize(chemin) if os.path.exists(chemin) else 0
    return "ok" if taille == attendu else f"INCOMPLET {taille}/{attendu}"


def main():
    regions = sys.argv[1:] or REGIONS
    cles = [(c, t) for c, t in inventaire() if retenu(c, regions)]
    total = sum(t for _, t in cles)
    print(f"{len(cles)} fichiers, {total / 1e9:.2f} Go, regions {', '.join(regions)}\n",
          flush=True)
    fait = 0
    for cle, taille in sorted(cles, key=lambda ct: ct[1]):
        etat = tirer(cle, taille)
        fait += taille
        print(f"  [{fait / total:>5.1%}] {taille / 1e6:>8.1f} Mo  {etat:<12} "
              f"{cle[len(PREFIXE) + 1:]}", flush=True)
    manquants = [c for c, t in cles
                 if not os.path.exists(local(c)) or os.path.getsize(local(c)) != t]
    print(f"\n{len(cles) - len(manquants)}/{len(cles)} complets")
    if manquants:
        print("MANQUANTS")
        for c in manquants:
            print("   ", c)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
