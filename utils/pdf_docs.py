"""
PDFs de verificaciones, mantenimientos e ILAC.
"""
import io
from datetime import date, datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak)
from reportlab.lib.enums import TA_CENTER

AZ  = colors.HexColor('#0f3460')
AZ2 = colors.HexColor('#1a4f8a')
GR  = colors.HexColor('#64748b')
OK  = colors.HexColor('#16a34a')
FL  = colors.HexColor('#dc2626')
AM  = colors.HexColor('#d97706')
BG  = colors.HexColor('#f8fafc')
GD  = colors.HexColor('#e2e8f0')

def _sty(**k):
    s = getSampleStyleSheet()['Normal']
    return ParagraphStyle(f'_s{hash(str(k))}', parent=s, **k)

def _enc(config, tipo):
    try:
        from utils.pdf_header import encabezado_controlado
        return encabezado_controlado(config, tipo)
    except Exception:
        return Paragraph(f"MetroGest — {tipo.upper()}",
                         _sty(fontSize=13, fontName='Helvetica-Bold', textColor=AZ))

def _h1(t):
    return Paragraph(t, _sty(fontSize=10, fontName='Helvetica-Bold',
                               textColor=AZ, spaceAfter=4, spaceBefore=6))

def _sp(h=0.3):
    return Spacer(1, h*cm)

def _tbl(data, cw, header_color=None):
    t = Table(data, colWidths=[c*cm for c in cw])
    t.setStyle(TableStyle([
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('FONTNAME',      (0,0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND',    (0,0), (-1, 0), header_color or AZ2),
        ('TEXTCOLOR',     (0,0), (-1, 0), colors.white),
        ('GRID',          (0,0), (-1,-1), 0.3, GD),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, BG]),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING',       (0,0), (-1,-1), 5),
    ]))
    return t

def _firmas(config):
    elab = getattr(config,'elaborado_por','') or ''
    rev  = getattr(config,'revisado_por', '') or ''
    apb  = getattr(config,'aprobado_por', '') or ''
    t = Table(
        [['Elaborado por','Revisado por','Aprobado por'],
         [elab, rev, apb],
         ['','',''],
         ['Firma:','Firma:','Firma:']],
        colWidths=[6.5*cm, 6.5*cm, 6.5*cm]
    )
    t.setStyle(TableStyle([
        ('FONTNAME',   (0,0),(-1, 0),'Helvetica-Bold'),
        ('FONTSIZE',   (0,0),(-1,-1), 8),
        ('ALIGN',      (0,0),(-1,-1),'CENTER'),
        ('GRID',       (0,0),(-1,-1), 0.5, GD),
        ('PADDING',    (0,0),(-1,-1), 6),
        ('BACKGROUND', (0,0),(-1, 0), BG),
        ('ROWHEIGHTS', (0,2),(-1, 2), 1.5*cm),
    ]))
    return t

def _pie(usuario, config):
    nombre_lab = getattr(config,'nombre','MetroGest') or 'MetroGest'
    return Paragraph(
        f"MetroGest v2.0 · {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
        f"{usuario.nombre} · {nombre_lab}",
        _sty(fontSize=7, textColor=GR, alignment=TA_CENTER)
    )

# ═══════════════════════════════════════════════════════════════════
# PDF VERIFICACIÓN INTERMEDIA
# ═══════════════════════════════════════════════════════════════════

