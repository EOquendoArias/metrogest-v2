#!/usr/bin/env python3
"""
seed_demo_data.py — Datos de demostración para MetroGest v2
============================================================
Puebla la BD con 8 equipos de demo realistas, calibraciones históricas,
verificaciones intermedias, mantenimientos y evaluaciones de riesgo ILAC G24.
Idempotente: si se ejecuta dos veces no duplica datos.

Uso (desde la raíz del proyecto):
    python seed_demo_data.py
"""
import sys
import random
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

sys.path.insert(0, ".")
random.seed(42)  # Reproducibilidad

from database import SessionLocal, engine, Base
from models import (
    Equipo, HistorialEstado, MagnitudEquipo,
    Calibracion, PuntoCalibracion,
    EvaluacionRiesgo, ConfigILAC,
    PlanVerificacion, VerificacionIntermedia, PuntoVerificacion,
    PlanMantenimiento, Mantenimiento, Usuario,
)

Base.metadata.create_all(bind=engine)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
HOY          = date.today()
LABORATORIO  = "Laboratorio CENAM Colombia S.A.S."
ACREDITACION = "ONAC 20-LAB-023"
RESPONSABLE  = "Edison Oquendo"
CARGO        = "Responsable Metrológico"
TRAZABILIDAD = (
    "Patrones trazables al Sistema Internacional de Unidades (SI) "
    "a través del Instituto Nacional de Metrología de Colombia (INM)."
)

# Contadores de certificados por año
_cert_counters: dict[str, int] = {}

def _next_cert(fecha: date) -> str:
    yr = str(fecha.year)
    _cert_counters[yr] = _cert_counters.get(yr, 0) + 1
    return f"CERT-{yr}-{_cert_counters[yr]:03d}"

# Contadores de resumen
resumen = dict(equipos=0, calibraciones=0, puntos_cal=0,
               verificaciones=0, planes_mant=0, mantenimientos=0, evaluaciones=0)

