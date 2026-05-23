from reportlab.platypus import Table, TableStyle, Image, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas as rl_canvas
from datetime import date
import os

AZ = colors.HexColor('#1a4f8a')
GR = colors.HexColor('#e2e8f0')

DOCS = {
    'analisis':      ('FOR-MET-001','1.0','ANÁLISIS DE RESULTADOS DE CALIBRACIÓN'),
    'verificacion':  ('FOR-MET-002','1.0','VERIFICACIÓN INTERMEDIA'),
    'mantenimiento': ('FOR-MET-003','1.0','REGISTRO DE MANTENIMIENTO'),
    'baja':          ('FOR-MET-004','1.0','ACTA DE BAJA DE EQUIPO'),
    'auditoria':     ('FOR-MET-005','1.0','RESUMEN PARA AUDITORÍA'),
}

def encabezado_controlado(config, tipo_doc):
    cod_def, ver_def, tit_def = DOCS.get(tipo_doc, ('FOR-MET-000','1.0','DOCUMENTO'))
    codigo = getattr(config, f'codigo_formato_{tipo_doc}', cod_def) or cod_def
    version= getattr(config, f'version_{tipo_doc}', ver_def) or ver_def
    nombre = getattr(config, 'nombre', 'Laboratorio') or 'Laboratorio'
    logo   = getattr(config, 'logo_path', None)

    sL = ParagraphStyle('L', fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor('#64748b'))
    sT = ParagraphStyle('T', fontSize=10, fontName='Helvetica-Bold', alignment=TA_CENTER,
                         textColor=colors.HexColor('#0f3460'), leading=13)

    if logo and os.path.exists(logo.lstrip('/')):
        col1 = Image(logo.lstrip('/'), width=4*cm, height=2*cm)
    else:
        col1 = Paragraph(f"<b>{nombre}</b>",
                          ParagraphStyle('P', fontSize=9, alignment=TA_CENTER, textColor=AZ))

    col2_t = Table([[Paragraph(nombre,sL)],[Paragraph(tit_def,sT)]], colWidths=[10*cm])
    col2_t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),2)]))

    elab = getattr(config,'elaborado_por','—') or '—'
    ctrl = Table([['Código:',codigo],['Versión:',version],
                  ['Fecha:',date.today().strftime('%d/%m/%Y')],['Elab.:',elab[:20]]],
                 colWidths=[2.2*cm,2.8*cm])
    ctrl.setStyle(TableStyle([
        ('FONTSIZE',(0,0),(-1,-1),7),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.3,GR),('PADDING',(0,0),(-1,-1),2),
    ]))
    h = Table([[col1,col2_t,ctrl]], colWidths=[4.5*cm,10*cm,5*cm])
    h.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),1,AZ),('INNERGRID',(0,0),(-1,-1),0.5,GR),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),5),
    ]))
    return h

class NumPageCanvas(rl_canvas.Canvas):
    def __init__(self,*a,**k):
        rl_canvas.Canvas.__init__(self,*a,**k); self._saved=[]
    def showPage(self):
        self._saved.append(dict(self.__dict__)); self._startPage()
    def save(self):
        n=len(self._saved)
        for s in self._saved:
            self.__dict__.update(s)
            self.setFont("Helvetica",7); self.setFillColor(colors.HexColor('#94a3b8'))
            self.drawRightString(self._pagesize[0]-2*cm,1.2*cm,f"Página {self._pageNumber} de {n}")
            self.drawString(2*cm,1.2*cm,"MetroGest · Gestión Metrológica")
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)