def generar_pdf_verificacion(ver, usuario, config):
    buf = io.BytesIO()
    mag = ver.magnitud
    eq  = ver.equipo
    plan = ver.plan

    try:
        from utils.pdf_header import NumPageCanvas
        canvas_maker = NumPageCanvas
    except Exception:
        canvas_maker = None

    doc = SimpleDocTemplate(buf, pagesize=A4,
                             rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2.5*cm)
    story = []

    # Encabezado
    story.append(_enc(config, 'verificacion'))
    story.append(_sp(0.4))

    # Datos generales
    story.append(_h1("1. Identificación del equipo y la verificación"))
    story.append(_tbl([
        ['EQUIPO','','VERIFICACIÓN',''],
        ['Nombre:', eq.nombre if eq else '—', 'Fecha:', ver.fecha.strftime('%d/%m/%Y')],
        ['Código:', eq.codigo if eq else '—', 'Tipo:', ver.tipo.replace('_',' ').title()],
        ['Magnitud:', mag.nombre if mag else '—', 'Realizada por:', ver.realizada_por or '—'],
        ['EMP:', mag.emp_texto if mag else '—', 'Patrón usado:', ver.patron_usado or '—'],
        ['Área:', eq.area if eq else '—', 'Próxima verif.:', ver.proxima_verificacion.strftime('%d/%m/%Y') if ver.proxima_verificacion else '—'],
    ], [3.2, 5.8, 3.8, 5.8]))
    story.append(_sp())

    # Umbrales
    if plan:
        story.append(_h1("2. Umbrales del plan de verificaciones"))
        story.append(_tbl([
            ['Frecuencia', 'Umbral alerta', 'Umbral fuera de límite', 'Procedimiento'],
            [f"Cada {plan.frecuencia_meses} meses",
             f"{plan.umbral_alerta_pct}% del EMP",
             f"{plan.umbral_fuera_pct}% del EMP",
             (plan.procedimiento or '—')[:60]],
        ], [4, 4, 4.5, 7]))
        story.append(_sp())

    # Puntos
    story.append(_h1("3. Puntos de verificación"))
    if ver.puntos:
        rows = [['N°','Patrón','Indicado','Error','% EMP','Resultado','Observación']]
        for p in ver.puntos:
            res_map = {'ok':'✓ OK','alerta':'⚠ Alerta','fuera':'✗ Fuera'}
            rows.append([
                str(p.numero_punto),
                f"{p.valor_patron:.6g}",
                f"{p.valor_indicado:.6g}" if p.valor_indicado is not None else '—',
                f"{p.error:+.5g}" if p.error is not None else '—',
                f"{p.desviacion_pct:.1f}%" if p.desviacion_pct is not None else '—',
                res_map.get(p.resultado, p.resultado or 'S/D'),
                (p.observacion or '')[:40],
            ])
        t = Table(rows, colWidths=[1, 2.5, 2.5, 2.5, 2.5, 2.5, 6])
        sty = TableStyle([
            ('FONTSIZE',      (0,0),(-1,-1), 7),
            ('FONTNAME',      (0,0),(-1, 0),'Helvetica-Bold'),
            ('BACKGROUND',    (0,0),(-1, 0), AZ2),
            ('TEXTCOLOR',     (0,0),(-1, 0), colors.white),
            ('GRID',          (0,0),(-1,-1), 0.3, GD),
            ('ALIGN',         (0,0),(-1,-1),'CENTER'),
            ('VALIGN',        (0,0),(-1,-1),'MIDDLE'),
            ('PADDING',       (0,0),(-1,-1), 3),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, BG]),
        ])
        for i, p in enumerate(ver.puntos):
            r = i + 1
            if p.resultado == 'ok':
                sty.add('TEXTCOLOR', (5,r),(5,r), OK)
                sty.add('FONTNAME',  (5,r),(5,r),'Helvetica-Bold')
            elif p.resultado == 'alerta':
                sty.add('TEXTCOLOR',  (5,r),(5,r), AM)
                sty.add('FONTNAME',   (5,r),(5,r),'Helvetica-Bold')
                sty.add('BACKGROUND', (0,r),(-1,r), colors.HexColor('#fefce8'))
            elif p.resultado == 'fuera':
                sty.add('TEXTCOLOR',  (5,r),(5,r), FL)
                sty.add('FONTNAME',   (5,r),(5,r),'Helvetica-Bold')
                sty.add('BACKGROUND', (0,r),(-1,r), colors.HexColor('#fff5f5'))
        t.setStyle(sty)
        story.append(t)
    else:
        story.append(Paragraph("Sin puntos registrados.", _sty(fontSize=9, textColor=GR)))
    story.append(_sp())

    # Resultado global
    story.append(_h1("4. Resultado y acción tomada"))
    res_map2 = {'aprobado':('✓ APROBADO', OK, colors.HexColor('#f0fdf4')),
                'alerta':  ('⚠ ALERTA',   AM, colors.HexColor('#fefce8')),
                'reprobado':('✗ FUERA DE LÍMITE', FL, colors.HexColor('#fff5f5')),
                'pendiente':('⏳ PENDIENTE', GR, BG)}
    vtxt, vcolor, vbg = res_map2.get(ver.resultado, ('—', GR, BG))
    desv_txt = f" · Desviación máxima: {ver.max_desviacion_pct:.1f}% del EMP" if ver.max_desviacion_pct is not None else ""
    accion = (ver.accion_tomada or 'ninguna').replace('_',' ').title()

    verdict = Table([[vtxt + desv_txt], [f"Acción tomada: {accion}"]],
                     colWidths=[19.5*cm])
    verdict.setStyle(TableStyle([
        ('FONTNAME',  (0,0),(0,0),'Helvetica-Bold'),
        ('FONTSIZE',  (0,0),(0,0), 12),
        ('FONTSIZE',  (0,1),(0,1), 9),
        ('TEXTCOLOR', (0,0),(-1,-1), vcolor),
        ('BACKGROUND',(0,0),(-1,-1), vbg),
        ('BOX',       (0,0),(-1,-1), 1.5, vcolor),
        ('PADDING',   (0,0),(-1,-1), 10),
        ('ALIGN',     (0,0),(-1,-1),'CENTER'),
    ]))
    story.append(verdict)

    if ver.observaciones:
        story.append(_sp(0.3))
        story.append(Paragraph(f"<b>Observaciones:</b> {ver.observaciones}",
                                _sty(fontSize=9, textColor=GR)))

    story.append(_sp(0.5))

    # Archivo adjunto
    if ver.archivo_path:
        story.append(Paragraph(
            f"📎 Registro físico adjunto: {ver.archivo_path.split('/')[-1]}",
            _sty(fontSize=8, textColor=GR)))
        story.append(_sp(0.3))

    # Firmas
    story.append(_h1("5. Firmas"))
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