# ─────────────────────────────────────────────────────────────────────────────
# DEFINICIÓN DE EQUIPOS
# ─────────────────────────────────────────────────────────────────────────────
EQUIPOS = [
    # ── EQ-002 Balanza analítica ──────────────────────────────────────────────
    {
        "codigo": "EQ-002",
        "nombre": "Balanza analítica",
        "marca": "Mettler Toledo", "modelo": "ME204B", "serie": "123456789",
        "inventario": "INV-002", "area": "Laboratorio",
        "ubicacion": "Mesa de trabajo A, Sala de pesaje",
        "descripcion": "Balanza analítica de alta precisión para pesaje de muestras críticas. Resolución 0.1 mg.",
        "costo": 8500000, "fecha_adq": HOY - relativedelta(years=3),
        "estado": "operativo", "apto": True,
        "mag": {
            "nombre": "Masa", "simbolo": "m", "unidad": "g",
            "rango_min": 0.0, "rango_max": 220.0, "resolucion": "0.1 mg",
            "emp_valor": 0.0003, "emp_unidad": "g", "emp_texto": "±0.3 mg",
            "incert_ref": 0.00005,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=6)],
        "prox_override": None,
        "temps": [21.5, 21.8, 22.0], "hums": [52.0, 51.0, 50.5],
        "verif_proc": "Verificar con pesas certificadas clase E2 de 100 g y 200 g. Registrar desviación respecto al valor de referencia.",
        "verif_patron": "Set de pesas clase E2 certificado ONAC, trazable al SI",
        "mant_trabajo": "Calibración interna, limpieza de platillos, verificación del nivel y ajuste del punto cero.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: limpieza del plato, verificación de nivelación, ajuste del cero con pesada patrón.",
    },
    # ── EQ-004 Calibrador vernier ─────────────────────────────────────────────
    {
        "codigo": "EQ-004",
        "nombre": "Calibrador vernier digital",
        "marca": "Mitutoyo", "modelo": 'CD-6"CSX', "serie": "12345678",
        "inventario": "INV-004", "area": "Producción",
        "ubicacion": "Estación de inspección P-03",
        "descripcion": 'Pie de rey digital 6" (150 mm), resolución 0.01 mm. Control de producto en proceso.',
        "costo": 650000, "fecha_adq": HOY - relativedelta(years=2, months=6),
        "estado": "operativo", "apto": True,
        "mag": {
            "nombre": "Longitud", "simbolo": "L", "unidad": "mm",
            "rango_min": 0.0, "rango_max": 150.0, "resolucion": "0.01 mm",
            "emp_valor": 0.02, "emp_unidad": "mm", "emp_texto": "±0.02 mm",
            "incert_ref": 0.003,
        },
        # Última cal hace ~11.5 meses → próxima en 20 días (!!)
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(days=345)],
        "prox_override": HOY + relativedelta(days=20),
        "temps": [20.5, 20.8, 21.0], "hums": [46.0, 47.5, 48.0],
        "verif_proc": "Verificar con bloques patrón calibrados de 25 mm, 50 mm y 100 mm. Calcular error y comparar con EMP.",
        "verif_patron": "Bloques patrón clase 1, certificado ONAC, trazables al SI",
        "mant_trabajo": "Limpieza de mordientes con paño seco, aplicación de aceite anti-corrosión, verificación del cero.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: limpieza de superficies de medición, lubricación del cursor, verificación de batería y cero.",
    },
    # ── EQ-005 Multímetro digital ─────────────────────────────────────────────
    {
        "codigo": "EQ-005",
        "nombre": "Multímetro digital",
        "marca": "Fluke", "modelo": "87-V", "serie": "99750123",
        "inventario": "INV-005", "area": "Mantenimiento",
        "ubicacion": "Taller eléctrico, armario de herramientas",
        "descripcion": "Multímetro TRMS industrial para mediciones de tensión, corriente y resistencia en instalaciones eléctricas.",
        "costo": 1200000, "fecha_adq": HOY - relativedelta(years=2),
        "estado": "operativo", "apto": True,
        "mag": {
            "nombre": "Tensión DC", "simbolo": "V", "unidad": "V",
            "rango_min": 0.0, "rango_max": 1000.0, "resolucion": "0.1 mV",
            # EMP relativo: 0.5% → emp_valor guarda 0.5 con unidad "% de lectura"
            "emp_valor": 0.005,  # como fracción (0.5%) para cálculos internos
            "emp_unidad": "% de lectura", "emp_texto": "±0.5% de la lectura",
            "incert_ref": 0.001,  # 0.1% de lectura
        },
        # Última cal hace ~11.3 meses → próxima en 25 días (!!)
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(days=340)],
        "prox_override": HOY + relativedelta(days=25),
        "temps": [22.0, 22.5, 23.0], "hums": [56.0, 55.0, 57.0],
        "verif_proc": "Verificar función tensión DC con fuente de referencia calibrada a 250 V, 500 V y 750 V. Registrar error relativo.",
        "verif_patron": "Fuente de referencia de tensión DC calibrada, certificado ONAC",
        "mant_trabajo": "Verificación de baterías, limpieza de conectores y puntas de prueba, comprobación del fusible interno.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: inspección de cables y puntas, sustitución de baterías, limpieza de terminales.",
    },
    # ── EQ-006 Manómetro — CALIBRACIÓN VENCIDA ───────────────────────────────
    {
        "codigo": "EQ-006",
        "nombre": "Manómetro de presión",
        "marca": "Wika", "modelo": "232.50", "serie": "M2024001",
        "inventario": "INV-006", "area": "Utilidades",
        "ubicacion": "Sala de compresores, línea de aire comprimido",
        "descripcion": "Manómetro de proceso para monitoreo de presión de aire comprimido. Fuera de servicio por calibración vencida.",
        "costo": 380000, "fecha_adq": HOY - relativedelta(years=2, months=6),
        "estado": "fuera_de_uso", "apto": False,
        "mag": {
            "nombre": "Presión", "simbolo": "P", "unidad": "bar",
            "rango_min": 0.0, "rango_max": 10.0, "resolucion": "0.01 bar",
            "emp_valor": 0.025,  # 0.25% de 10 bar = 0.025 bar
            "emp_unidad": "bar", "emp_texto": "±0.25% del fondo de escala",
            "incert_ref": 0.005,
        },
        # Última cal hace 7 meses → próxima VENCIDA hace 30 días (X)
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=7)],
        "prox_override": HOY - relativedelta(days=30),
        "temps": [23.0, 23.2, 23.5], "hums": [60.0, 62.0, 63.0],
        "verif_proc": "Verificar con calibrador de presión de referencia a 2.5, 5.0 y 7.5 bar. Registrar error absoluto.",
        "verif_patron": "Calibrador de presión Fluke 718 300G, certificado ONAC",
        "mant_trabajo": "Inspección de carcasa y carátula, limpieza del conector, verificación de la escala de lectura.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: inspección visual, limpieza del cuerpo, prueba de estanqueidad.",
    },
    # ── EQ-007 Higrómetro ─────────────────────────────────────────────────────
    {
        "codigo": "EQ-007",
        "nombre": "Higrómetro digital",
        "marca": "Testo", "modelo": "608-H2", "serie": "T20240056",
        "inventario": "INV-007", "area": "Almacén",
        "ubicacion": "Almacén de materia prima, zona de acondicionamiento",
        "descripcion": "Sensor combinado de temperatura y humedad relativa para monitoreo de condiciones ambientales.",
        "costo": 750000, "fecha_adq": HOY - relativedelta(years=2),
        "estado": "operativo", "apto": True,
        "mag": {
            "nombre": "Humedad relativa", "simbolo": "HR", "unidad": "% HR",
            "rango_min": 10.0, "rango_max": 95.0, "resolucion": "0.1 % HR",
            "emp_valor": 2.0, "emp_unidad": "% HR", "emp_texto": "±2% HR",
            "incert_ref": 0.3,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=6)],
        "prox_override": None,
        "temps": [20.0, 20.2, 20.5], "hums": [48.0, 50.0, 52.0],
        "verif_proc": "Verificar con soluciones salinas saturadas de referencia (NaCl 75.5% HR, KCl 84.3% HR) a los puntos medios.",
        "verif_patron": "Soluciones salinas saturadas certificadas; higrómetro patrón calibrado ONAC",
        "mant_trabajo": "Limpieza del sensor con paño seco, verificación de pantalla y reemplazo de baterías.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: limpieza del sensor con aire seco, verificación de calibración interna, sustitución de baterías.",
    },
    # ── EQ-008 Cronómetro ─────────────────────────────────────────────────────
    {
        "codigo": "EQ-008",
        "nombre": "Cronómetro de laboratorio",
        "marca": "Hanhart", "modelo": "1/100 Ratoamt", "serie": "H98765",
        "inventario": "INV-008", "area": "Calidad",
        "ubicacion": "Laboratorio de control de calidad",
        "descripcion": "Cronómetro de precisión 1/100 s para medición de tiempos de proceso en ensayos de calidad.",
        "costo": 420000, "fecha_adq": HOY - relativedelta(years=2, months=9),
        "estado": "operativo", "apto": True,
        "mag": {
            "nombre": "Tiempo", "simbolo": "t", "unidad": "s",
            "rango_min": 0.0, "rango_max": 3600.0, "resolucion": "0.01 s",
            "emp_valor": 0.1, "emp_unidad": "s", "emp_texto": "±0.1 s",
            "incert_ref": 0.01,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=6)],
        "prox_override": None,
        "temps": [21.0, 21.3, 21.5], "hums": [51.0, 52.0, 53.5],
        "verif_proc": "Comparar con señal de tiempo GPS a intervalos de 15 min, 30 min y 60 min. Registrar error acumulado.",
        "verif_patron": "Receptor GPS con salida 1PPS, resolución 0.01 s",
        "mant_trabajo": "Verificación de botones de inicio/parada, limpieza de pantalla LCD y reemplazo preventivo de batería.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: comprobación de botones, reemplazo de batería, limpieza de pantalla, prueba de precisión.",
    },
    # ── EQ-009 Nivel de precisión ─────────────────────────────────────────────
    {
        "codigo": "EQ-009",
        "nombre": "Nivel de precisión",
        "marca": "Stabila", "modelo": "196-2S", "serie": "S2023112",
        "inventario": "INV-009", "area": "Metrología",
        "ubicacion": "Sala de metrología, armario de patrones",
        "descripcion": "Nivel digital de precisión para verificación de horizontalidad y verticalidad de equipos de producción.",
        "costo": 950000, "fecha_adq": HOY - relativedelta(years=2, months=3),
        "estado": "operativo", "apto": True,
        "mag": {
            "nombre": "Ángulo", "simbolo": "α", "unidad": "°",
            "rango_min": -60.0, "rango_max": 60.0, "resolucion": "0.01 °",
            "emp_valor": 0.02, "emp_unidad": "°", "emp_texto": "±0.02°",
            "incert_ref": 0.003,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=6)],
        "prox_override": None,
        "temps": [20.5, 21.0, 21.5], "hums": [45.0, 47.0, 48.0],
        "verif_proc": "Verificar con tabla de senos calibrada a ±10°, ±30° y 0°. Comparar lectura con ángulo de referencia calculado.",
        "verif_patron": "Tabla de senos de alta precisión con bloques patrón calibrados ONAC",
        "mant_trabajo": "Limpieza de superficies de apoyo, verificación de hermeticidad de ampolla, comprobación de batería y display.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: limpieza de superficies, verificación de ampolla, comprobación de batería y calibración digital.",
    },
    # ── EQ-010 Pipeta volumétrica ─────────────────────────────────────────────
    {
        "codigo": "EQ-010",
        "nombre": "Pipeta volumétrica",
        "marca": "Brand", "modelo": "Transferpette", "serie": "PV2024005",
        "inventario": "INV-010", "area": "Laboratorio",
        "ubicacion": "Laboratorio químico, área de micropipeteo",
        "descripcion": "Pipeta monocanal 1–10 mL para dosificación de reactivos en análisis fisicoquímicos.",
        "costo": 320000, "fecha_adq": HOY - relativedelta(years=1, months=8),
        "estado": "operativo", "apto": True,
        "mag": {
            "nombre": "Volumen", "simbolo": "V", "unidad": "mL",
            "rango_min": 1.0, "rango_max": 10.0, "resolucion": "0.01 mL",
            "emp_valor": 0.02, "emp_unidad": "mL", "emp_texto": "±0.02 mL",
            "incert_ref": 0.003,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=6)],
        "prox_override": None,
        "temps": [22.0, 22.2, 22.5], "hums": [53.0, 54.0, 56.0],
        "verif_proc": "Método gravimétrico a 3.0, 5.0 y 8.0 mL con agua destilada a 20°C y balanza analítica calibrada.",
        "verif_patron": "Balanza analítica EQ-002 (ME204B), agua destilada destilada a temperatura controlada",
        "mant_trabajo": "Inspección de émbolo y O-ring, limpieza del cuerpo y boquilla, verificación del volumen dispensado.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: inspección de émbolo y sellos, limpieza de boquilla, verificación gravimétrica.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — GENERACIÓN DE PUNTOS
