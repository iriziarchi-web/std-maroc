"""Génération d'un modèle EnergyPlus (epJSON) à partir d'une description simple du bâtiment."""

from dataclasses import dataclass, field

from . import bibliotheque as bib

VERSION_ENERGYPLUS = "24.2"
ZONE = "Logement"


@dataclass
class Batiment:
    """Maison de plain-pied à une zone, en forme de boîte."""

    mur: str = "pise_50"
    toiture: str = "dalle_beton"
    plancher: str = "dallage"
    longueur: float = 10.0  # m, façades sud et nord
    largeur: float = 10.0  # m, façades est et ouest
    hauteur: float = 3.0  # m sous plafond
    orientation: float = 0.0  # degrés, rotation du bâtiment par rapport au nord
    # Part vitrée de chaque façade (surface de baie / surface de façade).
    baies: dict = field(default_factory=lambda: {"sud": 0.15, "nord": 0.15, "est": 0.0, "ouest": 0.0})
    hauteur_baie: float = 1.2
    allege: float = 0.9
    u_vitrage: float = 5.8  # simple vitrage
    facteur_solaire: float = 0.75
    occupants: int = 4
    apports_internes: float = 4.0  # W/m2 (éclairage et équipements, moyenne)
    infiltration: float = 0.5  # vol/h
    ventilation_nocturne: bool = True
    debit_nocturne: float = 5.0  # vol/h quand les fenêtres sont ouvertes la nuit

    @property
    def surface(self):
        return self.longueur * self.largeur


def _materiaux_et_construction(nom, paroi, objets):
    """Ajoute les matériaux et la construction d'une paroi. EnergyPlus attend les couches de l'extérieur
    vers l'intérieur."""
    mats = bib.materiaux()
    noms = []
    for cle, ep in paroi.couches:
        m = mats[cle]
        nom_mat = f"{cle}_{round(ep * 100, 1):g}cm"
        objets["Material"][nom_mat] = {
            "roughness": m["rugosite"],
            "thickness": ep,
            "conductivity": m["lambda"],
            "density": m["rho"],
            "specific_heat": m["cp"],
            "thermal_absorptance": 0.9,
            "solar_absorptance": m["absorption_solaire"],
            "visible_absorptance": m["absorption_solaire"],
        }
        noms.append(nom_mat)
    cons = {"outside_layer": noms[0]}
    for i, n in enumerate(noms[1:], start=2):
        cons[f"layer_{i}"] = n
    objets["Construction"][nom] = cons


def _sommets(points):
    return [{"vertex_x_coordinate": x, "vertex_y_coordinate": y, "vertex_z_coordinate": z} for x, y, z in points]


def geometrie_murs(b):
    """Sommets des quatre murs, ordre anti-horaire vu de l'extérieur, en partant du coin supérieur gauche."""
    L, W, H = b.longueur, b.largeur, b.hauteur
    return {
        "sud": [(0, 0, H), (0, 0, 0), (L, 0, 0), (L, 0, H)],
        "est": [(L, 0, H), (L, 0, 0), (L, W, 0), (L, W, H)],
        "nord": [(L, W, H), (L, W, 0), (0, W, 0), (0, W, H)],
        "ouest": [(0, W, H), (0, W, 0), (0, 0, 0), (0, 0, H)],
    }


def geometrie_baie(b, facade, part):
    """Baie centrée sur la façade, même ordre de sommets que le mur porteur."""
    murs = geometrie_murs(b)
    ul, ll, lr, _ = murs[facade]
    largeur_mur = ((lr[0] - ll[0]) ** 2 + (lr[1] - ll[1]) ** 2) ** 0.5
    surface = part * largeur_mur * b.hauteur
    largeur = min(surface / b.hauteur_baie, largeur_mur - 0.4)
    hauteur = surface / largeur
    z0 = b.allege
    z1 = min(z0 + hauteur, b.hauteur - 0.1)
    ux, uy = (lr[0] - ll[0]) / largeur_mur, (lr[1] - ll[1]) / largeur_mur
    d0 = (largeur_mur - largeur) / 2
    d1 = d0 + largeur

    def p(d, z):
        return (round(ll[0] + ux * d, 4), round(ll[1] + uy * d, 4), z)

    return [p(d0, z1), p(d0, z0), p(d1, z0), p(d1, z1)]