# ═══════════════════════════════════════════════════════════════════
# PDF MANTENIMIENTO
# ═══════════════════════════════════════════════════════════════════

def generar_pdf_mantenimiento(mant, usuario, config):
    buf = io.BytesIO()
    eq  = mant.equipo

    try:
        from utils.pdf_header import NumPageCanvas
        canvas_maker = NumPageCanvas
    except Exception:
        canvas_maker = None

    doc = SimpleDocTemplate(buf, pagesize=A4,
                             rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2.5*cm)
    story = []

    story.append(_enc(config, 'mantenimiento'))
    story.append(_sp(0.4))

    # Datos generales
    story.append(_h1("1. Identificación del equipo y del mantenimiento"))
    story.append(_tbl([
        ['EQUIPO','','MANTENIMIENTO',''],
        ['Nombre:', eq.nombre if eq else '—', 'Tipo:', mant.tipo.title()],
        ['Código:', eq.codigo if eq else '—', 'Origen:', mant.origen.title()],
        ['Marca/Modelo:', f"{eq.marca or ''} {eq.modelo or ''}".strip() or '—' if eq else '—',
         'Orden de trabajo:', mant.orden_trabajo or '—'],
        ['N° Serie:', eq.numero_serie if eq else '—', 'Estado:', mant.estado.title()],
        ['Área:', eq.area if eq else '—', 'Costo:', f"${mant.costo:,.2f}" if mant.costo else '—'],
    ], [3.2, 5.8, 3.8, 5.8]))
    story.append(_sp())

    # Fechas y responsables
    story.append(_h1("2. Fechas y responsables"))
    story.append(_tbl([
        ['Fecha programada', 'Fecha inicio', 'Fecha fin', 'Responsable / Empresa'],
        [mant.fecha_programada.strftime('%d/%m/%Y') if mant.fecha_programada else '—',
         mant.fecha_inicio.strftime('%d/%m/%Y') if mant.fecha_inicio else '—',
         mant.fecha_fin.strftime('%d/%m/%Y') if mant.fecha_fin else '—',
         mant.responsable_interno or mant.empresa_externa or '—'],
    ], [4, 4, 4, 7.5]))
    story.append(_sp())

    # Descripción del trabajo
    story.append(_h1("3. Descripción del trabajo"))
    for lbl, val in [
        ('Título:', mant.titulo),
        ('Descripción:', mant.descripcion or '—'),
        ('Falla encontrada:', mant.falla_encontrada or '—'),
        ('Trabajo realizado:', mant.trabajo_realizado or '—'),
        ('Repuestos utilizados:', mant.repuestos_utilizados or '—'),
    ]:
        story.append(Paragraph(f"<b>{lbl}</b> {val}",
                                _sty(fontSize=9, textColor=GR, spaceAfter=4)))
    story.append(_sp())

    # Impacto metrológico
    story.append(_h1("4. Impacto metrológico"))
    story.append(_tbl([
        ['¿Requiere recalibración?', '¿Afecta la medición?', 'Observaciones metrológicas'],
        ['SÍ' if mant.requiere_calibracion else 'NO',
         'SÍ' if mant.afecta_medicion else 'NO',
         (mant.observaciones_metrologicas or '—')[:80]],
    ], [5, 5, 9.5]))
    story.append(_sp())

    # Alerta si requiere calibración
    if mant.requiere_calibracion:
        alerta = Table([['⚠ ESTE EQUIPO REQUIERE RECALIBRACIÓN ANTES DE VOLVER A USO']],
                        colWidths=[19.5*cm])
        alerta.setStyle(TableStyle([
            ('FONTNAME',  (0,0),(0,0),'Helvetica-Bold'),
            ('FONTSIZE',  (0,0),(0,0), 10),
            ('TEXTCOLOR', (0,0),(0,0), AM),
            ('BACKGROUND',(0,0),(0,0), colors.HexColor('#fef3c7')),
            ('BOX',       (0,0),(0,0), 1.5, AM),
            ('PADDING',   (0,0),(0,0), 10),
            ('ALIGN',     (0,0),(0,0),'CENTER'),
        ]))
        story.append(alerta)
        story.append(_sp(0.3))

    # Firmas
    story.append(_h1("5. Firmas"))
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