# ─────────────────────────────────────────────────────────────────────────────

def _puntos_patron(mag: dict, n: int = 5) -> list[float]:
    """Distribuye n puntos sobre el rango de la magnitud."""
    nombre = mag["nombre"]
    rmin, rmax = mag["rango_min"], mag["rango_max"]
    if nombre == "Tensión DC":
        return [100.0, 250.0, 500.0, 750.0, 1000.0]
    if nombre == "Ángulo":
        return [-60.0, -30.0, 0.0, 30.0, 60.0]
    if nombre == "Volumen":
        return [1.0, 3.0, 5.0, 7.5, 10.0]
    if nombre == "Tiempo":
        return [900.0, 1800.0, 2700.0, 3600.0, 60.0]
    step = (rmax - rmin) / (n - 1)
    return [round(rmin + i * step, 5) for i in range(n)]


def _emp_en_punto(mag: dict, vp: float) -> float:
    """Devuelve el EMP absoluto en la unidad de la magnitud para el punto vp."""
    if mag["nombre"] == "Tensión DC":
        return mag["emp_valor"] * abs(vp)   # emp_valor = 0.005 = 0.5%
    return mag["emp_valor"]


def _incert_en_punto(mag: dict, vp: float) -> float:
    """Devuelve la incertidumbre en el punto."""
    if mag["nombre"] == "Tensión DC":
        return mag["incert_ref"] * abs(vp)
    return mag["incert_ref"]


def generar_puntos_calibracion(mag: dict) -> list[dict]:
    puntos = []
    for i, vp in enumerate(_puntos_patron(mag)):
        emp = _emp_en_punto(mag, vp)
        u   = _incert_en_punto(mag, vp)
        # Error: dentro del 60% del EMP, centrado en cero
        error = round(random.uniform(-emp * 0.55, emp * 0.55), 8)
        vi    = round(vp + error, 8)
        abs_eu = round(abs(error) + u, 8)
        puntos.append(dict(
            numero_punto      = i + 1,
            valor_patron      = round(vp, 6),
            valor_indicado    = round(vi, 6),
            error             = round(error, 6),
            tolerancia_inf    = round(-emp, 6),
            tolerancia_sup    = round(emp, 6),
            incertidumbre     = round(u, 6),
            abs_error_mas_u   = round(abs_eu, 6),
            emp_punto         = round(emp, 6),
            dentro_tolerancia = bool(abs_eu <= emp),
        ))
    return puntos


def generar_puntos_verificacion(mag: dict) -> tuple[list[dict], float]:
    """Devuelve (lista_puntos, max_desviacion_pct)."""
    nombre = mag["nombre"]
    rmin, rmax = mag["rango_min"], mag["rango_max"]
    if nombre == "Tensión DC":
        pts_pat = [250.0, 500.0, 750.0]
    elif nombre == "Ángulo":
        pts_pat = [-30.0, 0.0, 30.0]
    elif nombre == "Volumen":
        pts_pat = [3.0, 5.0, 8.0]
    elif nombre == "Tiempo":
        pts_pat = [900.0, 1800.0, 3600.0]
    else:
        step = (rmax - rmin) / 4.0
        pts_pat = [round(rmin + step, 4), round(rmin + 2*step, 4), round(rmin + 3*step, 4)]

    puntos, max_desv = [], 0.0
    for i, vp in enumerate(pts_pat):
        emp = _emp_en_punto(mag, vp)
        # Error ≤ 45% del EMP → resultado "ok"
        error  = random.uniform(-emp * 0.45, emp * 0.45)
        vi     = round(vp + error, 6)
        desv   = round((abs(error) / emp * 100), 2) if emp > 0 else 0.0
        max_desv = max(max_desv, desv)
        puntos.append(dict(
            numero_punto   = i + 1,
            valor_patron   = round(vp, 4),
            valor_indicado = round(vi, 6),
            error          = round(error, 6),
            tolerancia_inf = round(-emp, 6),
            tolerancia_sup = round(emp, 6),
            desviacion_pct = desv,
            resultado      = "ok",
        ))
    return puntos, round(max_desv, 2)


# ─────────────────────────────────────────────────────────────────────────────
# CREACIÓN DE UN EQUIPO CON TODOS SUS DATOS
# ─────────────────────────────────────────────────────────────────────────────

