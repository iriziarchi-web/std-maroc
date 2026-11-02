"""Lecture des fichiers météo EPW et téléchargement depuis climate.onebuilding.org."""

import io
import re
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

ONEBUILDING_MAROC = "https://climate.onebuilding.org/WMO_Region_1_Africa/MAR_Morocco/"


@dataclass
class Meteo:
    ville: str
    latitude: float
    longitude: float
    fuseau: float
    altitude: float
    temperature_sol: list  # 12 valeurs mensuelles (°C)
    temperature_ext: list  # 8760 valeurs horaires (°C)


def lire_epw(chemin):
    """Lit l'en-tête et la température sèche horaire d'un fichier EPW."""
    lignes = Path(chemin).read_text(encoding="latin-1").splitlines()
    loc = lignes[0].split(",")
    ville = loc[1]
    lat, lon, fuseau, alt = (float(x) for x in loc[6:10])

    temperature_ext = []
    sol = None
    for ligne in lignes:
        champs = ligne.split(",")
        if champs[0] == "GROUND TEMPERATURES":
            sol = _temperatures_sol(champs)
        elif re.match(r"^\d{4}$", champs[0]) and len(champs) > 6:
            temperature_ext.append(float(champs[6]))

    if len(temperature_ext) < 8760:
        raise ValueError(f"{chemin} : {len(temperature_ext)} heures lues, 8760 attendues")
    temperature_ext = temperature_ext[:8760]
    if sol is None:
        sol = _moyennes_mensuelles(temperature_ext)
    return Meteo(ville, lat, lon, fuseau, alt, sol, temperature_ext)


def _temperatures_sol(champs):
    """Prend la profondeur la plus grande disponible, plus proche du sol sous un dallage.

    Format : GROUND TEMPERATURES, n, puis pour chaque profondeur :
    profondeur, conductivité, masse volumique, chaleur spécifique, 12 valeurs.
    """
    try:
        n = int(champs[1])
    except (ValueError, IndexError):
        return None
    blocs = []
    for i in range(n):
        debut = 2 + i * 16
        valeurs = champs[debut + 4: debut + 16]
        if len(valeurs) == 12 and all(v.strip() for v in valeurs):
            blocs.append((float(champs[debut]), [float(v) for v in valeurs]))
    if not blocs:
        return None
    return max(blocs)[1]


def _moyennes_mensuelles(horaire):
    jours = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    res, h = [], 0
    for j in jours:
        bloc = horaire[h: h + 24 * j]
        res.append(sum(bloc) / len(bloc))
        h += 24 * j
    return res


def telecharger_epw(recherche, destination, index_url=ONEBUILDING_MAROC):
    """Télécharge le fichier TMYx le plus récent d'une ville depuis climate.onebuilding.org.

    Retourne le chemin du fichier écrit.
    """
    with urllib.request.urlopen(index_url, timeout=60) as r:
        page = r.read().decode("utf-8", "replace")
    liens = re.findall(r'href="([^"]+\.zip)"', page)
    candidats = [l for l in liens if recherche.lower() in l.lower() and "TMYx" in l]
    if not candidats:
        raise FileNotFoundError(f"Aucun fichier TMYx trouvé pour « {recherche} » sur {index_url}")
    # Préfère la période la plus récente (ex. TMYx.2009-2023 avant TMYx).
    candidats.sort(key=lambda l: (len(re.findall(r"\d{4}-\d{4}", l)) > 0, l), reverse=True)
    url = urllib.request.urljoin(index_url, candidats[0])
    with urllib.request.urlopen(url, timeout=120) as r:
        contenu = r.read()
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        nom_epw = next(n for n in z.namelist() if n.lower().endswith(".epw"))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(z.read(nom_epw))
    return destination