# ═══════════════════════════════════════════════════════════════════
# PDF EVALUACIÓN ILAC
# ═══════════════════════════════════════════════════════════════════

def generar_pdf_ilac(mag, ev, usuario, config):
    buf = io.BytesIO()
    eq  = mag.equipo

    try:
        from utils.pdf_header import NumPageCanvas
        canvas_maker = NumPageCanvas
    except Exception:
        canvas_maker = None

    doc = SimpleDocTemplate(buf, pagesize=A4,
                             rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2.5*cm)
    story = []

    story.append(_enc(config, 'analisis'))
    story.append(_sp(0.4))

    story.append(_h1("1. Identificación"))
    story.append(_tbl([
        ['Equipo', 'Magnitud', 'Evaluado por', 'Fecha'],
        [eq.nombre if eq else '—', mag.nombre,
         ev.evaluado_por or '—',
         ev.fecha_evaluacion.strftime('%d/%m/%Y') if ev.fecha_evaluacion else '—'],
    ], [6, 4.5, 5, 4]))
    story.append(_sp())

    story.append(_h1("2. Evaluación de factores de riesgo — ILAC-G24 §5.1"))
    story.append(Paragraph(
        "Escala: 1 = Riesgo alto (calibrar más frecuente) → 5 = Riesgo bajo (calibrar menos frecuente)",
        _sty(fontSize=8, textColor=GR, spaceAfter=6)))

    factores_info = [
        ('f_incertidumbre',  'a) Incertidumbre de medición requerida'),
        ('f_tipo',           'b) Tipo de instrumento'),
        ('f_riesgo_emp',     'c) Riesgo de superar el EMP'),
        ('f_fabricante',     'd) Recomendación del fabricante'),
        ('f_deriva',         'e) Tendencia al desgaste y deriva'),
        ('f_uso',            'f) Intensidad de uso'),
        ('f_ambiental',      'g) Condiciones ambientales'),
        ('f_magnitud',       'h) Influencia de la magnitud medida'),
        ('f_similares',      'i) Datos de dispositivos similares'),
        ('f_comparaciones',  'j) Frecuencia de comparaciones'),
        ('f_verificaciones', 'k) Verificaciones intermedias'),
        ('f_transporte',     'l) Riesgo de transporte'),
        ('f_personal',       'm) Capacitación del personal'),
        ('f_legal',          'n) Requisitos legales'),
    ]
    rows = [['#', 'Factor de riesgo', 'Calificación (1-5)']]
    for campo, label in factores_info:
        valor = getattr(ev, campo, 3)
        nivel = {1:'Muy alto',2:'Alto',3:'Medio',4:'Bajo',5:'Muy bajo'}.get(valor,'—')
        rows.append([label[:3], label[3:], f"{valor} — {nivel}"])

    t = Table(rows, colWidths=[1, 14.5, 4])
    t.setStyle(TableStyle([
        ('FONTSIZE',      (0,0),(-1,-1), 8),
        ('FONTNAME',      (0,0),(-1, 0),'Helvetica-Bold'),
        ('BACKGROUND',    (0,0),(-1, 0), AZ2),
        ('TEXTCOLOR',     (0,0),(-1, 0), colors.white),
        ('GRID',          (0,0),(-1,-1), 0.3, GD),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, BG]),
        ('VALIGN',        (0,0),(-1,-1),'MIDDLE'),
        ('PADDING',       (0,0),(-1,-1), 4),
    ]))
    story.append(t)
    story.append(_sp())

    story.append(_h1("3. Resultado del análisis"))
    pun = ev.puntuacion_total or 0
    col = OK if pun >= 3.5 else AM if pun >= 2.5 else FL

    res_data = [
        ['Puntuación promedio', 'Intervalo sugerido', 'Intervalo adoptado', 'Rec. fabricante'],
        [f"{pun:.2f} / 5.0",
         f"{ev.intervalo_sugerido_meses} meses" if ev.intervalo_sugerido_meses else '—',
         f"{ev.intervalo_adoptado_meses} meses" if ev.intervalo_adoptado_meses else '—',
         f"{ev.intervalo_fabricante_meses} meses" if ev.intervalo_fabricante_meses else 'No indicada'],
    ]
    tr = Table(res_data, colWidths=[5, 5, 5, 4.5])
    tr.setStyle(TableStyle([
        ('FONTSIZE',      (0,0),(-1,-1), 9),
        ('FONTNAME',      (0,0),(-1, 0),'Helvetica-Bold'),
        ('BACKGROUND',    (0,0),(-1, 0), AZ2),
        ('TEXTCOLOR',     (0,0),(-1, 0), colors.white),
        ('FONTNAME',      (2,1),(2,1),'Helvetica-Bold'),
        ('TEXTCOLOR',     (2,1),(2,1), AZ),
        ('FONTSIZE',      (2,1),(2,1), 12),
        ('GRID',          (0,0),(-1,-1), 0.5, GD),
        ('ALIGN',         (0,0),(-1,-1),'CENTER'),
        ('VALIGN',        (0,0),(-1,-1),'MIDDLE'),
        ('PADDING',       (0,0),(-1,-1), 8),
    ]))
    story.append(tr)
    story.append(_sp(0.3))

    # Veredicto
    adoptado = ev.intervalo_adoptado_meses or 12
    v_txt = f"PERÍODO DE CALIBRACIÓN DEFINIDO: CADA {adoptado} MESES"
    v_tbl = Table([[v_txt]], colWidths=[19.5*cm])
    v_tbl.setStyle(TableStyle([
        ('FONTNAME',  (0,0),(0,0),'Helvetica-Bold'),
        ('FONTSIZE',  (0,0),(0,0), 12),
        ('TEXTCOLOR', (0,0),(0,0), AZ),
        ('BACKGROUND',(0,0),(0,0), colors.HexColor('#eff6ff')),
        ('BOX',       (0,0),(0,0), 2, AZ2),
        ('PADDING',   (0,0),(0,0), 12),
        ('ALIGN',     (0,0),(0,0),'CENTER'),
    ]))
    story.append(v_tbl)

    if ev.justificacion:
        story.append(_sp(0.3))
        story.append(Paragraph(f"<b>Justificación:</b> {ev.justificacion}",
                                _sty(fontSize=9, textColor=GR)))
    if ev.justificacion_exceso:
        story.append(_sp(0.2))
        story.append(Paragraph(
            f"<b>Justificación por exceder intervalo sugerido:</b> {ev.justificacion_exceso}",
            _sty(fontSize=9, textColor=AM)))

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


