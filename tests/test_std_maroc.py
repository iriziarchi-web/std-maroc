import json
import os
import tempfile
import unittest
from pathlib import Path

from std_maroc import bibliotheque as bib
from std_maroc import confort, meteo, modele, rapport

from .outils import epw_synthetique

SCHEMA = os.environ.get("ENERGYPLUS_SCHEMA")


def normale(points):
    """Normale de Newell d'un polygone."""
    nx = ny = nz = 0.0
    for i, (x1, y1, z1) in enumerate(points):
        x2, y2, z2 = points[(i + 1) % len(points)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx, ny, nz


class TestBibliotheque(unittest.TestCase):
    def test_toutes_les_couches_existent(self):
        for famille, parois in bib.parois().items():
            if famille.startswith("_"):
                continue
            for cle in parois:
                for mat, ep in bib.paroi(famille, cle).couches:
                    self.assertIn(mat, bib.materiaux())
                    self.assertGreater(ep, 0)

    def test_valeurs_u_plausibles(self):
        # Parpaing 20 cm enduit : U d'environ 2,2 W/m2.K ; pisé 50 cm : d'environ 1,3.
        self.assertAlmostEqual(bib.paroi("murs", "parpaing_20").u, 2.2, delta=0.4)
        self.assertAlmostEqual(bib.paroi("murs", "pise_50").u, 1.3, delta=0.3)
        self.assertGreater(bib.paroi("murs", "pise_50").masse_surfacique,
                           3 * bib.paroi("murs", "parpaing_20").masse_surfacique)

    def test_zones_rtcm(self):
        self.assertEqual(len(bib.zones()), 6)
        self.assertEqual(bib.zone_par_ville("agadir")[0], "Z1")
        self.assertEqual(bib.zone_par_ville("errachidia")[0], "Z6")


class TestMeteo(unittest.TestCase):
    def test_lecture_epw(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.epw"
            epw_synthetique(p)
            m = meteo.lire_epw(p)
        self.assertEqual(m.ville, "Testville")
        self.assertEqual(len(m.temperature_ext), 8760)
        self.assertEqual(len(m.temperature_sol), 12)
        self.assertAlmostEqual(m.latitude, 30.38)


class TestGeometrie(unittest.TestCase):
    def test_normales_sortantes(self):
        b = modele.Batiment()
        attendues = {"sud": (0, -1), "est": (1, 0), "nord": (0, 1), "ouest": (-1, 0)}
        for facade, pts in modele.geometrie_murs(b).items():
            nx, ny, nz = normale(pts)
            self.assertEqual((round(nx / abs(nx or ny)) if nx else 0, round(ny / abs(ny or nx)) if ny else 0),
                             attendues[facade], facade)

    def test_baies_dans_le_mur_et_meme_orientation(self):
        b = modele.Batiment()
        murs = modele.geometrie_murs(b)
        for facade in ("sud", "nord"):
            pts = modele.geometrie_baie(b, facade, 0.15)
            n_mur, n_baie = normale(murs[facade]), normale(pts)
            self.assertGreater(sum(a * c for a, c in zip(n_mur, n_baie)), 0)
            surface = sum(abs(v) for v in n_baie) / 2
            self.assertAlmostEqual(surface, 0.15 * 10 * 3, places=2)


class TestModele(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        p = Path(self.dossier.name) / "t.epw"
        epw_synthetique(p)
        self.meteo = meteo.lire_epw(p)

    def tearDown(self):
        self.dossier.cleanup()

    def test_toiture_vers_le_haut_plancher_vers_le_bas(self):
        o = modele.construire(modele.Batiment(), self.meteo)
        s = o["BuildingSurface:Detailed"]
        pts = lambda n: [(v["vertex_x_coordinate"], v["vertex_y_coordinate"], v["vertex_z_coordinate"])
                         for v in s[n]["vertices"]]
        self.assertGreater(normale(pts("Toiture"))[2], 0)
        self.assertLess(normale(pts("Plancher"))[2], 0)

    def test_references_coherentes(self):
        for mur in bib.parois()["murs"]:
            for vent in (True, False):
                o = modele.construire(modele.Batiment(mur=mur, ventilation_nocturne=vent), self.meteo)
                for cons in o["Construction"].values():
                    for couche in cons.values():
                        self.assertTrue(couche in o["Material"] or
                                        couche in o["WindowMaterial:SimpleGlazingSystem"], couche)
                for s in o["BuildingSurface:Detailed"].values():
                    self.assertIn(s["construction_name"], o["Construction"])
                    self.assertIn(s["zone_name"], o["Zone"])
                for f in o.get("FenestrationSurface:Detailed", {}).values():
                    self.assertIn(f["building_surface_name"], o["BuildingSurface:Detailed"])
                self.assertEqual("ZoneVentilation:DesignFlowRate" in o, vent)

    @unittest.skipUnless(SCHEMA, "ENERGYPLUS_SCHEMA non défini (chemin vers Energy+.schema.epJSON)")
    def test_conforme_au_schema_energyplus(self):
        import jsonschema
        schema = json.loads(Path(SCHEMA).read_text())
        for mur in bib.parois()["murs"]:
            o = modele.construire(modele.Batiment(mur=mur), self.meteo)
            jsonschema.validate(o, schema)


class TestConfort(unittest.TestCase):
    def test_limite_haute_bornee(self):
        hautes, basses = confort.limites_adaptatives([35.0] * 8760)
        self.assertAlmostEqual(hautes[5000], 0.33 * 30 + 18.8 + 3, places=6)
        hautes, _ = confort.limites_adaptatives([20.0] * 8760)
        self.assertAlmostEqual(hautes[5000], 0.33 * 20 + 18.8 + 3, places=6)

    def test_comptage(self):
        t_ext = [20.0] * 8760  # limite haute 28,4 °C
        t_op = [27.0] * 8760
        for h in range(4000, 4010):
            t_op[h] = 30.0
        ind = confort.calculer(t_op, t_ext)
        self.assertEqual(ind.heures_chaud, 10)
        self.assertEqual(ind.heures_sup_28, 10)
        self.assertAlmostEqual(ind.degres_heures_chaud, 16.0, places=1)
        self.assertEqual(ind.heures_chaud_ete, 10)  # heure 4000 = 16 juin
        self.assertEqual(ind.heures_froid, 0)

    def test_semaine_la_plus_chaude(self):
        t = [20.0] * 8760
        for h in range(200 * 24, 207 * 24):
            t[h] = 40.0
        self.assertEqual(confort.semaine_la_plus_chaude(t), 200 * 24)


class TestRapport(unittest.TestCase):
    def test_pdf_avec_resultats_fictifs(self):
        resultats, semaines = [], {}
        for ville, code in (("Agadir", "Z1"), ("Errachidia", "Z6")):
            semaines[ville] = {"Extérieur": [25 + (h % 24) / 3 for h in range(168)]}
            for i, mur in enumerate(("pise_50", "parpaing_20")):
                for vent in (True, False):
                    ind = confort.Indicateurs(100 * i + 50 * (not vent), 80, 300.0, 200, 0, 31.0, 14.0, 2.0, 14.0)
                    resultats.append({"ville": ville, "zone": code, "mur": mur, "ventilation_nocturne": vent,
                                      "indicateurs": ind.en_dict()})
                semaines[ville][bib.paroi("murs", mur).nom] = [27 + i + (h % 24) / 10 for h in range(168)]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.pdf"
            rapport.ecrire(p, resultats, semaines, modele.Batiment())
            self.assertGreater(p.stat().st_size, 3000)


if __name__ == "__main__":
    unittest.main()
