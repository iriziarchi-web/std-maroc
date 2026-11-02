"""Lancement d'EnergyPlus et lecture des résultats."""

import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path


def trouver_energyplus():
    exe = os.environ.get("ENERGYPLUS_EXE") or shutil.which("energyplus")
    if not exe:
        raise FileNotFoundError(
            "EnergyPlus introuvable. Installez EnergyPlus 24.2 puis ajoutez-le au PATH, "
            "ou indiquez son chemin dans la variable ENERGYPLUS_EXE."
        )
    return exe


def lancer(modele, epw, dossier):
    """Écrit le modèle, lance EnergyPlus et retourne le chemin de la base SQLite des résultats."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    entree = dossier / "modele.epJSON"
    entree.write_text(json.dumps(modele, indent=1, ensure_ascii=False), encoding="utf-8")
    cmd = [trouver_energyplus(), "-w", str(epw), "-d", str(dossier), str(entree)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    erreurs = dossier / "eplusout.err"
    if r.returncode != 0:
        detail = erreurs.read_text(errors="replace")[-3000:] if erreurs.exists() else r.stderr[-3000:]
        raise RuntimeError(f"EnergyPlus a échoué ({r.returncode}).\n{detail}")
    return dossier / "eplusout.sql"


def lire_serie(sql, variable, cle=None):
    """Série horaire d'une variable sur la période de simulation (hors jours de mise en régime)."""
    con = sqlite3.connect(sql)
    try:
        req = """
            SELECT rd.Value
            FROM ReportData rd
            JOIN ReportDataDictionary d ON d.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
            JOIN Time t ON t.TimeIndex = rd.TimeIndex
            JOIN EnvironmentPeriods e ON e.EnvironmentPeriodIndex = t.EnvironmentPeriodIndex
            WHERE d.Name = ? AND d.ReportingFrequency = 'Hourly' AND e.EnvironmentType = 3
              AND (t.WarmupFlag IS NULL OR t.WarmupFlag = 0)
        """
        params = [variable]
        if cle is not None:
            req += " AND upper(d.KeyValue) = upper(?)"
            params.append(cle)
        req += " ORDER BY rd.TimeIndex"
        valeurs = [v for (v,) in con.execute(req, params)]
        if not valeurs:  # anciennes versions : pas de filtre sur le type de période
            req = req.replace("AND e.EnvironmentType = 3", "")
            valeurs = [v for (v,) in con.execute(req, params)]
        return valeurs[-8760:]
    finally:
        con.close()