def crear_equipo(db, ed: dict, admin_id: int) -> None:
    # Idempotencia
    if db.query(Equipo).filter(Equipo.codigo == ed["codigo"]).first():
        print(f"  [SKIP]  {ed['codigo']} ya existe — omitiendo")
        return

    print(f"  [+]  Creando {ed['codigo']} — {ed['nombre']}")

    # ── Equipo ────────────────────────────────────────────────────────────────
    eq = Equipo(
        codigo=ed["codigo"], nombre=ed["nombre"],
        descripcion=ed.get("descripcion"),
        marca=ed.get("marca"), modelo=ed.get("modelo"),
        numero_serie=ed.get("serie"),
        numero_inventario=ed.get("inventario"),
        fecha_adquisicion=ed.get("fecha_adq"),
        costo=ed.get("costo"),
        area=ed.get("area"), ubicacion=ed.get("ubicacion"),
        responsable=RESPONSABLE,
        estado=ed["estado"],
        apto_para_uso=ed["apto"],
        confirmacion_metrologica=ed["apto"],
    )
    db.add(eq); db.flush()
    resumen["equipos"] += 1

    # Historial de estado
    db.add(HistorialEstado(
        equipo_id=eq.id, usuario_id=admin_id,
        estado_nuevo="en_espera_calibracion",
        motivo="Registro inicial del equipo en MetroGest",
    ))
    if ed["estado"] == "operativo":
        db.add(HistorialEstado(
            equipo_id=eq.id, usuario_id=admin_id,
            estado_anterior="en_espera_calibracion", estado_nuevo="operativo",
            motivo="Equipo habilitado tras calibración inicial satisfactoria",
        ))
    elif ed["estado"] == "fuera_de_uso":
        db.add(HistorialEstado(
            equipo_id=eq.id, usuario_id=admin_id,
            estado_anterior="operativo", estado_nuevo="fuera_de_uso",
            motivo="Calibración vencida — equipo retirado hasta nueva calibración",
        ))

    # ── Magnitud ──────────────────────────────────────────────────────────────
    m = ed["mag"]
    mag = MagnitudEquipo(
        equipo_id=eq.id,
        nombre=m["nombre"], simbolo=m.get("simbolo"), unidad=m.get("unidad"),
        rango_min=m.get("rango_min"), rango_max=m.get("rango_max"),
        resolucion=m.get("resolucion"),
        emp_valor=m.get("emp_valor"), emp_unidad=m.get("emp_unidad"),
        emp_texto=m.get("emp_texto"),
        tipo_instrumento="continuo",
        umbral_alerta_pct=80.0, umbral_fuera_pct=100.0,
        activa=True, orden=1,
        notas=f"Magnitud principal de {ed['nombre']}",
    )
    db.add(mag); db.flush()

    # ── Calibraciones (3 históricas) ──────────────────────────────────────────
    cal_fechas   = ed["cal_fechas"]
    prox_override = ed.get("prox_override")

    for i, fecha_cal in enumerate(cal_fechas):
        # Fecha próxima calibración
        if i < len(cal_fechas) - 1:
            prox_cal = fecha_cal + relativedelta(months=12)
        else:
            prox_cal = prox_override if prox_override else fecha_cal + relativedelta(months=12)

        cert = _next_cert(fecha_cal)

        cal = Calibracion(
            magnitud_id=mag.id, equipo_id=eq.id,
            numero_certificado=cert,
            laboratorio=LABORATORIO,
            acreditacion_laboratorio=ACREDITACION,
            fecha_calibracion=fecha_cal,
            proxima_calibracion=prox_cal,
            patrones_utilizados=f"Patrones de referencia trazables al SI — Serie {cert}",
            metodo_calibracion="Método de comparación directa con patrón de referencia",
            temperatura_ambiente=ed["temps"][i],
            humedad_relativa=ed["hums"][i],
            trazabilidad=TRAZABILIDAD,
            observaciones=(
                f"Calibración N°{i+1}. Condiciones ambientales dentro de los rangos establecidos. "
                f"Todos los puntos dentro de la EMP."
            ),
            certificado_path=f"/static/certificados/{cert}.pdf",
            costo=round(random.uniform(250000, 650000), -3),
            resultado="aprobado",
            grado_regresion_sel=1,
            metodo_analisis=ed.get("metodo_analisis", "regresion"),
            usar_incertidumbre=True,
            metodo_periodo="evaluacion_riesgo",
            justificacion_periodo="Intervalo determinado según evaluación de riesgo ILAC G24.",
            aprobado_por_id=admin_id,
            fecha_aprobacion=datetime.combine(fecha_cal, datetime.min.time()),
        )
        db.add(cal); db.flush()
        resumen["calibraciones"] += 1

        for pt in generar_puntos_calibracion(m):
            db.add(PuntoCalibracion(calibracion_id=cal.id, **pt))
            resumen["puntos_cal"] += 1

    # ── Evaluación de riesgo ILAC G24 ─────────────────────────────────────────
    factores = dict(
        f_incertidumbre=3, f_tipo=2, f_riesgo_emp=3, f_fabricante=2,
        f_deriva=2, f_uso=3, f_ambiental=2, f_magnitud=3,
        f_similares=3, f_comparaciones=2, f_verificaciones=2,
        f_transporte=1, f_personal=2, f_legal=3,
    )
    puntuacion = sum(factores.values())  # = 31
    db.add(EvaluacionRiesgo(
        magnitud_id=mag.id,
        **factores,
        intervalo_fabricante_meses=12,
        puntuacion_total=float(puntuacion),
        intervalo_sugerido_meses=12,
        intervalo_adoptado_meses=12,
        justificacion=(
            f"Intervalo de 12 meses adoptado según evaluación de riesgo ILAC G24. "
            f"Puntuación total: {puntuacion}/70. Nivel de riesgo moderado."
        ),
        evaluado_por=RESPONSABLE,
        fecha_evaluacion=HOY - relativedelta(months=6),
    ))
    resumen["evaluaciones"] += 1

    # ── Config ILAC ───────────────────────────────────────────────────────────
    db.add(ConfigILAC(
        magnitud_id=mag.id,
        metodo="m1",
        intervalo_inicial_meses=12, intervalo_actual_meses=12,
        intervalo_minimo_meses=6,   intervalo_maximo_meses=24,
        porcentaje_escalera=80.0,
        horas_uso_acumuladas=0.0,
    ))

    # ── Plan de verificaciones ────────────────────────────────────────────────
    plan_v = PlanVerificacion(
        magnitud_id=mag.id, equipo_id=eq.id,
        frecuencia_meses=3,
        procedimiento=ed.get("verif_proc", "Verificación por comparación con patrón interno."),
        patron_referencia=ed.get("verif_patron", "Patrón interno de referencia calibrado"),
        umbral_alerta_pct=70.0, umbral_fuera_pct=100.0,
        activo=True,
        aprobado_por_nombre=RESPONSABLE,
        aprobado_por_cargo=CARGO,
        fecha_aprobacion=HOY - relativedelta(months=6),
    )
    db.add(plan_v); db.flush()

    # ── Verificaciones intermedias (2) ────────────────────────────────────────
    for j, offset_meses in enumerate([3, 1]):
        fecha_v = HOY - relativedelta(months=offset_meses)
        pts_v, max_desv = generar_puntos_verificacion(m)
        verif = VerificacionIntermedia(
            plan_id=plan_v.id, equipo_id=eq.id, magnitud_id=mag.id,
            fecha=fecha_v,
            proxima_verificacion=fecha_v + relativedelta(months=3),
            tipo="programada",
            realizada_por=RESPONSABLE,
            patron_usado=ed.get("verif_patron", "Patrón interno calibrado"),
            resultado="aprobado",
            accion_tomada="ninguna",
            observaciones=(
                f"Verificación N°{j+1}. Todos los puntos dentro de tolerancia. "
                f"Desviación máxima registrada: {max_desv:.1f}% del EMP."
            ),
            max_desviacion_pct=max_desv,
        )
        db.add(verif); db.flush()
        resumen["verificaciones"] += 1

        for pt_v in pts_v:
            db.add(PuntoVerificacion(verificacion_id=verif.id, **pt_v))

    # ── Plan de mantenimiento ─────────────────────────────────────────────────
    db.add(PlanMantenimiento(
        equipo_id=eq.id,
        frecuencia_meses=6, tipo="preventivo",
        descripcion=ed.get("plan_mant_desc", "Mantenimiento preventivo semestral."),
        responsable=RESPONSABLE, activo=True,
    ))
    resumen["planes_mant"] += 1

    # ── Registros de mantenimiento (2 completados) ────────────────────────────
    codigo_num = ed["codigo"].split("-")[-1]  # "002", "004", etc.
    for k, offset_meses in enumerate([12, 6]):
        fecha_m = HOY - relativedelta(months=offset_meses)
        anio_ot = (HOY - relativedelta(months=offset_meses)).year
        db.add(Mantenimiento(
            equipo_id=eq.id,
            tipo="preventivo", origen="plan",
            titulo=f"Mantenimiento preventivo semestral — {ed['nombre']}",
            descripcion=ed.get("plan_mant_desc"),
            responsable_interno=RESPONSABLE,
            orden_trabajo=f"OT-{anio_ot}-{codigo_num}-{k+1:02d}",
            fecha_programada=fecha_m,
            fecha_inicio=fecha_m,
            fecha_fin=fecha_m + relativedelta(days=1),
            estado="completado",
            trabajo_realizado=ed.get("mant_trabajo", "Mantenimiento preventivo ejecutado según plan."),
            costo=round(random.uniform(80000, 250000), -3),
            requiere_calibracion=False,
            afecta_medicion=False,
            observaciones_metrologicas="Equipo en condiciones normales de operación tras el mantenimiento.",
        ))
        resumen["mantenimientos"] += 1

    db.flush()


# ─────────────────────────────────────────────────────────────────────────────
# PESAS PATRÓN E2 (EQ-011 a EQ-019)
# ─────────────────────────────────────────────────────────────────────────────
# Tolerancias OIML clase E2 (en gramos)
_EMP_E2 = {500: 3e-4, 200: 1e-4, 100: 1e-4, 50: 6e-5,
            20: 3e-5, 10: 2e-5, 5: 1.5e-5, 2: 1.2e-5, 1: 1e-5}
# Correcciones realistas en gramos (dentro del EMP)
_CORR_E2 = {500: +2.5e-4, 200: -0.8e-4, 100: +1.5e-4, 50: -0.5e-5*6,
             20: +0.9e-5*3, 10: -0.5e-5*2, 5: +0.8e-5*1.5, 2: -0.9e-5*1.2, 1: +0.6e-5}

