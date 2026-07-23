"""
utils/pdf_metodos.py — Certificados PDF de los métodos avanzados de intervalo
=============================================================================
Un único generador para M1 (deriva), M2 (caja negra), M3 (horas) y M4 (escalera).
Reutiliza los helpers de estilo de utils.pdf_docs.
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                                 HRFlowable)

from utils.pdf_docs import (_enc, _h1, _sp, _tbl, _firmas, _pie, _sty,
                            AZ, AZ2, GR, OK, FL, AM, BG, GD)

_TITULOS = {
    'deriva':     ('Análisis de deriva (M1)',       'Método de carta de control — ILAC-G24'),
    'caja-negra': ('Método de caja negra (M2)',     'Verificaciones intermedias — ILAC-G24'),
    'horas':      ('Método por horas de uso (M3)',  'Intervalo por horas de operación — ILAC-G24'),
    'escalera':   ('Método de escalera (M4)',       'Ajuste automático (staircase) — ILAC-G24'),
}


def _tabla_serie(encabezados, filas, anchos):
    data = [encabezados] + filas
    t = Table(data, colWidths=[a * cm for a in anchos])
    t.setStyle(TableStyle([
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND',    (0, 0), (-1, 0), AZ2),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('GRID',          (0, 0), (-1, -1), 0.3, GD),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, BG]),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (1, 0), (-1, -1), 'CENTER'),
        ('PADDING',       (0, 0), (-1, -1), 4),
    ]))
    return t


def _seccion_metodo(metodo, a, mag):
    """Flowables específicos de cada método (sección 2 del PDF)."""
    fl = []

    if metodo == 'deriva':
        ritmo = a.get('pendiente', 0) * 100
        mhe = a.get('meses_hasta_emp')
        fl.append(_tbl([
            ['Ritmo de deriva', 'Consumo actual', 'Tiempo hasta EMP', 'Calidad ajuste (R²)'],
            [f"{ritmo:+.2f} %/mes",
             f"{a.get('r_last', 0)*100:.0f} %",
             (f"{mhe:.0f} meses" if mhe is not None else "Sin deriva"),
             f"{a.get('r2', 0):.2f}"],
        ], [4.7, 4.3, 4.3, 4.2]))
        fl.append(_sp(0.3))
        filas = [[str(i + 1), s['fecha'].strftime('%d/%m/%Y'), f"{s['r']*100:.0f} %"]
                 for i, s in enumerate(a.get('serie', []))]
        if filas:
            fl.append(Paragraph("Histórico de consumo de tolerancia:",
                                _sty(fontSize=8, textColor=GR, spaceAfter=3)))
            fl.append(_tabla_serie(['#', 'Fecha de calibración', 'Consumo del EMP'],
                                   filas, [1.5, 8, 8]))

    elif metodo == 'caja-negra':
        fl.append(_tbl([
            ['Verificaciones', 'Conformes', 'En alerta', 'Fuera de tolerancia'],
            [str(a.get('n_verificaciones', 0)), str(a.get('n_conforme', 0)),
             str(a.get('n_alerta', 0)), str(a.get('n_fuera', 0))],
        ], [4.5, 4.3, 4.3, 4.4]))
        fl.append(_sp(0.3))
        _lbl = {'conforme': 'Conforme', 'alerta': 'Alerta', 'no_conforme': 'Fuera'}
        filas = [[str(i + 1), s['fecha'].strftime('%d/%m/%Y'),
                  _lbl.get(s['estado'], s['estado']),
                  (f"{s['desv']:.1f} %" if s.get('desv') is not None else '—')]
                 for i, s in enumerate(a.get('serie', []))]
        if filas:
            fl.append(Paragraph(
                f"Umbral de alerta {a.get('umbral_alerta', 70):.0f}% · "
                f"fuera de tolerancia {a.get('umbral_fuera', 100):.0f}%:",
                _sty(fontSize=8, textColor=GR, spaceAfter=3)))
            fl.append(_tabla_serie(['#', 'Fecha', 'Estado', 'Desviación'],
                                   filas, [1.5, 6, 5, 5]))

    elif metodo == 'horas':
        lim = a.get('limite') or 0
        acum = a.get('acumuladas') or 0
        rest = a.get('horas_restantes', max(0, lim - acum))
        hmes = a.get('horas_mes')
        fl.append(_tbl([
            ['Límite de horas', 'Horas acumuladas', 'Horas restantes', 'Consumido'],
            [f"{lim:.0f} h", f"{acum:.0f} h", f"{rest:.0f} h",
             f"{a.get('pct_consumido', 0):.0f} %"],
        ], [4.5, 4.5, 4.3, 4.2]))
        if hmes:
            fl.append(_sp(0.3))
            fl.append(_tbl([
                ['Uso estimado', 'Equivalente a'],
                [f"{hmes:.0f} h/mes",
                 (f"{a.get('meses_equiv', 0):.0f} meses hasta la próxima calibración")],
            ], [8, 9.5]))

    elif metodo == 'escalera':
        _res_ult = a.get('conforme_ultimo')
        fl.append(_tbl([
            ['Paso configurado', 'Racha', 'Último resultado'],
            [f"{a.get('paso_pct', 20)} %",
             f"{a.get('streak', 0)} calibración(es)",
             ('Conforme' if _res_ult else 'No conforme' if _res_ult is not None else '—')],
        ], [5.5, 6, 6]))
        fl.append(_sp(0.3))
        filas = [[str(i + 1), s['fecha'].strftime('%d/%m/%Y'),
                  ('Conforme' if s['conforme'] else 'No conforme'),
                  f"{s['r']*100:.0f} %"]
                 for i, s in enumerate(a.get('serie', []))]
        if filas:
            fl.append(Paragraph("Historial de resultados:",
                                _sty(fontSize=8, textColor=GR, spaceAfter=3)))
            fl.append(_tabla_serie(['#', 'Fecha', 'Resultado', 'Consumo del EMP'],
                                   filas, [1.5, 6, 5, 5]))

    return fl


def generar_pdf_metodo(mag, analisis, metodo, usuario, config):
    """Genera el PDF de un método avanzado. Retorna bytes."""
    buf = io.BytesIO()
    eq = mag.equipo

    try:
        from utils.pdf_header import NumPageCanvas
        canvas_maker = NumPageCanvas
    except Exception:
        canvas_maker = None

    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm,
                             topMargin=2 * cm, bottomMargin=2.5 * cm)
    story = []
    story.append(_enc(config, 'analisis'))
    story.append(_sp(0.4))

    titulo, subtitulo = _TITULOS.get(metodo, ('Análisis de intervalo', 'ILAC-G24'))
    story.append(_h1(f"1. {titulo}"))
    story.append(Paragraph(subtitulo, _sty(fontSize=8, textColor=GR, spaceAfter=6)))

    story.append(_tbl([
        ['Equipo', 'Magnitud', 'EMP', 'Fecha'],
        [eq.nombre if eq else '—', mag.nombre,
         (f"±{mag.emp_valor} {mag.unidad or ''}" if mag.emp_valor else '—'),
         datetime.now().strftime('%d/%m/%Y')],
    ], [6, 5, 4.5, 4]))
    story.append(_sp())

    story.append(_h1("2. Datos del análisis"))
    for f in _seccion_metodo(metodo, analisis, mag):
        story.append(f)
    story.append(_sp())

    # Veredicto
    story.append(_h1("3. Período recomendado"))
    interv = analisis.get('intervalo_sugerido', '—')
    v_tbl = Table([[f"PERÍODO DE CALIBRACIÓN RECOMENDADO: CADA {interv} MESES"]],
                  colWidths=[17.5 * cm])
    v_tbl.setStyle(TableStyle([
        ('FONTNAME',   (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (0, 0), 12),
        ('TEXTCOLOR',  (0, 0), (0, 0), AZ),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#eff6ff')),
        ('BOX',        (0, 0), (0, 0), 2, AZ2),
        ('PADDING',    (0, 0), (0, 0), 12),
        ('ALIGN',      (0, 0), (0, 0), 'CENTER'),
    ]))
    story.append(v_tbl)

    if analisis.get('mensaje'):
        story.append(_sp(0.3))
        story.append(Paragraph(f"<b>Fundamento:</b> {analisis['mensaje']}",
                                _sty(fontSize=9, textColor=GR)))

    story.append(_sp(0.5))
    story.append(_h1("4. Firmas"))
    story.append(_firmas(config))
    story.append(_sp(0.3))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GD))
    story.append(_pie(usuario, config))

    if canvas_maker:
        doc.build(story, canvasmaker=canvas_maker)
    else:
        doc.build(story)
    buf.seek(0)
    return buf.read()
