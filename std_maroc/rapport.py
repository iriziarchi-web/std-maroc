"""Rapport PDF en français comparant les variantes de parois."""

from datetime import date

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import bibliotheque as bib

COULEURS = [colors.HexColor(c) for c in ("#b5651d", "#d4a373", "#6c757d", "#8a5a44", "#264653")]
GRIS = colors.HexColor("#999999")


def _tableau(resultats, ville, ventilation):
    entete = ["Paroi", "U\n(W/m².K)", "Masse\n(kg/m²)", "Heures\ninconfort\n(an)", "dont\nété",
              "Heures\n> 28 °C", "T max\n(°C)", "Amplitude\nint. été (°C)"]
    lignes = [entete]
    for r in resultats:
        if r["ville"] != ville or r["ventilation_nocturne"] != ventilation:
            continue
        p = bib.paroi("murs", r["mur"])
        i = r["indicateurs"]
        lignes.append([p.nom, f"{p.u:.2f}", f"{p.masse_surfacique:.0f}", i["heures_chaud"], i["heures_chaud_ete"],
                       i["heures_sup_28"], f"{i['t_max']:.1f}", f"{i['amplitude_ete']:.1f}"])
    t = Table(lignes, colWidths=[5.6 * cm] + [1.6 * cm] * 7, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, GRIS),
    ]))
    return t


def _barres(resultats, ville):
    murs = [r["mur"] for r in resultats if r["ville"] == ville and r["ventilation_nocturne"]]
    series = []
    for vent in (False, True):
        series.append([next(r["indicateurs"]["heures_chaud"] for r in resultats
                            if r["ville"] == ville and r["mur"] == m and r["ventilation_nocturne"] == vent)
                       for m in murs])
    d = Drawing(17 * cm, 6.5 * cm)
    bc = VerticalBarChart()
    bc.x, bc.y, bc.width, bc.height = 40, 40, 13 * cm, 4.5 * cm
    bc.data = series
    bc.categoryAxis.categoryNames = [bib.paroi("murs", m).nom.split(",")[0] for m in murs]
    bc.categoryAxis.labels.fontSize = 7
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labels.fontSize = 7
    bc.bars[0].fillColor = colors.HexColor("#c9ada7")
    bc.bars[1].fillColor = colors.HexColor("#4a4e69")
    bc.barSpacing = 1
    d.add(bc)
    lg = Legend()
    lg.x, lg.y = 13.8 * cm, 5.6 * cm
    lg.fontSize = 7
    lg.colorNamePairs = [(colors.HexColor("#c9ada7"), "sans ventilation nocturne"),
                         (colors.HexColor("#4a4e69"), "avec ventilation nocturne")]
    d.add(lg)
    d.add(String(40, 6.2 * cm, "Heures d'inconfort par an (EN 16798-1, cat. II)", fontSize=8))
    return d


def _courbes(series, ville):
    """series : {'Extérieur': [...168], nom paroi: [...168]}"""
    d = Drawing(17 * cm, 7.5 * cm)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 40, 40, 12.5 * cm, 5.5 * cm
    noms = list(series)
    lp.data = [list(enumerate(v)) for v in series.values()]
    for i, nom in enumerate(noms):
        lp.lines[i].strokeColor = GRIS if nom == "Extérieur" else COULEURS[(i - 1) % len(COULEURS)]
        lp.lines[i].strokeWidth = 0.8 if nom == "Extérieur" else 1.4
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, 168
    lp.xValueAxis.valueSteps = list(range(0, 169, 24))
    lp.xValueAxis.labelTextFormat = lambda h: f"J{int(h // 24) + 1}"
    lp.xValueAxis.labels.fontSize = 7
    lp.yValueAxis.labels.fontSize = 7
    d.add(lp)
    lg = Legend()
    lg.x, lg.y = 13.5 * cm, 6.3 * cm
    lg.fontSize = 7
    lg.colorNamePairs = [(lp.lines[i].strokeColor, n.split(",")[0]) for i, n in enumerate(noms)]
    d.add(lg)
    d.add(String(40, 7.0 * cm, f"{ville} : semaine la plus chaude, température opérative (°C), "
                               "avec ventilation nocturne", fontSize=8))
    return d


def ecrire(chemin, resultats, semaines, batiment):
    """resultats : liste de dicts (ville, mur, ventilation_nocturne, indicateurs).
    semaines : {ville: {'Extérieur': [...], nom paroi: [...]}}."""
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm, title="STD Maroc : prototype 1")
    e = [Paragraph("Simulation thermique dynamique : comparaison de parois", st["Title"]),
         Paragraph(f"Prototype 1, {date.today():%d/%m/%Y}. Moteur EnergyPlus.", st["Normal"]),
         Spacer(1, 8),
         Paragraph(
             f"Maison de plain-pied de {batiment.longueur:g} m x {batiment.largeur:g} m, "
             f"{batiment.hauteur:g} m sous plafond, toiture « {bib.paroi('toitures', batiment.toiture).nom} », "
             f"baies {int(batiment.baies['sud'] * 100)} % au sud et {int(batiment.baies['nord'] * 100)} % au nord "
             f"en simple vitrage, {batiment.occupants} occupants, sans climatisation. Seule la paroi verticale change "
             "d'une variante à l'autre. La ventilation nocturne ouvre les fenêtres de 22 h à 7 h "
             f"({batiment.debit_nocturne:g} vol/h) quand il fait plus frais dehors.", st["Normal"]),
         Spacer(1, 6),
         Paragraph(
             "Heures d'inconfort : heures où la température opérative dépasse la limite haute du confort adaptatif "
             "EN 16798-1, catégorie II (0,33 x T<sub>rm</sub> + 21,8 °C). Les propriétés des matériaux sont "
             "provisoires et doivent encore être sourcées.", st["Normal"])]
    villes = list(dict.fromkeys(r["ville"] for r in resultats))
    for ville in villes:
        code = next(r["zone"] for r in resultats if r["ville"] == ville)
        e += [PageBreak(), Paragraph(f"{ville} (zone RTCM {code})", st["Heading2"]),
              Paragraph("Avec ventilation nocturne", st["Heading4"]), _tableau(resultats, ville, True),
              Spacer(1, 6),
              Paragraph("Sans ventilation nocturne", st["Heading4"]), _tableau(resultats, ville, False),
              Spacer(1, 10), _barres(resultats, ville), Spacer(1, 6), _courbes(semaines[ville], ville)]
    doc.build(e)
