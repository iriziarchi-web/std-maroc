"""Outils de test : fichier EPW synthétique."""

import math


def epw_synthetique(chemin, t_moy=20.0, amp_an=8.0, amp_jour=7.0):
    """Écrit un EPW minimal : température sinusoïdale (jour et année), autres champs plausibles."""
    entete = [
        "LOCATION,Testville,-,MAR,Synthetique,000000,30.38,-9.57,0.0,23.0",
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,1,2.0,,,," + ",".join(f"{t_moy + 3 * math.sin(2 * math.pi * (m - 4) / 12):.1f}"
                                                   for m in range(12)),
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,synthetique",
        "COMMENTS 2,synthetique",
        "DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31",
    ]
    jours = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    lignes, h = [], 0
    for mois, nj in enumerate(jours, start=1):
        for jour in range(1, nj + 1):
            for heure in range(1, 25):
                t = (t_moy - amp_an * math.cos(2 * math.pi * (h / 8760 - 0.04))
                     - amp_jour * math.cos(2 * math.pi * (heure - 3) / 24))
                champs = [2020, mois, jour, heure, 60, "?9?9?9?9E0?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9*9*9?9?9?9",
                          f"{t:.1f}", "5.0", "40", "101300", "0", "0", "300", "0", "0", "0",
                          "0", "0", "0", "0", "180", "3.0", "0", "0", "20.0", "77777", "9", "999999999",
                          "0", "0.1", "0", "88", "0", "0", "0"]
                lignes.append(",".join(str(c) for c in champs))
                h += 1
    with open(chemin, "w", encoding="latin-1") as f:
        f.write("\n".join(entete + lignes) + "\n")