PESAS_E2 = [
    {"codigo": "EQ-011", "valor_g": 500, "serie": "PE2-2024-500",
     "estado": "operativo", "apto": True, "prox_dias": None},
    {"codigo": "EQ-012", "valor_g": 200, "serie": "PE2-2024-200",
     "estado": "operativo", "apto": True, "prox_dias": None},
    {"codigo": "EQ-013", "valor_g": 100, "serie": "PE2-2024-100",
     "estado": "operativo", "apto": True, "prox_dias": None},
    {"codigo": "EQ-014", "valor_g": 50,  "serie": "PE2-2024-050",
     "estado": "operativo", "apto": True, "prox_dias": None},
    {"codigo": "EQ-015", "valor_g": 20,  "serie": "PE2-2024-020",
     "estado": "operativo", "apto": True, "prox_dias": None},
    {"codigo": "EQ-016", "valor_g": 10,  "serie": "PE2-2024-010",
     "estado": "operativo", "apto": True, "prox_dias": None},
    {"codigo": "EQ-017", "valor_g": 5,   "serie": "PE2-2024-005",
     "estado": "operativo", "apto": True, "prox_dias": None},
    {"codigo": "EQ-018", "valor_g": 2,   "serie": "PE2-2024-002",
     "estado": "operativo", "apto": True, "prox_dias": 28},   # alerta ⚠
    {"codigo": "EQ-019", "valor_g": 1,   "serie": "PE2-2024-001",
     "estado": "en_espera_calibracion", "apto": False, "sin_cal": True},
]

CERT_PESAS = "CERT-PESAS-2024-001"
FECHA_PESAS = HOY - relativedelta(months=8)


def crear_pesa(db, pd_: dict, admin_id: int) -> None:
    if db.query(Equipo).filter(Equipo.codigo == pd_["codigo"]).first():
        print(f"  [SKIP]  {pd_['codigo']} ya existe")
        return

    vg  = pd_["valor_g"]
    emp = _EMP_E2[vg]
    corr = _CORR_E2[vg]

    print(f"  [+]  Creando {pd_['codigo']} — Pesa E2 {vg} g")

    eq = Equipo(
        codigo=pd_["codigo"],
        nombre=f"Pesa patron E2 — {vg} g",
        descripcion=(
            f"Pertenece al Juego de Pesas Patron E2 — Certificado {CERT_PESAS}. "
            f"Cada pesa se gestiona como instrumento independiente."
        ),
        marca="Radwag", modelo="E2 OIML", numero_serie=pd_["serie"],
        numero_inventario=f"INV-{pd_['codigo'][3:]}",
        area="Laboratorio", ubicacion="Caja de pesas, armario de patrones",
        responsable=RESPONSABLE,
        estado=pd_["estado"], apto_para_uso=pd_["apto"],
        confirmacion_metrologica=pd_["apto"],
        fecha_adquisicion=HOY - relativedelta(years=1),
        costo=round(vg * 15000, -3),
    )
    db.add(eq); db.flush()
    resumen["equipos"] += 1

    db.add(HistorialEstado(
        equipo_id=eq.id, usuario_id=admin_id,
        estado_nuevo="en_espera_calibracion",
        motivo="Registro inicial del juego de pesas patron E2",
    ))
    if pd_["estado"] == "operativo":
        db.add(HistorialEstado(
            equipo_id=eq.id, usuario_id=admin_id,
            estado_anterior="en_espera_calibracion", estado_nuevo="operativo",
            motivo=f"Habilitada tras calibración INM — {CERT_PESAS}",
        ))

    if pd_.get("sin_cal"):
        db.flush(); return   # EQ-019: sin calibración

    mag = MagnitudEquipo(
        equipo_id=eq.id,
        nombre="Masa", simbolo="m", unidad="g",
        rango_min=round(vg * 0.999, 6), rango_max=round(vg * 1.001, 6),
        resolucion="0.01 mg",
        emp_valor=emp, emp_unidad="g",
        emp_texto=f"±{emp*1000:.3f} mg",
        tipo_instrumento="discreto",
        umbral_alerta_pct=80.0, umbral_fuera_pct=100.0,
        activa=True, orden=1,
        notas=f"Valor nominal: {vg} g, clase E2 OIML",
    )
    db.add(mag); db.flush()

    # Proxima calibración
    if pd_["prox_dias"] is not None:
        prox = HOY + relativedelta(days=pd_["prox_dias"])
    else:
        prox = FECHA_PESAS + relativedelta(months=24)   # 16 meses desde hace 8 = +16m

    cal = Calibracion(
        magnitud_id=mag.id, equipo_id=eq.id,
        numero_certificado=CERT_PESAS,
        laboratorio="Instituto Nacional de Metrologia de Colombia — INM",
        acreditacion_laboratorio="ONAC 20-LAB-001",
        fecha_calibracion=FECHA_PESAS,
        proxima_calibracion=prox,
        patrones_utilizados="Patrones primarios del INM, trazables al SI",
        metodo_calibracion="Comparacion directa con patron de masa de referencia",
        temperatura_ambiente=20.5, humedad_relativa=50.0,
        trazabilidad=TRAZABILIDAD,
        observaciones=f"Pesa {vg} g — Corrección convencional: {corr*1000:+.4f} mg",
        certificado_path=f"/static/certificados/{CERT_PESAS}.pdf",
        costo=0.0,   # Costo compartido en el juego
        resultado="aprobado",
        grado_regresion_sel=None,
        metodo_analisis="lagrange",
        usar_incertidumbre=True,
        metodo_periodo="evaluacion_riesgo",
        justificacion_periodo="Juego de pesas patron, intervalo 24 meses segun OIML.",
        aprobado_por_id=admin_id,
        fecha_aprobacion=datetime.combine(FECHA_PESAS, datetime.min.time()),
    )
    db.add(cal); db.flush()
    resumen["calibraciones"] += 1

    # 1 punto: valor nominal con corrección
    vi = round(vg + corr, 8)
    err = round(corr, 8)
    aeu = round(abs(err) + emp * 0.2, 8)
    db.add(PuntoCalibracion(
        calibracion_id=cal.id, numero_punto=1,
        valor_patron=float(vg), valor_indicado=vi, error=err,
        tolerancia_inf=round(-emp, 8), tolerancia_sup=round(emp, 8),
        incertidumbre=round(emp * 0.2, 8),
        abs_error_mas_u=aeu, emp_punto=round(emp, 8),
        dentro_tolerancia=bool(aeu <= emp),
        observacion=f"Corrección convencional: {corr*1000:+.4f} mg",
    ))
    resumen["puntos_cal"] += 1

    # Evaluación riesgo (simplificada para pesas)
    factores = dict(f_incertidumbre=2, f_tipo=1, f_riesgo_emp=2, f_fabricante=2,
                    f_deriva=1, f_uso=2, f_ambiental=1, f_magnitud=2,
                    f_similares=3, f_comparaciones=2, f_verificaciones=3,
                    f_transporte=2, f_personal=1, f_legal=3)
    db.add(EvaluacionRiesgo(
        magnitud_id=mag.id, **factores,
        intervalo_fabricante_meses=24,
        puntuacion_total=float(sum(factores.values())),
        intervalo_sugerido_meses=24, intervalo_adoptado_meses=24,
        justificacion="Pesa patron clase E2 OIML. Intervalo 24 meses segun norma.",
        evaluado_por=RESPONSABLE, fecha_evaluacion=FECHA_PESAS,
    ))
    resumen["evaluaciones"] += 1

    db.add(ConfigILAC(
        magnitud_id=mag.id, metodo="m1",
        intervalo_inicial_meses=24, intervalo_actual_meses=24,
        intervalo_minimo_meses=12, intervalo_maximo_meses=36,
        porcentaje_escalera=80.0, horas_uso_acumuladas=0.0,
    ))
    db.flush()