def _horaire_compact(nom_limites, blocs):
    """blocs : liste de (heure 'HH:MM', valeur) pour tous les jours de l'année."""
    data = [{"field": "Through: 12/31"}, {"field": "For: AllDays"}]
    for heure, v in blocs:
        data += [{"field": f"Until: {heure}"}, {"field": v}]
    return {"schedule_type_limits_name": nom_limites, "data": data}


def construire(b, meteo, nom="Simulation"):
    """Retourne le modèle epJSON (dict) d'un bâtiment pour un climat donné."""
    o = {k: {} for k in ("Material", "Construction")}
    o["Version"] = {"Version 1": {"version_identifier": VERSION_ENERGYPLUS}}
    o["SimulationControl"] = {"SimulationControl 1": {
        "do_zone_sizing_calculation": "No",
        "do_system_sizing_calculation": "No",
        "do_plant_sizing_calculation": "No",
        "run_simulation_for_sizing_periods": "No",
        "run_simulation_for_weather_file_run_periods": "Yes",
    }}
    o["Building"] = {nom: {
        "north_axis": b.orientation,
        "terrain": "Suburbs",
        "solar_distribution": "FullExterior",
        "maximum_number_of_warmup_days": 25,
        "minimum_number_of_warmup_days": 6,
    }}
    o["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": 6}}
    o["GlobalGeometryRules"] = {"GlobalGeometryRules 1": {
        "starting_vertex_position": "UpperLeftCorner",
        "vertex_entry_direction": "Counterclockwise",
        "coordinate_system": "Relative",
    }}
    o["Site:Location"] = {meteo.ville or "Site": {
        "latitude": meteo.latitude,
        "longitude": meteo.longitude,
        "time_zone": meteo.fuseau,
        "elevation": meteo.altitude,
    }}
    o["RunPeriod"] = {"Annee": {
        "begin_month": 1, "begin_day_of_month": 1, "end_month": 12, "end_day_of_month": 31,
        "use_weather_file_holidays_and_special_days": "No",
        "use_weather_file_daylight_saving_period": "No",
    }}
    mois = ["january", "february", "march", "april", "may", "june", "july",
            "august", "september", "october", "november", "december"]
    o["Site:GroundTemperature:BuildingSurface"] = {"Sol": {
        f"{m}_ground_temperature": round(t, 2) for m, t in zip(mois, meteo.temperature_sol)
    }}

    # Parois
    _materiaux_et_construction("Mur", bib.paroi("murs", b.mur), o)
    _materiaux_et_construction("Toiture", bib.paroi("toitures", b.toiture), o)
    # Pour le plancher, la « face extérieure » est la face côté sol.
    _materiaux_et_construction("Plancher", bib.paroi("planchers", b.plancher), o)
    o["WindowMaterial:SimpleGlazingSystem"] = {"Vitrage": {
        "u_factor": b.u_vitrage, "solar_heat_gain_coefficient": b.facteur_solaire, "visible_transmittance": 0.8,
    }}
    o["Construction"]["Fenetre"] = {"outside_layer": "Vitrage"}

    # Zone et surfaces
    o["Zone"] = {ZONE: {"x_origin": 0, "y_origin": 0, "z_origin": 0, "ceiling_height": b.hauteur,
                        "volume": b.surface * b.hauteur, "floor_area": b.surface}}
    L, W, H = b.longueur, b.largeur, b.hauteur
    surfaces = {}
    for facade, pts in geometrie_murs(b).items():
        surfaces[f"Mur_{facade}"] = {
            "surface_type": "Wall", "construction_name": "Mur", "zone_name": ZONE,
            "outside_boundary_condition": "Outdoors", "sun_exposure": "SunExposed", "wind_exposure": "WindExposed",
            "vertices": _sommets(pts),
        }
    surfaces["Toiture"] = {
        "surface_type": "Roof", "construction_name": "Toiture", "zone_name": ZONE,
        "outside_boundary_condition": "Outdoors", "sun_exposure": "SunExposed", "wind_exposure": "WindExposed",
        "vertices": _sommets([(0, W, H), (0, 0, H), (L, 0, H), (L, W, H)]),
    }
    surfaces["Plancher"] = {
        "surface_type": "Floor", "construction_name": "Plancher", "zone_name": ZONE,
        "outside_boundary_condition": "Ground", "sun_exposure": "NoSun", "wind_exposure": "NoWind",
        "vertices": _sommets([(0, W, 0), (L, W, 0), (L, 0, 0), (0, 0, 0)]),
    }
    o["BuildingSurface:Detailed"] = surfaces

    fen = {}
    for facade, part in b.baies.items():
        if part <= 0:
            continue
        pts = geometrie_baie(b, facade, part)
        f = {"surface_type": "Window", "construction_name": "Fenetre", "building_surface_name": f"Mur_{facade}",
             "number_of_vertices": 4}
        for i, (x, y, z) in enumerate(pts, start=1):
            f[f"vertex_{i}_x_coordinate"] = x
            f[f"vertex_{i}_y_coordinate"] = y
            f[f"vertex_{i}_z_coordinate"] = z
        fen[f"Baie_{facade}"] = f
    if fen:
        o["FenestrationSurface:Detailed"] = fen

    # Horaires
    o["ScheduleTypeLimits"] = {
        "Fraction": {"lower_limit_value": 0, "upper_limit_value": 1, "numeric_type": "Continuous"},
        "Quelconque": {"numeric_type": "Continuous"},
    }
    o["Schedule:Compact"] = {
        "Presence": _horaire_compact("Fraction", [("08:00", 1.0), ("13:00", 0.5), ("18:00", 0.7), ("24:00", 1.0)]),
        "Activite": _horaire_compact("Quelconque", [("24:00", 110)]),
        "Apports": _horaire_compact("Fraction", [("07:00", 0.3), ("19:00", 0.6), ("23:00", 1.0), ("24:00", 0.3)]),
        "Toujours": _horaire_compact("Fraction", [("24:00", 1.0)]),
        "Nuit": _horaire_compact("Fraction", [("07:00", 1.0), ("22:00", 0.0), ("24:00", 1.0)]),
    }

    o["People"] = {"Occupants": {
        "zone_or_zonelist_or_space_or_spacelist_name": ZONE,
        "number_of_people_schedule_name": "Presence",
        "number_of_people_calculation_method": "People",
        "number_of_people": b.occupants,
        "fraction_radiant": 0.3,
        "activity_level_schedule_name": "Activite",
    }}
    o["ElectricEquipment"] = {"Apports_internes": {
        "zone_or_zonelist_or_space_or_spacelist_name": ZONE,
        "schedule_name": "Apports",
        "design_level_calculation_method": "Watts/Area",
        # La moyenne journalière de l'horaire 'Apports' vaut 0,5 : on double pour retrouver la moyenne visée.
        "watts_per_floor_area": b.apports_internes * 2,
        "fraction_radiant": 0.5,
    }}
    o["ZoneInfiltration:DesignFlowRate"] = {"Infiltration": {
        "zone_or_zonelist_or_space_or_spacelist_name": ZONE,
        "schedule_name": "Toujours",
        "design_flow_rate_calculation_method": "AirChanges/Hour",
        "air_changes_per_hour": b.infiltration,
    }}
    if b.ventilation_nocturne:
        o["ZoneVentilation:DesignFlowRate"] = {"Ventilation_nocturne": {
            "zone_or_zonelist_or_space_or_spacelist_name": ZONE,
            "schedule_name": "Nuit",
            "design_flow_rate_calculation_method": "AirChanges/Hour",
            "air_changes_per_hour": b.debit_nocturne,
            "ventilation_type": "Natural",
            # On ouvre seulement s'il fait plus de 22 °C dedans et plus frais dehors.
            "minimum_indoor_temperature": 22.0,
            "delta_temperature": 1.0,
        }}

    sorties = ["Zone Operative Temperature", "Zone Mean Air Temperature", "Site Outdoor Air Drybulb Temperature"]
    o["Output:Variable"] = {
        f"Sortie {i}": {"key_value": "*", "variable_name": v, "reporting_frequency": "Hourly"}
        for i, v in enumerate(sorties, start=1)
    }
    o["Output:SQLite"] = {"Output:SQLite 1": {"option_type": "SimpleAndTabular"}}
    return o