# ═══════════════════════════════════════════════════════════════════
# PDF PLAN DE VERIFICACIONES
# ═══════════════════════════════════════════════════════════════════

def generar_pdf_listado_general(datos, hoy, usuario, config):
    """PDF del listado general de equipos (auditoría)."""
    buf = io.BytesIO()

    try:
        from utils.pdf_header import NumPageCanvas
        canvas_maker = NumPageCanvas
    except Exception:
        canvas_maker = None

    doc = SimpleDocTemplate(buf, pagesize=A4,
                             rightMargin=1.5*cm, leftMargin=1.5*cm,
                             topMargin=2*cm, bottomMargin=2.5*cm)
    story = []

    story.append(_enc(config, 'auditoria'))
    story.append(_sp(0.4))
    story.append(Paragraph(
        f"LISTADO GENERAL DE EQUIPOS — {hoy.strftime('%d/%m/%Y')}",
        _sty(fontSize=11, fontName='Helvetica-Bold', textColor=AZ,
             alignment=TA_CENTER, spaceAfter=8)))

    # Resumen numérico
    total = len(datos)
    vencidos = sum(1 for d in datos if d["dias_cal"] is not None and d["dias_cal"] < 0)
    criticos = sum(1 for d in datos if d["dias_cal"] is not None and 0 <= d["dias_cal"] <= 30)
    verif_vencidas = sum(1 for d in datos if d.get("verif_estado") == "vencida")

    story.append(_tbl([
        ['Total equipos', 'Cal. vencidas', 'Cal. próximas ≤30d', 'Verif. vencidas'],
        [str(total), str(vencidos), str(criticos), str(verif_vencidas)],
    ], [4.9, 4.9, 4.9, 4.9], header_color=AZ))
    story.append(_sp(0.5))

    story.append(_h1("Detalle de equipos"))

    # Tabla principal
    rows = [['Equipo / Código', 'Estado', 'Últ. cal.', 'Próx. cal.', 'Días cal.',
             'Verif. estado', 'Próx. verif.', 'Últ. mant.']]

    verif_labels = {
        'al_dia':   'Al día',
        'pendiente':'Pendiente',
        'vencida':  'Vencida',
        'sin_plan': 'Sin plan',
        'no_aplica':'No aplica',
    }

    for d in datos:
        eq = d['equipo']
        dias_txt = '—'
        if d['dias_cal'] is not None:
            if d['dias_cal'] < 0:
                dias_txt = f"Vencida {abs(d['dias_cal'])}d"
            elif d['dias_cal'] == 0:
                dias_txt = 'Hoy'
            else:
                dias_txt = f"{d['dias_cal']}d"

        vp = d.get('verif_proxima')
        rows.append([
            f"{eq.nombre}\n{eq.codigo}",
            eq.estado.replace('_', ' ').title(),
            d['ultima_cal'].strftime('%d/%m/%Y') if d['ultima_cal'] else '—',
            d['proxima_cal'].strftime('%d/%m/%Y') if d['proxima_cal'] else '—',
            dias_txt,
            verif_labels.get(d.get('verif_estado', ''), '—'),
            vp.strftime('%d/%m/%Y') if vp else '—',
            d['ultimo_mant'].strftime('%d/%m/%Y') if d['ultimo_mant'] else '—',
        ])

    t = Table(rows, colWidths=[4, 2.5, 2.2, 2.2, 2, 2.2, 2.2, 2.2])
    sty = TableStyle([
        ('FONTSIZE',      (0, 0), (-1, -1), 7),
        ('FONTNAME',      (0, 0), (-1,  0), 'Helvetica-Bold'),
        ('BACKGROUND',    (0, 0), (-1,  0), AZ2),
        ('TEXTCOLOR',     (0, 0), (-1,  0), colors.white),
        ('GRID',          (0, 0), (-1, -1), 0.3, GD),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, BG]),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING',       (0, 0), (-1, -1), 4),
        ('ALIGN',         (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN',         (0, 0), (0,  -1), 'LEFT'),
    ])
    # Colorear días de calibración
    for i, d in enumerate(datos):
        r = i + 1
        if d['dias_cal'] is not None:
            if d['dias_cal'] < 0:
                sty.add('TEXTCOLOR', (4, r), (4, r), FL)
                sty.add('FONTNAME',  (4, r), (4, r), 'Helvetica-Bold')
            elif d['dias_cal'] <= 30:
                sty.add('TEXTCOLOR', (4, r), (4, r), AM)
                sty.add('FONTNAME',  (4, r), (4, r), 'Helvetica-Bold')
        ve = d.get('verif_estado')
        if ve == 'vencida':
            sty.add('TEXTCOLOR', (5, r), (5, r), FL)
            sty.add('FONTNAME',  (5, r), (5, r), 'Helvetica-Bold')
        elif ve == 'pendiente':
            sty.add('TEXTCOLOR', (5, r), (5, r), AM)
    t.setStyle(sty)
    story.append(t)

    story.append(_sp(0.5))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GD))
    story.append(_pie(usuario, config))

    if canvas_maker:
        doc.build(story, canvasmaker=canvas_maker)
    else:
        doc.build(story)
    buf.seek(0)
    return buf.read()