# ─────────────────────────────────────────────────────────────────────────────
# EQUIPOS ADICIONALES (EQ-020 a EQ-025)
# ─────────────────────────────────────────────────────────────────────────────
EQUIPOS_EXTRA = [
    # EQ-020 Micrómetro exterior — calibrado
    {
        "codigo": "EQ-020", "nombre": "Micrometro exterior",
        "marca": "Mitutoyo", "modelo": "103-137", "serie": "MT2023445",
        "inventario": "INV-020", "area": "Produccion",
        "ubicacion": "Estacion de inspeccion P-01",
        "descripcion": "Micrometro de exteriores 0–25 mm, resolución 0.001 mm. Control dimensional de piezas maquinadas.",
        "costo": 850000, "fecha_adq": HOY - relativedelta(years=2, months=1),
        "estado": "operativo", "apto": True,
        "metodo_analisis": "regresion",
        "mag": {
            "nombre": "Longitud", "simbolo": "L", "unidad": "mm",
            "rango_min": 0.0, "rango_max": 25.0, "resolucion": "0.001 mm",
            "emp_valor": 0.004, "emp_unidad": "mm", "emp_texto": "±0.004 mm",
            "incert_ref": 0.0008,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=6)],
        "prox_override": None,
        "temps": [20.1, 20.3, 20.5], "hums": [44.0, 46.0, 47.0],
        "verif_proc": "Verificar con bloques patron de 5 mm, 12.5 mm y 20 mm. Registrar error en cada punto.",
        "verif_patron": "Bloques patron clase 1, trazables al SI",
        "mant_trabajo": "Limpieza de espiga y yunque con paño seco, aplicacion de aceite, verificacion del cero.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: limpieza y lubricacion, verificacion de cero, inspeccion de tornillo micrometrico.",
    },
    # EQ-021 pH-metro — calibrado, LAGRANGE
    {
        "codigo": "EQ-021", "nombre": "pH-metro de laboratorio",
        "marca": "Hanna", "modelo": "HI2210", "serie": "HI20240078",
        "inventario": "INV-021", "area": "Laboratorio",
        "ubicacion": "Laboratorio quimico, area de medicion de pH",
        "descripcion": "pH-metro de precision con electrodo combinado. Uso en analisis de aguas y soluciones acuosas.",
        "costo": 980000, "fecha_adq": HOY - relativedelta(years=1, months=10),
        "estado": "operativo", "apto": True,
        "metodo_analisis": "lagrange",
        "mag": {
            "nombre": "pH", "simbolo": "pH", "unidad": "pH",
            "rango_min": 0.0, "rango_max": 14.0, "resolucion": "0.01 pH",
            "emp_valor": 0.05, "emp_unidad": "pH", "emp_texto": "+/-0.05 pH",
            "incert_ref": 0.01,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=6)],
        "prox_override": None,
        "temps": [25.0, 25.0, 25.0], "hums": [55.0, 56.0, 57.0],
        "verif_proc": "Verificar con buffers certificados de pH 4.01, 7.00 y 10.01 a 25 grados C.",
        "verif_patron": "Buffers de pH certificados NIST, pH 4.01, 7.00 y 10.01",
        "mant_trabajo": "Limpieza del electrodo con solucion HCl 0.1M, recarga de KCl, calibracion de 3 puntos.",
        "plan_mant_desc": "Mantenimiento preventivo trimestral: limpieza y reacondicionamiento del electrodo, calibracion con 3 buffers.",
    },
    # EQ-022 Luxómetro — ALERTA, LAGRANGE
    {
        "codigo": "EQ-022", "nombre": "Luxometro digital",
        "marca": "Testo", "modelo": "545", "serie": "TE20230234",
        "inventario": "INV-022", "area": "HSEQ",
        "ubicacion": "Deposito de HSEQ, equipos de medicion ambiental",
        "descripcion": "Luxometro digital para evaluacion de niveles de iluminacion en puestos de trabajo segun norma.",
        "costo": 620000, "fecha_adq": HOY - relativedelta(years=2, months=4),
        "estado": "operativo", "apto": True,
        "metodo_analisis": "lagrange",
        "mag": {
            "nombre": "Iluminancia", "simbolo": "E", "unidad": "lux",
            "rango_min": 0.0, "rango_max": 100000.0, "resolucion": "1 lux",
            "emp_valor": 3.0,   # 3% del fondo de escala para simplificar
            "emp_unidad": "% de lectura", "emp_texto": "+/-3% de la lectura",
            "incert_ref": 0.005,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(days=338)],
        "prox_override": HOY + relativedelta(days=22),   # alerta ⚠
        "temps": [23.0, 23.0, 23.5], "hums": [50.0, 52.0, 53.0],
        "verif_proc": "Verificar con lampara de referencia calibrada a 500, 1000 y 2000 lux. Registrar error relativo.",
        "verif_patron": "Fuente de iluminacion de referencia calibrada, trazable al SI",
        "mant_trabajo": "Limpieza de la celula fotoelectrica con paño optico, verificacion de la respuesta espectral.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: limpieza de la celula, verificacion de bateria, comprobacion de respuesta.",
    },
    # EQ-023 Anemómetro — ALERTA, regresion
    {
        "codigo": "EQ-023", "nombre": "Anemometro digital",
        "marca": "Testo", "modelo": "416", "serie": "TE20240156",
        "inventario": "INV-023", "area": "HSEQ",
        "ubicacion": "Deposito de HSEQ, equipos de medicion ambiental",
        "descripcion": "Anemometro de alabe para medicion de velocidad de aire en sistemas HVAC y evaluacion ambiental.",
        "costo": 540000, "fecha_adq": HOY - relativedelta(years=1, months=11),
        "estado": "operativo", "apto": True,
        "metodo_analisis": "regresion",
        "mag": {
            "nombre": "Velocidad de aire", "simbolo": "v", "unidad": "m/s",
            "rango_min": 0.0, "rango_max": 20.0, "resolucion": "0.01 m/s",
            "emp_valor": 0.05, "emp_unidad": "m/s", "emp_texto": "+/-0.05 m/s",
            "incert_ref": 0.01,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(days=342)],
        "prox_override": HOY + relativedelta(days=18),   # alerta ⚠
        "temps": [22.0, 22.5, 23.0], "hums": [48.0, 50.0, 51.0],
        "verif_proc": "Verificar en tunel de viento de referencia a 2, 5 y 10 m/s. Registrar error absoluto.",
        "verif_patron": "Tunel de viento calibrado, anemometro laser de referencia",
        "mant_trabajo": "Limpieza del alabe con aire comprimido seco, inspeccion de rodamientos, verificacion de linealidad.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: limpieza del alabe, lubricacion de rodamientos, verificacion del punto cero.",
    },
    # EQ-024 Torquímetro — VENCIDA, LAGRANGE
    {
        "codigo": "EQ-024", "nombre": "Torquimetro",
        "marca": "Gedore", "modelo": "TBN 10", "serie": "GE2023789",
        "inventario": "INV-024", "area": "Produccion",
        "ubicacion": "Linea de ensamble, estacion de apriete T-02",
        "descripcion": "Llave dinamometrica de 2 a 10 N·m para control de torque en ensamble. Fuera de servicio por calibracion vencida.",
        "costo": 1100000, "fecha_adq": HOY - relativedelta(years=2, months=7),
        "estado": "fuera_de_uso", "apto": False,
        "metodo_analisis": "lagrange",
        "mag": {
            "nombre": "Par de torsion", "simbolo": "T", "unidad": "N.m",
            "rango_min": 2.0, "rango_max": 10.0, "resolucion": "0.01 N.m",
            "emp_valor": 0.04,   # 0.5% de 10 N.m ≈ 0.05, usamos 0.04
            "emp_unidad": "N.m", "emp_texto": "+/-0.5% del fondo de escala",
            "incert_ref": 0.008,
        },
        "cal_fechas": [HOY-relativedelta(months=30), HOY-relativedelta(months=18), HOY-relativedelta(months=7)],
        "prox_override": HOY - relativedelta(days=45),   # vencida ✗
        "temps": [22.0, 22.5, 23.0], "hums": [52.0, 53.0, 55.0],
        "verif_proc": "Verificar con torquimetro de referencia a 4, 6 y 8 N·m. Registrar error relativo.",
        "verif_patron": "Torquimetro de referencia certificado, trazable al SI",
        "mant_trabajo": "Inspeccion del mecanismo de trinquete, verificacion del ajuste del resorte, limpieza del cuerpo.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: inspeccion de mecanismo, verificacion de rango, limpieza y lubricacion.",
    },
    # EQ-025 Conductímetro — en_espera_calibracion
    {
        "codigo": "EQ-025", "nombre": "Conductimetro portatil",
        "marca": "Hanna", "modelo": "HI9813-6", "serie": "HI20230345",
        "inventario": "INV-025", "area": "Laboratorio",
        "ubicacion": "Laboratorio quimico, area de analisis de aguas",
        "descripcion": "Conductimetro portatil para medicion de conductividad electrica en muestras de agua y soluciones.",
        "costo": 480000, "fecha_adq": HOY - relativedelta(months=4),
        "estado": "en_espera_calibracion", "apto": False,
        "metodo_analisis": "regresion",
        "mag": {
            "nombre": "Conductividad", "simbolo": "k", "unidad": "uS/cm",
            "rango_min": 0.0, "rango_max": 4000.0, "resolucion": "1 uS/cm",
            "emp_valor": 10.0, "emp_unidad": "uS/cm", "emp_texto": "+/-10 uS/cm",
            "incert_ref": 2.0,
        },
        "cal_fechas": [],   # sin calibraciones — equipo nuevo
        "prox_override": None,
        "temps": [], "hums": [],
        "verif_proc": "Verificar con soluciones patron de conductividad de 1413 uS/cm y 2764 uS/cm.",
        "verif_patron": "Soluciones patron de conductividad certificadas, trazables al SI",
        "mant_trabajo": "Limpieza de la celda conductivimetrica, verificacion de la constante de celda, calibracion.",
        "plan_mant_desc": "Mantenimiento preventivo semestral: limpieza de celda, verificacion de constante K, calibracion con soluciones patron.",
    },
]


