# STD Maroc

Logiciel de simulation thermique dynamique (STD) adapté au contexte marocain, construit sur le moteur
[EnergyPlus](https://energyplus.net). Il apporte ce qu'EnergyPlus n'a pas d'origine : les zones climatiques
du RTCM, une bibliothèque de matériaux locaux (pisé, adobe, BTC, pierre, enduits terre et chaux, tadelakt),
une saisie simple en français et des résultats de confort d'été destinés au futur label marocain des
matériaux locaux.

## Prototype 1

Une maison de plain-pied de 10 m x 10 m, sans climatisation, simulée sur une année à Agadir (zone Z1) et à
Errachidia (zone Z6). Quatre murs sont comparés, avec et sans ventilation nocturne :

| Mur | U (W/m².K) | Masse (kg/m²) |
| --- | --- | --- |
| Pisé 50 cm, enduits terre | 1,29 | 1 018 |
| Adobe 40 cm, enduits terre | 1,26 | 708 |
| Pierre 50 cm, enduits chaux | 1,95 | 1 164 |
| Parpaing 20 cm, enduit ciment (référence) | 2,20 | 254 |

Le confort est évalué selon le modèle adaptatif de la norme EN 16798-1 (catégorie II). Le rapport PDF donne,
pour chaque variante, les heures d'inconfort, les heures au-dessus de 28 °C, la température maximale et
l'amplitude intérieure, ainsi que les courbes de la semaine la plus chaude.

Les propriétés des matériaux sont provisoires (`std_maroc/donnees/materiaux.json`) et doivent être sourcées.

## Utilisation

Prérequis : Python 3.10 ou plus, [EnergyPlus 24.2](https://github.com/NREL/EnergyPlus/releases/tag/v24.2.0a)
installé et accessible dans le PATH (ou via la variable `ENERGYPLUS_EXE`).

```
pip install -r requirements.txt
python -m std_maroc meteo agadir errachidia   # télécharge les fichiers météo
python -m std_maroc prototype                 # lance les 16 simulations et écrit resultats/rapport_prototype_1.pdf
```

Autres commandes :

```
python -m std_maroc parois                               # caractéristiques des parois
python -m std_maroc generer --ville agadir --mur pise_50 # écrit le modèle EnergyPlus sans le lancer
python -m unittest -v                                    # tests
```

Sans rien installer, la simulation peut aussi tourner sur GitHub : onglet **Actions**, « Simulation
prototype 1 », **Run workflow**. Le rapport PDF est ensuite téléchargeable dans les artefacts de l'exécution.

## Organisation

| Fichier | Rôle |
| --- | --- |
| `std_maroc/donnees/` | matériaux, parois, zones climatiques RTCM |
| `std_maroc/modele.py` | traduit la description du bâtiment en modèle EnergyPlus (epJSON) |
| `std_maroc/simulation.py` | lance EnergyPlus et lit les résultats |
| `std_maroc/confort.py` | indicateurs de confort d'été (EN 16798-1) |
| `std_maroc/rapport.py` | rapport PDF en français |
| `std_maroc/meteo.py` | lecture et téléchargement des fichiers EPW |

## Limites connues

- Une seule zone thermique, géométrie en boîte.
- Transferts d'humidité dans la terre non modélisés.
- Fichiers météo TMYx publics ; des années types officielles (DGM, AMEE) seraient préférables.
- Résultats non encore comparés à un autre logiciel (Pleiades/COMFIE prévu) ni à des mesures.
