"""Bibliothèque des matériaux, parois et zones climatiques."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DONNEES = Path(__file__).parent / "donnees"

# Résistances superficielles (m2.K/W), valeurs conventionnelles pour une paroi verticale.
RSI_MUR = 0.13
RSE_MUR = 0.04


def _charger(nom):
    with open(DONNEES / nom, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def materiaux():
    return _charger("materiaux.json")["materiaux"]


@lru_cache(maxsize=None)
def parois():
    return _charger("parois.json")


@lru_cache(maxsize=None)
def zones():
    return _charger("climats.json")["zones"]


def zone_par_ville(cle):
    """Retourne (code de zone, données) pour une clé de ville comme 'agadir'."""
    for code, z in zones().items():
        if z["cle"] == cle:
            return code, z
    raise KeyError(f"Ville inconnue : {cle}. Villes connues : {[z['cle'] for z in zones().values()]}")


@dataclass
class Paroi:
    cle: str
    nom: str
    couches: list  # [(clé matériau, épaisseur m)], de l'extérieur vers l'intérieur

    @property
    def epaisseur(self):
        return sum(e for _, e in self.couches)

    @property
    def resistance(self):
        """Résistance thermique des couches seules (m2.K/W)."""
        return sum(e / materiaux()[m]["lambda"] for m, e in self.couches)

    @property
    def u(self):
        """Coefficient U d'un mur avec résistances superficielles (W/m2.K)."""
        return 1.0 / (RSI_MUR + self.resistance + RSE_MUR)

    @property
    def masse_surfacique(self):
        """Masse surfacique (kg/m2)."""
        return sum(e * materiaux()[m]["rho"] for m, e in self.couches)

    @property
    def capacite_surfacique(self):
        """Capacité thermique surfacique (kJ/m2.K)."""
        mat = materiaux()
        return sum(e * mat[m]["rho"] * mat[m]["cp"] for m, e in self.couches) / 1000.0


def paroi(famille, cle):
    """famille : 'murs', 'toitures' ou 'planchers'."""
    d = parois()[famille][cle]
    return Paroi(cle, d["nom"], [tuple(c) for c in d["couches"]])