def crear_equipo_extra(db, ed: dict, admin_id: int) -> None:
    """Crea equipo extra con posibles 0 o 3 calibraciones."""
    if db.query(Equipo).filter(Equipo.codigo == ed["codigo"]).first():
        print(f"  [SKIP]  {ed['codigo']} ya existe")
        return

    print(f"  [+]  Creando {ed['codigo']} — {ed['nombre']}")

    eq = Equipo(
        codigo=ed["codigo"], nombre=ed["nombre"],
        descripcion=ed.get("descripcion"),
        marca=ed.get("marca"), modelo=ed.get("modelo"),
        numero_serie=ed.get("serie"), numero_inventario=ed.get("inventario"),
        fecha_adquisicion=ed.get("fecha_adq"),
        costo=ed.get("costo"),
        area=ed.get("area"), ubicacion=ed.get("ubicacion"),
        responsable=RESPONSABLE,
        estado=ed["estado"], apto_para_uso=ed["apto"],
        confirmacion_metrologica=ed["apto"],
    )
    db.add(eq); db.flush()
    resumen["equipos"] += 1

    db.add(HistorialEstado(
        equipo_id=eq.id, usuario_id=admin_id,
        estado_nuevo="en_espera_calibracion",
        motivo="Registro inicial del equipo",
    ))
    if ed["estado"] == "operativo":
        db.add(HistorialEstado(
            equipo_id=eq.id, usuario_id=admin_id,
            estado_anterior="en_espera_calibracion", estado_nuevo="operativo",
            motivo="Equipo habilitado tras calibración inicial",
        ))
    elif ed["estado"] == "fuera_de_uso":
        db.add(HistorialEstado(
            equipo_id=eq.id, usuario_id=admin_id,
            estado_anterior="operativo", estado_nuevo="fuera_de_uso",
            motivo="Calibracion vencida — equipo retirado hasta recalibración",
        ))

    m = ed["mag"]
    mag = MagnitudEquipo(
        equipo_id=eq.id,
        nombre=m["nombre"], simbolo=m.get("simbolo"), unidad=m.get("unidad"),
        rango_min=m.get("rango_min"), rango_max=m.get("rango_max"),
        resolucion=m.get("resolucion"),
        emp_valor=m.get("emp_valor"), emp_unidad=m.get("emp_unidad"),
        emp_texto=m.get("emp_texto"),
        tipo_instrumento="continuo",
        umbral_alerta_pct=80.0, umbral_fuera_pct=100.0,
        activa=True, orden=1,
    )
    db.add(mag); db.flush()

    # Calibraciones (puede ser 0 si lista vacía)
    cal_fechas    = ed.get("cal_fechas", [])
    prox_override = ed.get("prox_override")

    for i, fecha_cal in enumerate(cal_fechas):
        if i < len(cal_fechas) - 1:
            prox_cal = fecha_cal + relativedelta(months=12)
        else:
            prox_cal = prox_override if prox_override else fecha_cal + relativedelta(months=12)

        cert = _next_cert(fecha_cal)
        cal = Calibracion(
            magnitud_id=mag.id, equipo_id=eq.id,
            numero_certificado=cert,
            laboratorio=LABORATORIO, acreditacion_laboratorio=ACREDITACION,
            fecha_calibracion=fecha_cal, proxima_calibracion=prox_cal,
            patrones_utilizados=f"Patrones de referencia trazables al SI — {cert}",
            metodo_calibracion="Metodo de comparacion directa con patron de referencia",
            temperatura_ambiente=ed["temps"][i] if ed.get("temps") else 22.0,
            humedad_relativa=ed["hums"][i] if ed.get("hums") else 55.0,
            trazabilidad=TRAZABILIDAD,
            observaciones=f"Calibracion N°{i+1}. Todos los puntos dentro de la EMP.",
            certificado_path=f"/static/certificados/{cert}.pdf",
            costo=round(random.uniform(250000, 650000), -3),
            resultado="aprobado",
            grado_regresion_sel=1,
            metodo_analisis=ed.get("metodo_analisis", "regresion"),
            usar_incertidumbre=True,
            metodo_periodo="evaluacion_riesgo",
            justificacion_periodo="Intervalo determinado segun evaluacion de riesgo ILAC G24.",
            aprobado_por_id=admin_id,
            fecha_aprobacion=datetime.combine(fecha_cal, datetime.min.time()),
        )
        db.add(cal); db.flush()
        resumen["calibraciones"] += 1

        for pt in generar_puntos_calibracion(m):
            db.add(PuntoCalibracion(calibracion_id=cal.id, **pt))
            resumen["puntos_cal"] += 1

    if not cal_fechas:
        # Equipo en espera — crear solo la magnitud, sin calibraciones
        # Crear igual evaluacion y plan para que aparezca en el inventario
        pass
    else:
        # Evaluacion de riesgo
        factores = dict(f_incertidumbre=3, f_tipo=2, f_riesgo_emp=3, f_fabricante=2,
                        f_deriva=2, f_uso=3, f_ambiental=2, f_magnitud=3,
                        f_similares=3, f_comparaciones=2, f_verificaciones=2,
                        f_transporte=1, f_personal=2, f_legal=3)
        db.add(EvaluacionRiesgo(
            magnitud_id=mag.id, **factores,
            intervalo_fabricante_meses=12,
            puntuacion_total=float(sum(factores.values())),
            intervalo_sugerido_meses=12, intervalo_adoptado_meses=12,
            justificacion="Intervalo 12 meses segun evaluacion ILAC G24.",
            evaluado_por=RESPONSABLE, fecha_evaluacion=HOY - relativedelta(months=6),
        ))
        resumen["evaluaciones"] += 1

        db.add(ConfigILAC(
            magnitud_id=mag.id, metodo="m1",
            intervalo_inicial_meses=12, intervalo_actual_meses=12,
            intervalo_minimo_meses=6, intervalo_maximo_meses=24,
            porcentaje_escalera=80.0, horas_uso_acumuladas=0.0,
        ))

        # Plan de verificaciones
        plan_v = PlanVerificacion(
            magnitud_id=mag.id, equipo_id=eq.id, frecuencia_meses=3,
            procedimiento=ed.get("verif_proc", "Verificacion por comparacion con patron interno."),
            patron_referencia=ed.get("verif_patron", "Patron interno calibrado"),
            umbral_alerta_pct=70.0, umbral_fuera_pct=100.0, activo=True,
            aprobado_por_nombre=RESPONSABLE, aprobado_por_cargo=CARGO,
            fecha_aprobacion=HOY - relativedelta(months=6),
        )
        db.add(plan_v); db.flush()

        for j, off in enumerate([3, 1]):
            fecha_v = HOY - relativedelta(months=off)
            pts_v, max_desv = generar_puntos_verificacion(m)
            verif = VerificacionIntermedia(
                plan_id=plan_v.id, equipo_id=eq.id, magnitud_id=mag.id,
                fecha=fecha_v, proxima_verificacion=fecha_v + relativedelta(months=3),
                tipo="programada", realizada_por=RESPONSABLE,
                patron_usado=ed.get("verif_patron", "Patron interno calibrado"),
                resultado="aprobado", accion_tomada="ninguna",
                observaciones=f"Verificacion N°{j+1}. Max desviacion: {max_desv:.1f}% del EMP.",
                max_desviacion_pct=max_desv,
            )
            db.add(verif); db.flush()
            resumen["verificaciones"] += 1
            for pt_v in pts_v:
                db.add(PuntoVerificacion(verificacion_id=verif.id, **pt_v))

    # Plan mantenimiento (siempre)
    db.add(PlanMantenimiento(
        equipo_id=eq.id, frecuencia_meses=6, tipo="preventivo",
        descripcion=ed.get("plan_mant_desc", "Mantenimiento preventivo semestral."),
        responsable=RESPONSABLE, activo=True,
    ))
    resumen["planes_mant"] += 1

    # Mantenimientos (solo si tiene calibraciones)
    if cal_fechas:
        codigo_num = ed["codigo"].split("-")[-1]
        for k, off in enumerate([12, 6]):
            fecha_m = HOY - relativedelta(months=off)
            anio_ot = fecha_m.year
            db.add(Mantenimiento(
                equipo_id=eq.id, tipo="preventivo", origen="plan",
                titulo=f"Mantenimiento preventivo semestral — {ed['nombre']}",
                descripcion=ed.get("plan_mant_desc"),
                responsable_interno=RESPONSABLE,
                orden_trabajo=f"OT-{anio_ot}-{codigo_num}-{k+1:02d}",
                fecha_programada=fecha_m, fecha_inicio=fecha_m,
                fecha_fin=fecha_m + relativedelta(days=1),
                estado="completado",
                trabajo_realizado=ed.get("mant_trabajo", "Mantenimiento ejecutado."),
                costo=round(random.uniform(80000, 250000), -3),
                requiere_calibracion=False, afecta_medicion=False,
                observaciones_metrologicas="Equipo en condiciones normales tras el mantenimiento.",
            ))
            resumen["mantenimientos"] += 1

    db.flush()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def _migrar(db):
    """Agrega metodo_analisis si no existe en la tabla calibraciones."""
    from sqlalchemy import text
    try:
        db.execute(text("ALTER TABLE calibraciones ADD COLUMN metodo_analisis TEXT DEFAULT 'regresion'"))
        db.commit()
    except Exception:
        db.rollback()


