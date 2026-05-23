"""PDF del Dashboard — resumen ejecutivo del estado de equipos."""
import io
from datetime import date, datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

AZ=colors.HexColor('#0f3460'); AZ2=colors.HexColor('#1a4f8a')
GR=colors.HexColor('#64748b'); OK=colors.HexColor('#16a34a')
FL=colors.HexColor('#dc2626'); AM=colors.HexColor('#d97706')
BG=colors.HexColor('#f8fafc'); GD=colors.HexColor('#e2e8f0')

def _s(**k):
    return ParagraphStyle(f'_s{hash(str(k))}',
                           parent=getSampleStyleSheet()['Normal'], **k)

def generar_pdf_dashboard(datos, hoy, usuario, config):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                             rightMargin=1.5*cm, leftMargin=1.5*cm,
                             topMargin=1.5*cm, bottomMargin=2*cm)
    nombre_lab = getattr(config,'nombre','Laboratorio') or 'Laboratorio'
    story = []

    # Encabezado
    try:
        from utils.pdf_header import encabezado_controlado
        story.append(encabezado_controlado(config, 'auditoria'))
    except Exception:
        story.append(Paragraph(f"<b>{nombre_lab} — Dashboard Metrológico</b>",
                                _s(fontSize=14, fontName='Helvetica-Bold', textColor=AZ)))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Fecha de generación: {hoy.strftime('%d/%m/%Y')} · Generado por: {usuario.nombre}",
        _s(fontSize=8, textColor=GR)))
    story.append(Spacer(1, 0.4*cm))

    # Indicadores resumen
    indicadores = [
        ['Total equipos', 'Operativos', 'Cal. vencidas', 'Próx. 30 días',
         'Próx. 60 días', 'Verif. pendientes', 'Mant. programados', f'Costo {hoy.year}'],
        [str(datos['total']), str(datos['operativos']), str(datos['vencidos']),
         str(datos['criticos_30']), str(datos['proximos_60']),
         str(datos['verif_pendientes']), str(datos['mant_programados']),
         f"${datos['costo_anio']:,.0f}"],
    ]
    ti = Table(indicadores, colWidths=[3.2*cm]*8)
    ti.setStyle(TableStyle([
        ('FONTSIZE',     (0,0),(-1,-1), 8),
        ('FONTNAME',     (0,0),(-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND',   (0,0),(-1, 0), AZ2),
        ('TEXTCOLOR',    (0,0),(-1, 0), colors.white),
        ('FONTNAME',     (0,1),(-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,1),(-1, 1), 13),
        ('TEXTCOLOR',    (2,1),(2, 1), FL),   # vencidos
        ('TEXTCOLOR',    (3,1),(3, 1), AM),   # criticos
        ('TEXTCOLOR',    (1,1),(1, 1), OK),   # operativos
        ('ALIGN',        (0,0),(-1,-1), 'CENTER'),
        ('GRID',         (0,0),(-1,-1), 0.5, GD),
        ('PADDING',      (0,0),(-1,-1), 6),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [BG]),
    ]))
    story.append(ti)
    story.append(Spacer(1, 0.4*cm))

    # Tabla detallada
    story.append(Paragraph("Estado detallado de equipos", _s(fontSize=10,
        fontName='Helvetica-Bold', textColor=AZ, spaceAfter=4)))

    header = ['Equipo','Código','Área','Estado','Magnitudes',
              'Última cal.','Próxima cal.','Días','Último mant.']
    rows = [header]
    for d in datos['filas']:
        eq = d['equipo']
        dias = d['dias_cal']
        if dias is None:
            dias_txt = 'Sin programar'
        elif dias < 0:
            dias_txt = f'Vencida {abs(dias)}d'
        elif dias == 0:
            dias_txt = 'Hoy'
        else:
            dias_txt = f'{dias}d'
        rows.append([
            eq.nombre[:28],
            eq.codigo,
            (eq.area or '—')[:15],
            eq.estado.replace('_',' ').title(),
            str(len([m for m in eq.magnitudes if m.activa])),
            d['ultima_cal'].strftime('%d/%m/%Y') if d['ultima_cal'] else '—',
            d['proxima_cal'].strftime('%d/%m/%Y') if d['proxima_cal'] else '—',
            dias_txt,
            d['ultimo_mant'].strftime('%d/%m/%Y') if d['ultimo_mant'] else '—',
        ])

    cw = [5.5, 2, 3, 3, 2, 2.5, 2.5, 2.5, 2.5]
    td = Table(rows, colWidths=[c*cm for c in cw])
    sty = TableStyle([
        ('FONTSIZE',      (0,0),(-1,-1), 7),
        ('FONTNAME',      (0,0),(-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND',    (0,0),(-1, 0), AZ2),
        ('TEXTCOLOR',     (0,0),(-1, 0), colors.white),
        ('GRID',          (0,0),(-1,-1), 0.3, GD),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, BG]),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('PADDING',       (0,0),(-1,-1), 3),
    ])
    # Colorear días según urgencia
    for i, d in enumerate(datos['filas']):
        r = i + 1
        dias = d['dias_cal']
        if dias is not None:
            if dias < 0:
                sty.add('TEXTCOLOR', (7,r),(7,r), FL)
                sty.add('FONTNAME',  (7,r),(7,r), 'Helvetica-Bold')
            elif dias <= 30:
                sty.add('TEXTCOLOR', (7,r),(7,r), AM)
    td.setStyle(sty)
    story.append(td)

    # Equipos por área
    if datos['por_area']:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph("Equipos por área", _s(fontSize=10,
            fontName='Helvetica-Bold', textColor=AZ, spaceAfter=4)))
        area_rows = [['Área','Cantidad']]
        for area, cant in datos['por_area'].items():
            area_rows.append([area, str(cant)])
        ta = Table(area_rows, colWidths=[8*cm, 3*cm])
        ta.setStyle(TableStyle([
            ('FONTSIZE',     (0,0),(-1,-1), 8),
            ('FONTNAME',     (0,0),(-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND',   (0,0),(-1, 0), AZ2),
            ('TEXTCOLOR',    (0,0),(-1, 0), colors.white),
            ('GRID',         (0,0),(-1,-1), 0.3, GD),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, BG]),
            ('PADDING',      (0,0),(-1,-1), 4),
        ]))
        story.append(ta)

    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GD))
    story.append(Paragraph(
        f"MetroGest v2.0 · {datetime.now().strftime('%d/%m/%Y %H:%M')} · {nombre_lab}",
        _s(fontSize=7, textColor=GR, alignment=TA_CENTER)))

    try:
        from utils.pdf_header import NumPageCanvas
        doc.build(story, canvasmaker=NumPageCanvas)
    except Exception:
        doc.build(story)
    buf.seek(0)
    return buf.read()
