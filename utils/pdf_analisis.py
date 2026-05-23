"""
Generador de PDF para análisis de calibración.
"""
import io
from datetime import date, datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak, Image)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

AZ  = colors.HexColor('#0f3460')
AZ2 = colors.HexColor('#1a4f8a')
GR  = colors.HexColor('#64748b')
OK  = colors.HexColor('#16a34a')
FL  = colors.HexColor('#dc2626')
BG  = colors.HexColor('#f8fafc')
GD  = colors.HexColor('#e2e8f0')
AM  = colors.HexColor('#d97706')

def _sty(**k):
    s = getSampleStyleSheet()['Normal']
    return ParagraphStyle(f'_s{hash(str(k))}', parent=s, **k)

def _encabezado(config, tipo='analisis'):
    try:
        from utils.pdf_header import encabezado_controlado
        return encabezado_controlado(config, tipo)
    except Exception:
        return Paragraph("MetroGest — Análisis de Calibración",
                         _sty(fontSize=14, fontName='Helvetica-Bold', textColor=AZ))

def _tabla_info(cal, mag, eq, ci_meses=None):
    data = [
        ['EQUIPO', '', 'CERTIFICADO', ''],
        ['Nombre:', eq.nombre if eq else '—', 'N° Certificado:', cal.numero_certificado or '—'],
        ['Código:', eq.codigo if eq else '—', 'Laboratorio:', cal.laboratorio or '—'],
        ['Marca/Modelo:', f"{eq.marca or ''} {eq.modelo or ''}".strip() or '—' if eq else '—',
         'Acreditación:', cal.acreditacion_laboratorio or '—'],
        ['N° Serie:', eq.numero_serie if eq else '—',
         'Fecha calibración:', cal.fecha_calibracion.strftime('%d/%m/%Y') if cal.fecha_calibracion else '—'],
        ['Magnitud:', mag.nombre if mag else '—',
         'Próxima calibración:', cal.proxima_calibracion.strftime('%d/%m/%Y') if cal.proxima_calibracion else 'Por definir'],
        ['EMP:', mag.emp_texto if mag else '—', 'Método:', cal.metodo_calibracion or '—'],
        ['Tipo instrumento:', (mag.tipo_instrumento or '').title() if mag else '—',
         'Período calibración:', f"{ci_meses} meses" if ci_meses else 'Por definir con ILAC'],
    ]
    t = Table(data, colWidths=[3.2*cm, 5.8*cm, 3.8*cm, 5.8*cm])
    t.setStyle(TableStyle([
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('FONTNAME',      (0,0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND',    (0,0), (-1, 0), AZ2),
        ('TEXTCOLOR',     (0,0), (-1, 0), colors.white),
        ('SPAN',          (0,0),  (1, 0)),
        ('SPAN',          (2,0),  (3, 0)),
        ('ALIGN',         (0,0), (-1, 0), 'CENTER'),
        ('FONTNAME',      (0,1),  (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',      (2,1),  (2,-1), 'Helvetica-Bold'),
        ('GRID',          (0,0), (-1,-1), 0.3, GD),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, BG]),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING',       (0,0), (-1,-1), 5),
    ]))
    return t

def _tabla_puntos(puntos, usar_u=True):
    if usar_u:
        header = ['N°', 'Patrón', 'Indicado', 'Error', 'Tol. inf', 'Tol. sup',
                  'U', '|E|+U', 'EMP', 'Resultado']
    else:
        header = ['N°', 'Patrón', 'Indicado', 'Error', 'Tol. inf', 'Tol. sup',
                  'EMP', 'Resultado']
    rows = [header]
    for p in puntos:
        u = p.incertidumbre or 0
        res = ('✓ APRUEBA' if p.dentro_tolerancia is True
               else '✗ FALLA' if p.dentro_tolerancia is False else 'S/D')
        if usar_u:
            rows.append([
                str(p.numero_punto),
                f"{p.valor_patron:.6g}", f"{p.valor_indicado:.6g}",
                f"{p.error:+.5g}" if p.error is not None else '—',
                f"{p.tolerancia_inf:.4g}" if p.tolerancia_inf is not None else '—',
                f"{p.tolerancia_sup:.4g}" if p.tolerancia_sup is not None else '—',
                f"{u:.4g}" if u else '—',
                f"{p.abs_error_mas_u:.5g}" if p.abs_error_mas_u is not None else '—',
                f"{p.emp_punto:.4g}" if p.emp_punto is not None else '—',
                res,
            ])
        else:
            rows.append([
                str(p.numero_punto),
                f"{p.valor_patron:.6g}", f"{p.valor_indicado:.6g}",
                f"{p.error:+.5g}" if p.error is not None else '—',
                f"{p.tolerancia_inf:.4g}" if p.tolerancia_inf is not None else '—',
                f"{p.tolerancia_sup:.4g}" if p.tolerancia_sup is not None else '—',
                f"{p.emp_punto:.4g}" if p.emp_punto is not None else '—',
                res,
            ])

    if usar_u:
        cw = [0.6, 1.8, 1.8, 1.8, 1.5, 1.5, 1.3, 1.5, 1.5, 2.2]
    else:
        cw = [0.6, 2.0, 2.0, 2.0, 1.8, 1.8, 1.8, 2.5]

    t = Table(rows, colWidths=[c*cm for c in cw])
    sty = TableStyle([
        ('FONTSIZE',      (0,0), (-1,-1), 7),
        ('FONTNAME',      (0,0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND',    (0,0), (-1, 0), AZ2),
        ('TEXTCOLOR',     (0,0), (-1, 0), colors.white),
        ('GRID',          (0,0), (-1,-1), 0.3, GD),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING',       (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, BG]),
    ])
    col_res = len(header) - 1
    for i, p in enumerate(puntos):
        r = i + 1
        if p.dentro_tolerancia is True:
            sty.add('TEXTCOLOR', (col_res,r), (col_res,r), OK)
            sty.add('FONTNAME',  (col_res,r), (col_res,r), 'Helvetica-Bold')
        elif p.dentro_tolerancia is False:
            sty.add('TEXTCOLOR',  (col_res,r), (col_res,r), FL)
            sty.add('FONTNAME',   (col_res,r), (col_res,r), 'Helvetica-Bold')
            sty.add('BACKGROUND', (0,r), (-1,r), colors.HexColor('#fff5f5'))
    t.setStyle(sty)
    return t

def _tabla_regresiones(regresiones, grado_sel):
    if not regresiones:
        return None
    header = ['Grado', 'R²', 'Se', 'Ecuación', 'Estado']
    rows = [header]
    for r in regresiones:
        rows.append([
            f"Grado {r['grado']}",
            f"{r['r2']:.6f}",
            f"{r['se']:.5g}" if r.get('se') else '—',
            (r['ecuacion'][:55] + '…') if len(r['ecuacion']) > 55 else r['ecuacion'],
            '★ Seleccionado' if r['grado'] == grado_sel else '',
        ])
    t = Table(rows, colWidths=[2*cm, 2.5*cm, 2*cm, 9*cm, 4*cm])
    sty = TableStyle([
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('FONTNAME',      (0,0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND',    (0,0), (-1, 0), AZ2),
        ('TEXTCOLOR',     (0,0), (-1, 0), colors.white),
        ('GRID',          (0,0), (-1,-1), 0.3, GD),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, BG]),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING',       (0,0), (-1,-1), 5),
    ])
    for i, r in enumerate(regresiones):
        if r['grado'] == grado_sel:
            sty.add('BACKGROUND', (0,i+1), (-1,i+1), colors.HexColor('#f0fdf4'))
            sty.add('TEXTCOLOR',  (4,i+1), (4,i+1), OK)
            sty.add('FONTNAME',   (4,i+1), (4,i+1), 'Helvetica-Bold')
            sty.add('FONTSIZE',   (4,i+1), (4,i+1), 9)
        else:
            sty.add('TEXTCOLOR',  (4,i+1), (4,i+1), GR)
    t.setStyle(sty)
    return t

def _grafica_matplotlib(puntos, regresiones, grado_sel, titulo, usar_u=True):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None

    x = [p.valor_patron for p in puntos]
    e = [p.error for p in puntos]
    u = [p.incertidumbre or 0 for p in puntos]
    ts = [p.tolerancia_sup for p in puntos]
    ti = [p.tolerancia_inf for p in puntos]
    colores = ['#16a34a' if p.dentro_tolerancia is True
               else '#dc2626' if p.dentro_tolerancia is False
               else '#1a4f8a' for p in puntos]

    fig, ax = plt.subplots(figsize=(11, 5))
    if any(v is not None for v in ts):
        ax.step([x[0]] + x + [x[-1]], [ts[0]] + ts + [ts[-1]],
                where='mid', color='red', lw=1.5, ls='--', label='Tol+', zorder=2)
        ax.step([x[0]] + x + [x[-1]], [ti[0]] + ti + [ti[-1]],
                where='mid', color='blue', lw=1.5, ls='--', label='Tol-', zorder=2)
    ax.axhline(0, color='black', lw=0.8, zorder=2)
    if regresiones and grado_sel:
        reg = next((r for r in regresiones if r['grado'] == grado_sel), None)
        if reg:
            xr = np.linspace(min(x)*0.97, max(x)*1.03, 200)
            yr = np.polyval(reg['coef'], xr) - xr
            ax.plot(xr, yr, '-', color='#e8a020', lw=2,
                    label=f"Regresión grado {grado_sel} (R²={reg['r2']:.4f})", zorder=3)
    if usar_u:
        yerr = u if any(v > 0 for v in u) else None
        if yerr:
            ax.errorbar(x, e, yerr=yerr, fmt='none', ecolor='#1a4f8a',
                        capsize=5, capthick=1.5, lw=1.5, label='U', zorder=4)
    for xi, ei, ci in zip(x, e, colores):
        ax.plot(xi, ei, 'o', color=ci, ms=8, zorder=5)
    ax.plot(x, e, '-', color='#1a4f8a', lw=1.5, label='Error actual', zorder=4)
    ax.set_xlabel('Valor patrón', fontsize=10)
    ax.set_ylabel('Error', fontsize=10)
    ax.set_title(titulo, fontsize=11, fontweight='bold')
    ax.legend(loc='best', fontsize=8, framealpha=0.85)
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────────────────

def generar_pdf_analisis(cal, puntos, regresiones, grado_sel,
                          usuario, config, usar_u=True):
    """
    Genera el PDF completo del análisis de calibración.
    usar_u: si True usa |Error|+U <= EMP, si False usa |Error| <= EMP
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2.5*cm)
    mag = cal.magnitud
    eq  = mag.equipo if mag else None

    story = []
    sp  = lambda h=0.3: Spacer(1, h*cm)
    h1  = lambda t: Paragraph(t, _sty(fontSize=10, fontName='Helvetica-Bold',
                                       textColor=AZ, spaceAfter=4, spaceBefore=6))

    criterio = "|Error| + U ≤ EMP" if usar_u else "|Error| ≤ EMP"

    # ── PÁG 1 ─────────────────────────────────────────────────────────────────
    story.append(_encabezado(config, 'analisis'))
    story.append(sp(0.4))
    story.append(h1("1. Identificación del equipo y del certificado"))
    # Obtener período de calibración si existe
    ci_meses = None
    try:
        if mag and hasattr(mag, 'config_ilac') and mag.config_ilac:
            ci_meses = mag.config_ilac.intervalo_actual_meses
    except Exception:
        pass
    story.append(_tabla_info(cal, mag, eq, ci_meses))
    story.append(sp())

    if cal.temperatura_ambiente or cal.humedad_relativa:
        story.append(h1("2. Condiciones ambientales"))
        t = Table([
            ['Temperatura ambiente', 'Humedad relativa', 'Método'],
            [f"{cal.temperatura_ambiente} °C" if cal.temperatura_ambiente else '—',
             f"{cal.humedad_relativa} %" if cal.humedad_relativa else '—',
             cal.metodo_calibracion or '—'],
        ], colWidths=[5*cm, 5*cm, 9.5*cm])
        t.setStyle(TableStyle([
            ('FONTSIZE',     (0,0), (-1,-1), 8),
            ('FONTNAME',     (0,0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND',   (0,0), (-1, 0), AZ2),
            ('TEXTCOLOR',    (0,0), (-1, 0), colors.white),
            ('GRID',         (0,0), (-1,-1), 0.3, GD),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING',      (0,0), (-1,-1), 5),
        ]))
        story.append(t)
        story.append(sp())

    story.append(h1(f"3. Resultados por punto — Criterio: {criterio}"))
    if puntos:
        story.append(_tabla_puntos(puntos, usar_u))
    else:
        story.append(Paragraph("Sin puntos registrados.", _sty(fontSize=9, textColor=GR)))
    story.append(sp())

    # ── PÁG 2 — Gráfica ───────────────────────────────────────────────────────
    if puntos and len(puntos) >= 2:
        story.append(PageBreak())
        story.append(_encabezado(config, 'analisis'))
        story.append(sp(0.3))
        story.append(h1("4. Gráfica de errores con banda de tolerancia"))
        titulo_graf = f"{mag.nombre if mag else ''} — Cert. {cal.numero_certificado or cal.id}"
        img_bytes = _grafica_matplotlib(puntos, regresiones, grado_sel, titulo_graf, usar_u)
        if img_bytes:
            story.append(Image(io.BytesIO(img_bytes), width=17*cm, height=8.5*cm))
            story.append(sp(0.2))
            u_label = "· Barras: U (incertidumbre expandida)" if usar_u else ""
            story.append(Paragraph(
                f"Verde: conforme · Rojo: no conforme {u_label} · Líneas punteadas: banda ±EMP",
                _sty(fontSize=7, textColor=GR)))
        else:
            story.append(Paragraph(
                "⚠ Gráfica no disponible. Instala matplotlib: pip install matplotlib",
                _sty(fontSize=9, textColor=AM)))

    # ── PÁG 3 — Regresión ─────────────────────────────────────────────────────
    if regresiones:
        story.append(PageBreak())
        story.append(_encabezado(config, 'analisis'))
        story.append(sp(0.3))
        story.append(h1("5. Análisis de regresión polinomial — comparativa R²"))
        t_reg = _tabla_regresiones(regresiones, grado_sel)
        if t_reg:
            story.append(t_reg)
        story.append(sp(0.3))
        if grado_sel:
            rs = next((r for r in regresiones if r['grado'] == grado_sel), None)
            if rs:
                story.append(h1("6. Ecuación de corrección seleccionada"))
                box = Table(
                    [[Paragraph(f"<b>{rs['ecuacion']}</b>",
                                _sty(fontSize=11, fontName='Helvetica-Bold',
                                     textColor=AZ2, alignment=TA_CENTER))],
                     [Paragraph(f"Grado {grado_sel} · R² = {rs['r2']}",
                                _sty(fontSize=8, textColor=GR, alignment=TA_CENTER))]],
                    colWidths=[19.5*cm]
                )
                box.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#eff6ff')),
                    ('BOX',        (0,0), (-1,-1), 1.5, AZ2),
                    ('PADDING',    (0,0), (-1,-1), 10),
                ]))
                story.append(box)

    # ── PÁG FINAL — Veredicto ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(_encabezado(config, 'analisis'))
    story.append(sp(0.3))
    story.append(h1("7. Veredicto de conformidad"))

    ok_c   = sum(1 for p in puntos if p.dentro_tolerancia is True)
    fail_c = sum(1 for p in puntos if p.dentro_tolerancia is False)

    if fail_c == 0 and ok_c > 0:
        vcolor, vbg = OK, colors.HexColor('#f0fdf4')
        vtxt = "✓  EQUIPO APRUEBA LA CALIBRACIÓN"
        vdet = f"Todos los {ok_c} punto(s) cumplen: {criterio}"
    elif fail_c > 0:
        vcolor, vbg = FL, colors.HexColor('#fff5f5')
        vtxt = "✗  EQUIPO NO APRUEBA LA CALIBRACIÓN"
        vdet = f"{fail_c} punto(s) no cumplen: {criterio} · {ok_c} aprueba(n)"
    else:
        vcolor, vbg = AM, colors.HexColor('#fef3c7')
        vtxt = "⚠  ANÁLISIS INCOMPLETO"
        vdet = "Faltan datos de tolerancia en los puntos registrados"

    verdict = Table([[vtxt], [vdet]], colWidths=[19.5*cm])
    verdict.setStyle(TableStyle([
        ('FONTNAME',  (0,0), (0,0), 'Helvetica-Bold'),
        ('FONTSIZE',  (0,0), (0,0), 13),
        ('FONTSIZE',  (0,1), (0,1), 8),
        ('TEXTCOLOR', (0,0), (-1,-1), vcolor),
        ('BACKGROUND',(0,0), (-1,-1), vbg),
        ('BOX',       (0,0), (-1,-1), 2, vcolor),
        ('PADDING',   (0,0), (-1,-1), 12),
        ('ALIGN',     (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(verdict)
    story.append(sp(0.5))

    # Aprobación
    story.append(h1("8. Registro de aprobación"))
    if cal.resultado == 'aprobado' and cal.aprobado_por:
        ap_data = [
            ['Aprobado por:', cal.aprobado_por.nombre,
             'Fecha:', cal.fecha_aprobacion.strftime('%d/%m/%Y %H:%M') if cal.fecha_aprobacion else '—'],
            ['Estado equipo:', 'OPERATIVO — APTO PARA USO', 'Resultado:', 'APROBADO'],
        ]
        ap_bg = colors.HexColor('#f0fdf4')
    else:
        ap_data = [
            ['Aprobado por:', '_' * 35, 'Fecha:', '_' * 20],
            ['Firma:', '', 'Cargo:', ''],
        ]
        ap_bg = colors.white

    ta = Table(ap_data, colWidths=[3.5*cm, 6.5*cm, 3.5*cm, 6*cm])
    ta.setStyle(TableStyle([
        ('FONTNAME',   (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',   (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 8),
        ('GRID',       (0,0), (-1,-1), 0.5, GD),
        ('PADDING',    (0,0), (-1,-1), 7),
        ('BACKGROUND', (0,0), (-1,-1), ap_bg),
        ('ROWHEIGHTS', (0,1), (-1, 1), 1.2*cm),
    ]))
    story.append(ta)
    story.append(sp(0.5))

    # Firmas
    story.append(h1("9. Firmas"))
    elab = getattr(config, 'elaborado_por', '') or ''
    rev  = getattr(config, 'revisado_por',  '') or ''
    apb  = getattr(config, 'aprobado_por',  '') or ''
    tf = Table(
        [['Elaborado por', 'Revisado por', 'Aprobado por'],
         [elab, rev, apb],
         ['', '', ''],
         ['Firma:', 'Firma:', 'Firma:']],
        colWidths=[6.5*cm, 6.5*cm, 6.5*cm]
    )
    tf.setStyle(TableStyle([
        ('FONTNAME',     (0,0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 8),
        ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
        ('GRID',         (0,0), (-1,-1), 0.5, GD),
        ('PADDING',      (0,0), (-1,-1), 6),
        ('BACKGROUND',   (0,0), (-1, 0), BG),
        ('ROWHEIGHTS',   (0,2), (-1, 2), 1.5*cm),
    ]))
    story.append(tf)
    story.append(sp(0.3))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GD))
    story.append(Paragraph(
        f"MetroGest v2.0 · {datetime.now().strftime('%d/%m/%Y %H:%M')} · {usuario.nombre}",
        _sty(fontSize=7, textColor=GR, alignment=TA_CENTER)
    ))

    try:
        from utils.pdf_header import NumPageCanvas
        doc.build(story, canvasmaker=NumPageCanvas)
    except Exception:
        doc.build(story)

    buf.seek(0)
    return buf.read()