def main():
    db = SessionLocal()
    try:
        _migrar(db)

        admin = db.query(Usuario).filter(Usuario.rol == "administrador").first()
        if not admin:
            print("[ERROR]  No se encontró usuario administrador. Inicia la app primero para crearlo.")
            return

        total_a_crear = len(EQUIPOS) + len(PESAS_E2) + len(EQUIPOS_EXTRA)
        print(f"\n>>>  MetroGest v2 — Seed de datos de demostración")
        print(f"    Fecha base   : {HOY}")
        print(f"    Administrador: {admin.nombre} (ID {admin.id})")
        print(f"    Equipos a crear (max): {total_a_crear}\n")

        print("[*] Equipos generales (EQ-002 a EQ-010)...")
        for ed in EQUIPOS:
            crear_equipo(db, ed, admin.id)

        print("\n[*] Juego de pesas patron E2 (EQ-011 a EQ-019)...")
        for pd_ in PESAS_E2:
            crear_pesa(db, pd_, admin.id)

        print("\n[*] Equipos adicionales (EQ-020 a EQ-025)...")
        for ed in EQUIPOS_EXTRA:
            crear_equipo_extra(db, ed, admin.id)

        db.commit()

        # Contar total en BD
        total_bd = db.query(Equipo).count()

        print(f"\n{'='*56}")
        print(f"[OK]  Seed completado. Resumen de datos creados:")
        print(f"    - {resumen['equipos']} equipo(s) nuevo(s)  (total en BD: {total_bd})")
        print(f"    - {resumen['calibraciones']} calibraciones ({resumen['puntos_cal']} puntos)")
        print(f"    - {resumen['verificaciones']} verificaciones intermedias")
        print(f"    - {resumen['planes_mant']} planes de mantenimiento")
        print(f"    - {resumen['mantenimientos']} registros de mantenimiento")
        print(f"    - {resumen['evaluaciones']} evaluaciones de riesgo ILAC")
        print(f"{'='*56}")
        print(f"\n  Estado del inventario ({total_bd} equipos):")
        print(f"  • Cal. proxima <= 30 dias : EQ-004, EQ-005, EQ-018, EQ-022, EQ-023")
        print(f"  • Calibracion vencida     : EQ-006, EQ-024")
        print(f"  • En espera calibracion   : EQ-003, EQ-019, EQ-025")
        print(f"  • Lagrange activado en     : pesas E2 (11-018) + EQ-021, EQ-022, EQ-024")
        print(f"{'='*56}\n")

    except Exception as exc:
        db.rollback()
        import traceback
        print(f"\n[ERROR]  Error durante la ejecución:")
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