def generar_pdf_plan_verificacion(mag, plan, usuario, config):
    buf = io.BytesIO()
    eq  = mag.equipo

    try:
        from utils.pdf_header import NumPageCanvas
        canvas_maker = NumPageCanvas
    except Exception:
        canvas_maker = None

    doc = SimpleDocTemplate(buf, pagesize=A4,
                             rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2.5*cm)
    story = []
    story.append(_enc(config, 'verificacion'))
    story.append(_sp(0.4))
    story.append(Paragraph(
        "PLAN DE VERIFICACIONES INTERMEDIAS — ISO/IEC 17025 §6.4.10",
        _sty(fontSize=11, fontName='Helvetica-Bold', textColor=AZ,
             alignment=TA_CENTER, spaceAfter=8)))

    story.append(_h1("1. Identificación"))
    story.append(_tbl([
        ['Equipo:', eq.nombre if eq else '—', 'Código:', eq.codigo if eq else '—'],
        ['Magnitud:', mag.nombre, 'Unidad:', mag.unidad or '—'],
        ['EMP:', mag.emp_texto or '—', 'Rango:', f"{mag.rango_min} – {mag.rango_max} {mag.unidad or ''}" if mag.rango_min is not None else '—'],
    ], [3.5, 5.5, 3, 7]))
    story.append(_sp())

    story.append(_h1("2. Decisión sobre verificaciones intermedias"))
    if plan.activo:
        frec_labels = {1:'Mensual',2:'Bimestral',3:'Trimestral',4:'Cuatrimestral',6:'Semestral',12:'Anual'}
        frec_txt = f"{frec_labels.get(plan.frecuencia_meses, '')} — cada {plan.frecuencia_meses} meses"
        story.append(_tbl([
            ['Decisión:', 'SE REALIZAN VERIFICACIONES', 'Frecuencia:', frec_txt],
            ['Procedimiento / norma:', plan.procedimiento or '—', 'Patrón de referencia:', plan.patron_referencia or '—'],
        ], [3.5, 5.5, 3.5, 7]))
        story.append(_sp())
        story.append(_h1("3. Umbrales de alerta (% del EMP)"))
        story.append(_tbl([
            ['Umbral alerta amarilla', 'Umbral fuera de límite rojo'],
            [f"{plan.umbral_alerta_pct}% del EMP", f"{plan.umbral_fuera_pct}% del EMP"],
        ], [9.75, 9.75]))
    else:
        nd_box = Table(
            [['NO SE REALIZAN VERIFICACIONES INTERMEDIAS'],
             [f"Justificación: {plan.justificacion_no_aplica or '—'}"]],
            colWidths=[19.5*cm])
        nd_box.setStyle(TableStyle([
            ('FONTNAME',  (0,0),(0,0),'Helvetica-Bold'),
            ('FONTSIZE',  (0,0),(0,0), 11),
            ('FONTSIZE',  (0,1),(0,1), 9),
            ('TEXTCOLOR', (0,0),(-1,-1), AM),
            ('BACKGROUND',(0,0),(-1,-1), colors.HexColor('#fefce8')),
            ('BOX',       (0,0),(-1,-1), 1.2, AM),
            ('PADDING',   (0,0),(-1,-1), 10),
            ('ALIGN',     (0,0),(0,0),'CENTER'),
        ]))
        story.append(nd_box)

    story.append(_sp())
    story.append(_h1("4. Aprobación del plan"))
    story.append(_tbl([
        ['Aprobado por:', plan.aprobado_por_nombre or '—',
         'Cargo:', plan.aprobado_por_cargo or '—',
         'Fecha:', plan.fecha_aprobacion.strftime('%d/%m/%Y') if plan.fecha_aprobacion else '—'],
    ], [3, 5, 2, 4, 2, 3.5]))
    story.append(_sp(0.8))
    story.append(_h1("5. Firmas"))
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
