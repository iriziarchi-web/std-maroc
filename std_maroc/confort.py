"""Indicateurs de confort d'été à partir des températures horaires.

Méthode : confort adaptatif de la norme EN 16798-1 (catégorie II, bâtiment sans climatisation).
  T_confort = 0,33 x T_rm + 18,8
  limite haute = T_confort + 3 ; limite basse = T_confort - 4
  T_rm : moyenne glissante pondérée des températures extérieures journalières (alpha = 0,8).
La norme limite le modèle à 10 °C <= T_rm <= 30 °C ; on borne T_rm à cet intervalle.
"""

from dataclasses import asdict, dataclass

ALPHA = 0.8
JOURS_MOIS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MOIS_ETE = (6, 7, 8, 9)  # juin à septembre


def mois_de_chaque_heure():
    res = []
    for m, j in enumerate(JOURS_MOIS, start=1):
        res += [m] * (24 * j)
    return res


def moyenne_glissante(t_ext_horaire):
    """T_rm pour chacun des 365 jours. On boucle deux fois sur l'année pour ne pas dépendre de la valeur
    de départ."""
    journalieres = [sum(t_ext_horaire[24 * d: 24 * d + 24]) / 24 for d in range(365)]
    trm = journalieres[-1]
    for _ in range(2):
        res = []
        for t_hier in [journalieres[-1]] + journalieres[:-1]:
            trm = (1 - ALPHA) * t_hier + ALPHA * trm
            res.append(trm)
    return res


def limites_adaptatives(t_ext_horaire):
    """Limites haute et basse (°C) heure par heure."""
    hautes, basses = [], []
    for trm in moyenne_glissante(t_ext_horaire):
        tc = 0.33 * min(max(trm, 10.0), 30.0) + 18.8
        hautes += [tc + 3] * 24
        basses += [tc - 4] * 24
    return hautes, basses


@dataclass
class Indicateurs:
    heures_chaud: int  # heures au-dessus de la limite adaptative haute, sur l'année
    heures_chaud_ete: int  # idem, de juin à septembre
    degres_heures_chaud: float  # somme des dépassements (°C.h)
    heures_sup_28: int  # heures où la température opérative dépasse 28 °C
    heures_froid: int  # heures sous la limite adaptative basse
    t_max: float
    t_min: float
    amplitude_ete: float  # amplitude journalière intérieure moyenne en été (°C)
    amplitude_ext_ete: float  # amplitude journalière extérieure moyenne en été (°C)

    def en_dict(self):
        return asdict(self)


def calculer(t_operative, t_exterieure):
    """t_operative, t_exterieure : 8760 valeurs horaires (°C)."""
    if len(t_operative) != 8760 or len(t_exterieure) != 8760:
        raise ValueError("8760 valeurs horaires attendues")
    hautes, basses = limites_adaptatives(t_exterieure)
    mois = mois_de_chaque_heure()
    chaud = [t > h for t, h in zip(t_operative, hautes)]
    ete = [m in MOIS_ETE for m in mois]

    def amplitude(serie):
        amps = [max(serie[24 * d: 24 * d + 24]) - min(serie[24 * d: 24 * d + 24])
                for d in range(365) if mois[24 * d] in MOIS_ETE]
        return sum(amps) / len(amps)

    return Indicateurs(
        heures_chaud=sum(chaud),
        heures_chaud_ete=sum(c and e for c, e in zip(chaud, ete)),
        degres_heures_chaud=round(sum(max(0.0, t - h) for t, h in zip(t_operative, hautes)), 1),
        heures_sup_28=sum(t > 28 for t in t_operative),
        heures_froid=sum(t < b for t, b in zip(t_operative, basses)),
        t_max=round(max(t_operative), 1),
        t_min=round(min(t_operative), 1),
        amplitude_ete=round(amplitude(t_operative), 1),
        amplitude_ext_ete=round(amplitude(t_exterieure), 1),
    )


def semaine_la_plus_chaude(t_exterieure):
    """Indice de la première heure de la semaine (7 jours) la plus chaude à l'extérieur."""
    journalieres = [sum(t_exterieure[24 * d: 24 * d + 24]) / 24 for d in range(365)]
    debut = max(range(365 - 7), key=lambda d: sum(journalieres[d: d + 7]))
    return debut * 24
