"""Ligne de commande.

  python -m std_maroc meteo agadir errachidia      télécharge les fichiers météo
  python -m std_maroc generer --ville agadir --mur pise_50   écrit le modèle EnergyPlus sans le lancer
  python -m std_maroc prototype                    lance le prototype 1 et produit le rapport PDF
  python -m std_maroc parois                       liste les parois et leurs caractéristiques
"""

import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path

from . import bibliotheque as bib
from . import confort, meteo, modele, rapport, simulation

RACINE = Path(__file__).resolve().parent.parent
METEO = RACINE / "meteo"
RESULTATS = RACINE / "resultats"

PROTOTYPE_VILLES = ["agadir", "errachidia"]
PROTOTYPE_MURS = ["pise_50", "adobe_40", "pierre_50", "parpaing_20"]


def chemin_epw(cle, dossier=METEO):
    _, z = bib.zone_par_ville(cle)
    p = Path(dossier) / z["fichier_epw"]
    if not p.exists():
        raise FileNotFoundError(f"Fichier météo manquant : {p}. Lancez « python -m std_maroc meteo {cle} » "
                                "ou déposez le fichier EPW à cet endroit.")
    return p


def cmd_meteo(args):
    for cle in args.villes:
        _, z = bib.zone_par_ville(cle)
        dest = METEO / z["fichier_epw"]
        print(f"{z['ville']} : téléchargement…")
        meteo.telecharger_epw(z["recherche_onebuilding"], dest)
        print(f"  écrit {dest}")


def cmd_parois(_args):
    for famille in ("murs", "toitures", "planchers"):
        print(f"\n{famille}")
        for cle in bib.parois()[famille]:
            p = bib.paroi(famille, cle)
            print(f"  {cle:20s} {p.nom:55s} ép. {p.epaisseur * 100:4.0f} cm  U {p.u:4.2f}  "
                  f"masse {p.masse_surfacique:5.0f} kg/m²  C {p.capacite_surfacique:5.0f} kJ/m².K")


def cmd_generer(args):
    m = meteo.lire_epw(chemin_epw(args.ville))
    b = modele.Batiment(mur=args.mur, ventilation_nocturne=not args.sans_ventilation)
    sortie = Path(args.sortie or f"{args.ville}_{args.mur}.epJSON")
    sortie.write_text(json.dumps(modele.construire(b, m), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"écrit {sortie}")


def cmd_prototype(args):
    base = modele.Batiment()
    resultats, semaines = [], {}
    RESULTATS.mkdir(exist_ok=True)
    for cle in args.villes:
        code, z = bib.zone_par_ville(cle)
        m = meteo.lire_epw(chemin_epw(cle))
        ville = z["ville"]
        semaines[ville] = {}
        for mur in args.murs:
            for vent in (True, False):
                b = replace(base, mur=mur, ventilation_nocturne=vent)
                nom = f"{cle}_{mur}_{'vent' if vent else 'sans-vent'}"
                print(f"Simulation {nom}…")
                sql = simulation.lancer(modele.construire(b, m, nom), chemin_epw(cle), RESULTATS / nom)
                t_op = simulation.lire_serie(sql, "Zone Operative Temperature", modele.ZONE)
                t_ext = simulation.lire_serie(sql, "Site Outdoor Air Drybulb Temperature")
                ind = confort.calculer(t_op, t_ext)
                resultats.append({"ville": ville, "zone": code, "mur": mur, "ventilation_nocturne": vent,
                                  "indicateurs": ind.en_dict()})
                if vent:
                    debut = confort.semaine_la_plus_chaude(t_ext)
                    semaines[ville].setdefault("Extérieur", t_ext[debut: debut + 168])
                    semaines[ville][bib.paroi("murs", mur).nom] = t_op[debut: debut + 168]

    with open(RESULTATS / "synthese.csv", "w", newline="", encoding="utf-8") as f:
        champs = ["ville", "zone", "mur", "ventilation_nocturne"] + list(resultats[0]["indicateurs"])
        w = csv.DictWriter(f, fieldnames=champs, delimiter=";")
        w.writeheader()
        for r in resultats:
            w.writerow({k: v for k, v in r.items() if k != "indicateurs"} | r["indicateurs"])
    (RESULTATS / "synthese.json").write_text(json.dumps(resultats, indent=1, ensure_ascii=False), encoding="utf-8")
    rapport.ecrire(RESULTATS / "rapport_prototype_1.pdf", resultats, semaines, base)
    print(f"Rapport : {RESULTATS / 'rapport_prototype_1.pdf'}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="std_maroc", description="Simulation thermique dynamique pour le Maroc")
    sp = p.add_subparsers(dest="commande", required=True)

    a = sp.add_parser("meteo", help="télécharger les fichiers météo EPW")
    a.add_argument("villes", nargs="+")
    a.set_defaults(f=cmd_meteo)

    a = sp.add_parser("parois", help="lister les parois")
    a.set_defaults(f=cmd_parois)

    a = sp.add_parser("generer", help="écrire un modèle EnergyPlus sans le lancer")
    a.add_argument("--ville", required=True)
    a.add_argument("--mur", required=True)
    a.add_argument("--sans-ventilation", action="store_true")
    a.add_argument("--sortie")
    a.set_defaults(f=cmd_generer)

    a = sp.add_parser("prototype", help="lancer le prototype 1")
    a.add_argument("--villes", nargs="+", default=PROTOTYPE_VILLES)
    a.add_argument("--murs", nargs="+", default=PROTOTYPE_MURS)
    a.set_defaults(f=cmd_prototype)

    args = p.parse_args(argv)
    args.f(args)


if __name__ == "__main__":
    main()
