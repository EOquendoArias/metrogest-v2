#!/usr/bin/env python3
"""
seed_carga_masiva.py — Fixture sintética de carga para MetroGest v2 (Fase 2.3)
================================================================================
Genera un volumen de datos a escala (~1,600 equipos por defecto, parametrizable)
para la prueba de carga/concurrencia de `docs/calidad/PLAN_PRUEBAS_CARGA.md`.

Diferencia deliberada con `seed_demo_data.py`:
  - `seed_demo_data.py` puebla una instalación de DEMO persistente con 25
    equipos curados a mano, usando el motor normal de la app (`DATABASE_URL`
    del `.env`), y crea el esquema con `Base.metadata.create_all(...)`.
  - Este script puebla una base de datos de PRUEBA/STAGING desechable con un
    volumen paramétrico de equipos sintéticos. NUNCA usa `DATABASE_URL` de la
    app — exige una URL explícita — y NO crea esquema (debe llegar por
    `alembic upgrade head`, según la regla de `CLAUDE.md` §7.2).

Regla de oro (ver PLAN_PRUEBAS_CARGA.md §5): esto NUNCA se corre contra la
base de datos real de un cliente. El script se niega a avanzar si la URL no
parece ser de prueba/staging, salvo confirmación explícita en dos pasos.

Prerrequisitos:
  1. La BD de destino ya tiene el esquema aplicado vía `alembic upgrade head`.
  2. La BD de destino ya tiene un usuario con rol "administrador" (arrancar
     la app una vez contra esa BD, o usar `resetear_password_admin.py`).

Uso:
    python seed_carga_masiva.py --database-url postgresql+psycopg2://user:pass@host/metrogest_carga
    CARGA_DATABASE_URL=postgresql+psycopg2://...  python seed_carga_masiva.py --yes
    python seed_carga_masiva.py --n 1600 --anios-historial 4 --usuarios 20 --database-url ...

Ver `python seed_carga_masiva.py --help` para todas las opciones.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import random
import secrets
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from dateutil.relativedelta import relativedelta

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.orm import sessionmaker

# Módulos del proyecto — solo definiciones (models.py) o funciones puras
# (auth.hash_password), sin efectos de conexión a BD al importarlos.
import models
import auth

HOY = date.today()

# ─────────────────────────────────────────────────────────────────────────────
# SEGURIDAD — nunca correr esto contra una base real
# ─────────────────────────────────────────────────────────────────────────────
_MARCADORES_BD_PRUEBA = ("test", "carga", "staging", "stg", "dev")


def _nombre_bd(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def _verificar_bd_segura(url: str, confirmo_flag: bool) -> None:
    nombre = _nombre_bd(url).lower()
    parece_prueba = any(m in nombre for m in _MARCADORES_BD_PRUEBA)

    print(f"\n>>> Base de datos de destino: {_nombre_bd(url)!r}")
    if not parece_prueba:
        print(
            "[ERROR]  El nombre de la base de datos no contiene 'test', 'carga', "
            "'staging', 'stg' ni 'dev'.\n"
            "         Este script genera datos SINTÉTICOS DE PRUEBA y nunca debe "
            "correr contra una base real.\n"
            "         Si de verdad es una BD de prueba con otro nombre, vuelve a "
            "correr con --confirmo-que-no-es-produccion."
        )
        sys.exit(1)
    if not confirmo_flag:
        print(
            "[ERROR]  Falta --confirmo-que-no-es-produccion. Es un paso "
            "deliberado, no un error de configuración: este script inserta miles "
            "de filas y no debe correr por accidente."
        )
        sys.exit(1)


def _confirmacion_interactiva(url: str, n: int, forzar_si: bool) -> None:
    if forzar_si:
        return
    print(
        f"\nEsto va a insertar ~{n} equipos sintéticos (y su historial) en:\n"
        f"    {_nombre_bd(url)!r}\n"
        f"Escribe SI (mayúsculas) para continuar, cualquier otra cosa cancela."
    )
    respuesta = input("> ").strip()
    if respuesta != "SI":
        print("Cancelado por el usuario.")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# PALETA DE MAGNITUDES — plantillas reutilizables, generalizan el criterio de
# seed_demo_data.py (EMP absoluto o relativo a la lectura) sin depender de
# comparar por nombre.
# ─────────────────────────────────────────────────────────────────────────────
MAGNITUD_TEMPLATES = [
    dict(nombre="Masa", simbolo="m", unidad="g", rango_min=0.0, rango_max=220.0,
         resolucion="0.1 mg", emp_valor=0.0003, emp_unidad="g", emp_texto="±0.3 mg",
         incert_ref=0.00005, emp_modo="absoluto",
         puntos_cal=[10.0, 50.0, 100.0, 150.0, 200.0], puntos_verif=[50.0, 100.0, 150.0],
         marcas=[("Mettler Toledo", "ME204B"), ("Sartorius", "Entris224i"), ("Radwag", "AS220")],
         areas=["Laboratorio", "Calidad"],
         verif_proc="Verificar con pesas certificadas clase E2. Registrar desviación respecto al valor de referencia.",
         verif_patron="Set de pesas clase E2 certificado ONAC, trazable al SI"),
    dict(nombre="Longitud", simbolo="L", unidad="mm", rango_min=0.0, rango_max=150.0,
         resolucion="0.01 mm", emp_valor=0.02, emp_unidad="mm", emp_texto="±0.02 mm",
         incert_ref=0.003, emp_modo="absoluto",
         puntos_cal=[10.0, 40.0, 75.0, 110.0, 150.0], puntos_verif=[25.0, 50.0, 100.0],
         marcas=[("Mitutoyo", 'CD-6"CSX'), ("Insize", "1108-150"), ("Starrett", "798B-6/150")],
         areas=["Producción", "Metrología"],
         verif_proc="Verificar con bloques patrón calibrados. Calcular error y comparar con EMP.",
         verif_patron="Bloques patrón clase 1, certificado ONAC, trazables al SI"),
    dict(nombre="Tensión DC", simbolo="V", unidad="V", rango_min=0.0, rango_max=1000.0,
         resolucion="0.1 mV", emp_valor=0.005, emp_unidad="% de lectura", emp_texto="±0.5% de la lectura",
         incert_ref=0.001, emp_modo="relativo_lectura",
         puntos_cal=[100.0, 250.0, 500.0, 750.0, 1000.0], puntos_verif=[250.0, 500.0, 750.0],
         marcas=[("Fluke", "87-V"), ("Keysight", "U1273A"), ("Fluke", "179")],
         areas=["Mantenimiento", "Utilidades"],
         verif_proc="Verificar función tensión DC con fuente de referencia calibrada. Registrar error relativo.",
         verif_patron="Fuente de referencia de tensión DC calibrada, certificado ONAC"),
    dict(nombre="Presión", simbolo="P", unidad="bar", rango_min=0.0, rango_max=10.0,
         resolucion="0.01 bar", emp_valor=0.025, emp_unidad="bar", emp_texto="±0.25% del fondo de escala",
         incert_ref=0.005, emp_modo="absoluto",
         puntos_cal=[1.0, 3.0, 5.0, 7.5, 10.0], puntos_verif=[2.5, 5.0, 7.5],
         marcas=[("Wika", "232.50"), ("Ashcroft", "1009"), ("Wika", "233.50")],
         areas=["Utilidades", "Producción"],
         verif_proc="Verificar con calibrador de presión de referencia. Registrar error absoluto.",
         verif_patron="Calibrador de presión certificado ONAC"),
    dict(nombre="Humedad relativa", simbolo="HR", unidad="% HR", rango_min=10.0, rango_max=95.0,
         resolucion="0.1 % HR", emp_valor=2.0, emp_unidad="% HR", emp_texto="±2% HR",
         incert_ref=0.3, emp_modo="absoluto",
         puntos_cal=[20.0, 40.0, 60.0, 75.0, 90.0], puntos_verif=[33.0, 75.5, 84.3],
         marcas=[("Testo", "608-H2"), ("Vaisala", "HM70"), ("Testo", "175 H1")],
         areas=["Almacén", "Laboratorio"],
         verif_proc="Verificar con soluciones salinas saturadas de referencia.",
         verif_patron="Soluciones salinas saturadas certificadas, higrómetro patrón calibrado ONAC"),
    dict(nombre="Tiempo", simbolo="t", unidad="s", rango_min=0.0, rango_max=3600.0,
         resolucion="0.01 s", emp_valor=0.1, emp_unidad="s", emp_texto="±0.1 s",
         incert_ref=0.01, emp_modo="absoluto",
         puntos_cal=[60.0, 900.0, 1800.0, 2700.0, 3600.0], puntos_verif=[900.0, 1800.0, 3600.0],
         marcas=[("Hanhart", "1/100 Ratoamt"), ("Oregon Scientific", "GA128"), ("Fisher", "06-662-19")],
         areas=["Calidad", "Laboratorio"],
         verif_proc="Comparar con señal de tiempo GPS a intervalos definidos.",
         verif_patron="Receptor GPS con salida 1PPS, resolución 0.01 s"),
    dict(nombre="Ángulo", simbolo="α", unidad="°", rango_min=-60.0, rango_max=60.0,
         resolucion="0.01 °", emp_valor=0.02, emp_unidad="°", emp_texto="±0.02°",
         incert_ref=0.003, emp_modo="absoluto",
         puntos_cal=[-60.0, -30.0, 0.0, 30.0, 60.0], puntos_verif=[-30.0, 0.0, 30.0],
         marcas=[("Stabila", "196-2S"), ("Bosch", "GIM 60"), ("Stabila", "48200")],
         areas=["Metrología", "Producción"],
         verif_proc="Verificar con tabla de senos calibrada.",
         verif_patron="Tabla de senos de alta precisión con bloques patrón calibrados ONAC"),
    dict(nombre="Volumen", simbolo="V", unidad="mL", rango_min=1.0, rango_max=10.0,
         resolucion="0.01 mL", emp_valor=0.02, emp_unidad="mL", emp_texto="±0.02 mL",
         incert_ref=0.003, emp_modo="absoluto",
         puntos_cal=[1.0, 3.0, 5.0, 7.5, 10.0], puntos_verif=[3.0, 5.0, 8.0],
         marcas=[("Brand", "Transferpette"), ("Eppendorf", "Research Plus"), ("Gilson", "Pipetman")],
         areas=["Laboratorio"],
         verif_proc="Método gravimétrico con agua destilada a temperatura controlada.",
         verif_patron="Balanza analítica de referencia, agua destilada a temperatura controlada"),
    dict(nombre="pH", simbolo="pH", unidad="pH", rango_min=0.0, rango_max=14.0,
         resolucion="0.01 pH", emp_valor=0.05, emp_unidad="pH", emp_texto="±0.05 pH",
         incert_ref=0.01, emp_modo="absoluto",
         puntos_cal=[2.0, 4.01, 7.0, 10.01, 12.0], puntos_verif=[4.01, 7.0, 10.01],
         marcas=[("Hanna", "HI2210"), ("Mettler Toledo", "SevenCompact"), ("Hanna", "HI98107")],
         areas=["Laboratorio"],
         verif_proc="Verificar con buffers certificados de pH a 25°C.",
         verif_patron="Buffers de pH certificados NIST"),
    dict(nombre="Iluminancia", simbolo="E", unidad="lux", rango_min=0.0, rango_max=100000.0,
         resolucion="1 lux", emp_valor=3.0, emp_unidad="% de lectura", emp_texto="±3% de la lectura",
         incert_ref=0.005, emp_modo="relativo_lectura",
         puntos_cal=[100.0, 500.0, 1000.0, 2000.0, 5000.0], puntos_verif=[500.0, 1000.0, 2000.0],
         marcas=[("Testo", "545"), ("Extech", "LT300"), ("Testo", "540")],
         areas=["HSEQ"],
         verif_proc="Verificar con lámpara de referencia calibrada.",
         verif_patron="Fuente de iluminación de referencia calibrada, trazable al SI"),
    dict(nombre="Velocidad de aire", simbolo="v", unidad="m/s", rango_min=0.0, rango_max=20.0,
         resolucion="0.01 m/s", emp_valor=0.05, emp_unidad="m/s", emp_texto="±0.05 m/s",
         incert_ref=0.01, emp_modo="absoluto",
         puntos_cal=[1.0, 2.0, 5.0, 10.0, 15.0], puntos_verif=[2.0, 5.0, 10.0],
         marcas=[("Testo", "416"), ("Kestrel", "5500"), ("Testo", "405i")],
         areas=["HSEQ", "Utilidades"],
         verif_proc="Verificar en túnel de viento de referencia.",
         verif_patron="Túnel de viento calibrado, anemómetro láser de referencia"),
    dict(nombre="Par de torsión", simbolo="T", unidad="N.m", rango_min=2.0, rango_max=10.0,
         resolucion="0.01 N.m", emp_valor=0.04, emp_unidad="N.m", emp_texto="±0.5% del fondo de escala",
         incert_ref=0.008, emp_modo="absoluto",
         puntos_cal=[2.0, 4.0, 6.0, 8.0, 10.0], puntos_verif=[4.0, 6.0, 8.0],
         marcas=[("Gedore", "TBN 10"), ("Norbar", "TTi 10"), ("Stahlwille", "730/10")],
         areas=["Producción"],
         verif_proc="Verificar con torquímetro de referencia.",
         verif_patron="Torquímetro de referencia certificado, trazable al SI"),
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE GENERACIÓN DE PUNTOS (mismo criterio que seed_demo_data.py:
# error aleatorio acotado a una fracción del EMP, centrado en cero)
# ─────────────────────────────────────────────────────────────────────────────


def _emp_en_punto(t: dict, vp: float) -> float:
    if t["emp_modo"] == "relativo_lectura":
        return t["emp_valor"] * abs(vp)
    return t["emp_valor"]


def _incert_en_punto(t: dict, vp: float) -> float:
    if t["emp_modo"] == "relativo_lectura":
        return t["incert_ref"] * abs(vp)
    return t["incert_ref"]


def generar_puntos_calibracion(t: dict) -> list[dict]:
    puntos = []
    for i, vp in enumerate(t["puntos_cal"]):
        emp = _emp_en_punto(t, vp)
        u = _incert_en_punto(t, vp)
        error = round(random.uniform(-emp * 0.55, emp * 0.55), 8)
        vi = round(vp + error, 8)
        abs_eu = round(abs(error) + u, 8)
        puntos.append(dict(
            numero_punto=i + 1, valor_patron=round(vp, 6), valor_indicado=round(vi, 6),
            error=round(error, 6), tolerancia_inf=round(-emp, 6), tolerancia_sup=round(emp, 6),
            incertidumbre=round(u, 6), abs_error_mas_u=round(abs_eu, 6), emp_punto=round(emp, 6),
            dentro_tolerancia=bool(abs_eu <= emp),
        ))
    return puntos


def generar_puntos_verificacion(t: dict) -> tuple[list[dict], float]:
    puntos, max_desv = [], 0.0
    for i, vp in enumerate(t["puntos_verif"]):
        emp = _emp_en_punto(t, vp)
        error = random.uniform(-emp * 0.45, emp * 0.45)
        vi = round(vp + error, 6)
        desv = round((abs(error) / emp * 100), 2) if emp > 0 else 0.0
        max_desv = max(max_desv, desv)
        puntos.append(dict(
            numero_punto=i + 1, valor_patron=round(vp, 4), valor_indicado=round(vi, 6),
            error=round(error, 6), tolerancia_inf=round(-emp, 6), tolerancia_sup=round(emp, 6),
            desviacion_pct=desv, resultado="ok",
        ))
    return puntos, round(max_desv, 2)


# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUCIÓN DE ESTADOS / MAGNITUDES POR EQUIPO
# ─────────────────────────────────────────────────────────────────────────────
_ESTADOS_PESOS = [("operativo", 0.75), ("fuera_de_uso", 0.10),
                  ("en_espera_calibracion", 0.10), ("dado_de_baja", 0.05)]
_N_MAGNITUDES_PESOS = [(1, 0.60), (2, 0.30), (3, 0.10)]


def _elegir_ponderado(pares: list[tuple]) -> object:
    valores, pesos = zip(*pares)
    return random.choices(valores, weights=pesos, k=1)[0]


RESPONSABLE = "Fixture de carga — Fase 2.3"
LABORATORIO = "Laboratorio de Calibración (carga sintética)"
ACREDITACION = "ONAC 20-LAB-000 (sintético)"
TRAZABILIDAD = "Patrones sintéticos trazables al SI — dato de prueba, no real."


def crear_equipo_carga(db, i: int, admin_id: int, anios_historial: int,
                        pct_pendiente: float) -> dict:
    """Crea un equipo sintético completo. Devuelve contadores para el resumen."""
    contadores = dict(equipos=0, magnitudes=0, calibraciones=0, puntos_cal=0,
                       verificaciones=0, puntos_verif=0, mantenimientos=0, evaluaciones=0)

    estado = _elegir_ponderado(_ESTADOS_PESOS)
    apto = estado == "operativo"
    tiene_historial = estado in ("operativo", "fuera_de_uso", "dado_de_baja")

    n_mag = _elegir_ponderado(_N_MAGNITUDES_PESOS)
    plantillas = random.sample(MAGNITUD_TEMPLATES, k=min(n_mag, len(MAGNITUD_TEMPLATES)))
    plantilla_principal = plantillas[0]
    marca, modelo = random.choice(plantilla_principal["marcas"])
    area = random.choice(plantilla_principal["areas"])
    codigo = f"CARGA-{i:05d}"

    eq = models.Equipo(
        codigo=codigo, nombre=f"{plantilla_principal['nombre']} sintético #{i}",
        descripcion=f"Equipo generado para prueba de carga Fase 2.3 (plantilla: {plantilla_principal['nombre']}).",
        marca=marca, modelo=modelo, numero_serie=f"SN-{i:06d}",
        numero_inventario=f"INV-CARGA-{i:05d}",
        fecha_adquisicion=HOY - relativedelta(years=random.randint(1, 6), months=random.randint(0, 11)),
        costo=round(random.uniform(300000, 9000000), -3),
        area=area, ubicacion=f"{area} — estación {random.randint(1, 20)}",
        responsable=RESPONSABLE,
        estado=estado, apto_para_uso=apto, confirmacion_metrologica=apto,
    )
    db.add(eq); db.flush()
    contadores["equipos"] += 1

    db.add(models.HistorialEstado(
        equipo_id=eq.id, usuario_id=admin_id,
        estado_nuevo=estado, motivo="Alta sintética — fixture de carga Fase 2.3",
    ))

    for orden, t in enumerate(plantillas, start=1):
        mag = models.MagnitudEquipo(
            equipo_id=eq.id, nombre=t["nombre"], simbolo=t.get("simbolo"), unidad=t.get("unidad"),
            rango_min=t.get("rango_min"), rango_max=t.get("rango_max"), resolucion=t.get("resolucion"),
            emp_valor=t.get("emp_valor"), emp_unidad=t.get("emp_unidad"), emp_texto=t.get("emp_texto"),
            tipo_instrumento="continuo", umbral_alerta_pct=80.0, umbral_fuera_pct=100.0,
            activa=True, orden=orden, notas=f"Magnitud sintética de {eq.nombre}",
        )
        db.add(mag); db.flush()
        contadores["magnitudes"] += 1

        if not tiene_historial:
            continue

        n_cal = random.randint(3, max(3, anios_historial + 1))
        cal_ids_pendientes_candidatas = []
        for k in range(n_cal):
            fecha_cal = HOY - relativedelta(months=12 * (n_cal - k))
            es_ultima = (k == n_cal - 1)
            if estado == "fuera_de_uso" and es_ultima:
                prox_cal = HOY - relativedelta(days=random.randint(5, 90))
            else:
                prox_cal = fecha_cal + relativedelta(months=12)

            marcar_pendiente = es_ultima and estado == "operativo" and random.random() < pct_pendiente
            resultado = "pendiente" if marcar_pendiente else "aprobado"

            cal = models.Calibracion(
                magnitud_id=mag.id, equipo_id=eq.id,
                numero_certificado=f"CERT-CARGA-{i:05d}-{mag.id}-{k+1}",
                laboratorio=LABORATORIO, acreditacion_laboratorio=ACREDITACION,
                fecha_calibracion=fecha_cal, proxima_calibracion=prox_cal,
                patrones_utilizados="Patrones sintéticos trazables al SI",
                metodo_calibracion="Método de comparación directa con patrón de referencia",
                temperatura_ambiente=round(random.uniform(18.0, 24.0), 1),
                humedad_relativa=round(random.uniform(40.0, 65.0), 1),
                trazabilidad=TRAZABILIDAD,
                observaciones="Calibración sintética generada para prueba de carga Fase 2.3.",
                costo=round(random.uniform(150000, 650000), -3),
                resultado=resultado, grado_regresion_sel=1,
                metodo_analisis="lagrange" if (mag.id % 3 == 0) else "regresion",
                usar_incertidumbre=True, metodo_periodo="evaluacion_riesgo",
                justificacion_periodo="Intervalo determinado según evaluación de riesgo ILAC G24 (sintético).",
                aprobado_por_id=None if resultado == "pendiente" else admin_id,
                fecha_aprobacion=None if resultado == "pendiente" else datetime.combine(fecha_cal, datetime.min.time()),
            )
            db.add(cal); db.flush()
            contadores["calibraciones"] += 1
            if resultado == "pendiente":
                cal_ids_pendientes_candidatas.append(cal.id)

            for pt in generar_puntos_calibracion(t):
                db.add(models.PuntoCalibracion(calibracion_id=cal.id, **pt))
                contadores["puntos_cal"] += 1

        n_verif = random.randint(2, 6)
        plan_v = models.PlanVerificacion(
            magnitud_id=mag.id, equipo_id=eq.id, frecuencia_meses=3,
            procedimiento=t["verif_proc"], patron_referencia=t["verif_patron"],
            umbral_alerta_pct=70.0, umbral_fuera_pct=100.0, activo=True,
            aprobado_por_nombre=RESPONSABLE, aprobado_por_cargo="Responsable Metrológico (sintético)",
            fecha_aprobacion=HOY - relativedelta(months=6),
        )
        db.add(plan_v); db.flush()

        for v in range(n_verif):
            fecha_v = HOY - relativedelta(months=3 * (n_verif - v))
            pts_v, max_desv = generar_puntos_verificacion(t)
            verif = models.VerificacionIntermedia(
                plan_id=plan_v.id, equipo_id=eq.id, magnitud_id=mag.id,
                fecha=fecha_v, proxima_verificacion=fecha_v + relativedelta(months=3),
                tipo="programada", realizada_por=RESPONSABLE, patron_usado=t["verif_patron"],
                resultado="aprobado", accion_tomada="ninguna",
                observaciones=f"Verificación sintética N°{v+1}. Desviación máxima: {max_desv:.1f}% del EMP.",
                max_desviacion_pct=max_desv,
            )
            db.add(verif); db.flush()
            contadores["verificaciones"] += 1
            for pt_v in pts_v:
                db.add(models.PuntoVerificacion(verificacion_id=verif.id, **pt_v))
                contadores["puntos_verif"] += 1

        factores = {f: random.randint(1, 3) for f in (
            "f_incertidumbre", "f_tipo", "f_riesgo_emp", "f_fabricante", "f_deriva", "f_uso",
            "f_ambiental", "f_magnitud", "f_similares", "f_comparaciones", "f_verificaciones",
            "f_transporte", "f_personal", "f_legal")}
        db.add(models.EvaluacionRiesgo(
            magnitud_id=mag.id, **factores,
            intervalo_fabricante_meses=12, puntuacion_total=float(sum(factores.values())),
            intervalo_sugerido_meses=12, intervalo_adoptado_meses=12,
            justificacion="Intervalo sintético de 12 meses (fixture de carga Fase 2.3).",
            evaluado_por=RESPONSABLE, fecha_evaluacion=HOY - relativedelta(months=6),
        ))
        contadores["evaluaciones"] += 1

        db.add(models.ConfigILAC(
            magnitud_id=mag.id, metodo="m1",
            intervalo_inicial_meses=12, intervalo_actual_meses=12,
            intervalo_minimo_meses=6, intervalo_maximo_meses=24,
            porcentaje_escalera=80.0, horas_uso_acumuladas=0.0,
        ))

    db.add(models.PlanMantenimiento(
        equipo_id=eq.id, frecuencia_meses=6, tipo="preventivo",
        descripcion="Mantenimiento preventivo semestral (fixture de carga Fase 2.3).",
        responsable=RESPONSABLE, activo=True,
    ))

    if tiene_historial:
        for k, off in enumerate([12, 6]):
            fecha_m = HOY - relativedelta(months=off)
            db.add(models.Mantenimiento(
                equipo_id=eq.id, tipo="preventivo", origen="plan",
                titulo=f"Mantenimiento preventivo semestral — {eq.nombre}",
                descripcion="Mantenimiento sintético para prueba de carga Fase 2.3.",
                responsable_interno=RESPONSABLE,
                orden_trabajo=f"OT-CARGA-{i:05d}-{k+1:02d}",
                fecha_programada=fecha_m, fecha_inicio=fecha_m, fecha_fin=fecha_m,
                estado="completado",
                trabajo_realizado="Mantenimiento preventivo ejecutado según plan (sintético).",
                costo=round(random.uniform(80000, 250000), -3),
                requiere_calibracion=False, afecta_medicion=False,
                observaciones_metrologicas="Equipo en condiciones normales (dato sintético).",
            ))
            contadores["mantenimientos"] += 1

    return contadores


# ─────────────────────────────────────────────────────────────────────────────
# USUARIOS DE CARGA — pool con contraseña conocida, mezcla de roles
# ─────────────────────────────────────────────────────────────────────────────
_ROLES_PESOS = [("operador", 0.70), ("solo_lectura", 0.20), ("administrador", 0.10)]


def crear_usuarios_carga(db, n_usuarios: int) -> list[dict]:
    creados = []
    for idx in range(1, n_usuarios + 1):
        rol = _elegir_ponderado(_ROLES_PESOS)
        email = f"carga_{rol}_{idx:03d}@carga.local"
        password = secrets.token_urlsafe(9)
        existente = db.query(models.Usuario).filter(models.Usuario.email == email).first()
        if existente:
            print(f"  [SKIP]  {email} ya existe")
            continue
        db.add(models.Usuario(
            nombre=f"Usuario de carga {idx:03d} ({rol})", email=email, rol=rol,
            hashed_password=auth.hash_password(password), activo=True,
            debe_cambiar_password=False,
        ))
        creados.append({"email": email, "password": password, "rol": rol})
    return creados


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def _verificar_esquema(engine) -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM equipos LIMIT 1"))
    except (ProgrammingError, OperationalError) as exc:
        print(
            "[ERROR]  No se pudo consultar la tabla 'equipos' en la BD de destino.\n"
            "         Este script NO crea esquema — corre `alembic upgrade head` "
            "contra esa base de datos primero.\n"
            f"         Detalle: {exc}"
        )
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--database-url", default=os.getenv("CARGA_DATABASE_URL"),
                     help="URL de SQLAlchemy de la BD de prueba/staging (o variable CARGA_DATABASE_URL). "
                          "NUNCA la URL de la app real.")
    ap.add_argument("--n", type=int, default=1600, help="Número de equipos a generar (default: 1600).")
    ap.add_argument("--anios-historial", type=int, default=4,
                     help="Años de historial de calibraciones por magnitud, aprox. (default: 4).")
    ap.add_argument("--usuarios", type=int, default=20,
                     help="Número de usuarios de carga a crear con contraseña conocida (default: 20).")
    ap.add_argument("--pct-pendiente", type=float, default=0.03,
                     help="Fracción de la última calibración de equipos operativos que se deja "
                          "en resultado='pendiente', para alimentar la tarea de aprobación en Locust (default: 0.03).")
    ap.add_argument("--batch-size", type=int, default=100, help="Equipos por commit (default: 100).")
    ap.add_argument("--seed", type=int, default=42, help="Semilla de reproducibilidad (default: 42).")
    ap.add_argument("--credenciales-out", default="usuarios_carga.json",
                     help="Archivo donde se guardan las credenciales del pool de usuarios de carga "
                          "(default: usuarios_carga.json, en el directorio actual).")
    ap.add_argument("--confirmo-que-no-es-produccion", action="store_true",
                     help="Requerido si el nombre de la BD no contiene test/carga/staging/stg/dev.")
    ap.add_argument("--yes", action="store_true",
                     help="Omite la confirmación interactiva (escribir SI). Úsalo solo en scripts "
                          "de CI ya controlados, no a mano.")
    args = ap.parse_args()

    if not args.database_url:
        print("[ERROR]  Falta --database-url (o la variable de entorno CARGA_DATABASE_URL).")
        sys.exit(1)

    random.seed(args.seed)

    _verificar_bd_segura(args.database_url, args.confirmo_que_no_es_produccion)
    _confirmacion_interactiva(args.database_url, args.n, args.yes)

    engine = create_engine(args.database_url)
    _verificar_esquema(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        admin = db.query(models.Usuario).filter(models.Usuario.rol == "administrador").first()
        if not admin:
            print("[ERROR]  No hay usuario 'administrador' en esa BD. Arranca la app una vez contra "
                  "ella (o usa resetear_password_admin.py) antes de sembrar.")
            sys.exit(1)

        ya_existentes = db.query(models.Equipo).filter(models.Equipo.codigo.like("CARGA-%")).count()
        if ya_existentes:
            print(
                f"[ERROR]  Ya hay {ya_existentes} equipos con prefijo 'CARGA-' en esta base.\n"
                "         Esta fixture es desechable por diseño (ver PLAN_PRUEBAS_CARGA.md §4): "
                "recrea la BD de prueba en vez de rellenarla incrementalmente, o bórralos tú mismo "
                "de forma explícita si sabes lo que haces."
            )
            sys.exit(1)

        print(f"\n>>> Generando {args.n} equipos sintéticos (semilla={args.seed})...\n")
        total = dict(equipos=0, magnitudes=0, calibraciones=0, puntos_cal=0,
                     verificaciones=0, puntos_verif=0, mantenimientos=0, evaluaciones=0)

        for i in range(1, args.n + 1):
            c = crear_equipo_carga(db, i, admin.id, args.anios_historial, args.pct_pendiente)
            for k, v in c.items():
                total[k] += v
            if i % args.batch_size == 0:
                db.commit()
                print(f"  [{i}/{args.n}] equipos creados y comprometidos...")
        db.commit()
        print(f"  [{args.n}/{args.n}] completado.\n")

        print(">>> Creando pool de usuarios de carga...")
        creds = crear_usuarios_carga(db, args.usuarios)
        db.commit()

        out_path = Path(args.credenciales_out)
        out_path.write_text(json.dumps({
            "generado": datetime.now().isoformat(timespec="seconds"),
            "database_url_nombre": _nombre_bd(args.database_url),
            "usuarios": creds,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"\n{'='*60}")
        print("[OK]  Fixture de carga generada:")
        print(f"    - {total['equipos']} equipos")
        print(f"    - {total['magnitudes']} magnitudes")
        print(f"    - {total['calibraciones']} calibraciones ({total['puntos_cal']} puntos)")
        print(f"    - {total['verificaciones']} verificaciones ({total['puntos_verif']} puntos)")
        print(f"    - {total['mantenimientos']} mantenimientos")
        print(f"    - {total['evaluaciones']} evaluaciones de riesgo ILAC")
        print(f"    - {len(creds)} usuarios de carga nuevos (credenciales en {out_path.resolve()})")
        print(f"{'='*60}\n")
        print("Siguiente paso: correr `locust -f locustfile.py` apuntando a la instancia "
              "de MetroGest levantada contra esta misma base de datos.")

    except Exception:
        db.rollback()
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
