"""
Análisis de deriva (M1, ILAC-G24) — utils/deriva.py. A diferencia de
test_calculos.py, esta función necesita objetos reales con relaciones de
SQLAlchemy (magnitud.calibraciones, calibracion.puntos, calibracion.magnitud),
así que se prueba contra la base de datos de prueba, no con mocks.
"""
from datetime import date, timedelta

import models
from utils.deriva import analizar_deriva


def _crear_equipo_y_magnitud(db, emp_valor=1.0):
    equipo = models.Equipo(codigo="EQ-TEST-DERIVA", nombre="Equipo de prueba",
                            estado="operativo")
    db.add(equipo)
    db.flush()
    magnitud = models.MagnitudEquipo(equipo_id=equipo.id, nombre="Temperatura",
                                      emp_valor=emp_valor, activa=True)
    db.add(magnitud)
    db.flush()
    return equipo, magnitud


def _agregar_calibracion(db, magnitud, equipo, fecha, error, incertidumbre=0.0):
    cal = models.Calibracion(magnitud_id=magnitud.id, equipo_id=equipo.id,
                              fecha_calibracion=fecha, resultado="aprobado",
                              usar_incertidumbre=True)
    db.add(cal)
    db.flush()
    db.add(models.PuntoCalibracion(calibracion_id=cal.id, numero_punto=1,
                                    valor_patron=100.0, valor_indicado=100.0 + error,
                                    error=error, incertidumbre=incertidumbre,
                                    emp_punto=magnitud.emp_valor))
    db.flush()
    return cal


def test_menos_de_tres_calibraciones_es_insuficiente(db):
    equipo, magnitud = _crear_equipo_y_magnitud(db)
    _agregar_calibracion(db, magnitud, equipo, date(2025, 1, 1), error=0.1)
    _agregar_calibracion(db, magnitud, equipo, date(2025, 4, 1), error=0.15)
    db.commit()
    db.refresh(magnitud)

    analisis = analizar_deriva(magnitud)
    assert analisis["estado"] == "insuficiente"
    assert analisis["n_calibraciones"] == 2


def test_equipo_estable_sin_deriva_permite_ampliar_intervalo(db):
    equipo, magnitud = _crear_equipo_y_magnitud(db, emp_valor=1.0)
    # Mismo error pequeño y constante en el tiempo: sin tendencia de deriva.
    for i in range(4):
        _agregar_calibracion(db, magnitud, equipo,
                              date(2025, 1, 1) + timedelta(days=90 * i), error=0.05)
    db.commit()
    db.refresh(magnitud)

    analisis = analizar_deriva(magnitud)
    assert analisis["estado"] == "estable"
    assert analisis["intervalo_sugerido"] >= 12


def test_equipo_que_ya_salio_de_tolerancia_exige_intervalo_minimo(db):
    equipo, magnitud = _crear_equipo_y_magnitud(db, emp_valor=1.0)
    _agregar_calibracion(db, magnitud, equipo, date(2025, 1, 1), error=0.2)
    _agregar_calibracion(db, magnitud, equipo, date(2025, 4, 1), error=0.5)
    # La última calibración ya excede el EMP (error 1.1 > emp 1.0).
    _agregar_calibracion(db, magnitud, equipo, date(2025, 7, 1), error=1.1)
    db.commit()
    db.refresh(magnitud)

    analisis = analizar_deriva(magnitud)
    assert analisis["estado"] == "fuera"
    assert analisis["intervalo_sugerido"] == 1


def test_deriva_creciente_recomienda_intervalo_intermedio(db):
    equipo, magnitud = _crear_equipo_y_magnitud(db, emp_valor=1.0)
    # El error crece de forma constante hacia el EMP, sin llegar a cruzarlo aún.
    _agregar_calibracion(db, magnitud, equipo, date(2025, 1, 1), error=0.1)
    _agregar_calibracion(db, magnitud, equipo, date(2025, 4, 1), error=0.2)
    _agregar_calibracion(db, magnitud, equipo, date(2025, 7, 1), error=0.3)
    db.commit()
    db.refresh(magnitud)

    analisis = analizar_deriva(magnitud)
    assert analisis["estado"] in ("deriva", "deriva_alta")
    assert 1 <= analisis["intervalo_sugerido"] <= 60
