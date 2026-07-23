"""
Firma electrónica (utils/firma_electronica.py): reautenticación con
contraseña real antes de firmar, y solo si es correcta se registra la
firma — dentro de la misma transacción que la operación de negocio.
"""
from types import SimpleNamespace

import auth
import models
from utils.firma_electronica import SIGNIFICADOS, verificar_y_firmar


def _crear_usuario(db, password="ClaveReal123"):
    u = models.Usuario(nombre="Firmante", email="firmante@test.com",
                        hashed_password=auth.hash_password(password), rol="administrador")
    db.add(u)
    db.commit()
    return u


def _fake_request():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


def test_password_incorrecta_no_registra_firma_ni_confirma(db):
    u = _crear_usuario(db)

    ok, error = verificar_y_firmar(db, _fake_request(), u, "clave-mala",
                                    "calibraciones", 1, "aprobar_calibracion")

    assert ok is False
    assert error
    assert db.query(models.FirmaElectronica).filter_by(
        tabla="calibraciones", registro_id=1).count() == 0


def test_password_correcta_registra_la_firma_con_el_significado_correcto(db):
    u = _crear_usuario(db)

    ok, error = verificar_y_firmar(db, _fake_request(), u, "ClaveReal123",
                                    "calibraciones", 55, "aprobar_calibracion")
    db.commit()

    assert ok is True
    assert error is None
    firma = db.query(models.FirmaElectronica).filter_by(
        tabla="calibraciones", registro_id=55).one()
    assert firma.usuario_id == u.id
    assert firma.usuario_nombre_firmado == "Firmante"
    assert firma.significado == SIGNIFICADOS["aprobar_calibracion"]
    assert firma.ip == "127.0.0.1"


def test_cada_tipo_de_accion_tiene_su_propio_significado_declarado():
    acciones_esperadas = {
        "aprobar_calibracion", "cerrar_verificacion", "cambiar_estado_equipo",
        "definir_intervalo_ilac_riesgo", "definir_intervalo_ilac_estandar",
        "definir_intervalo_ilac_deriva", "definir_intervalo_ilac_escalera",
        "definir_intervalo_ilac_caja_negra", "definir_intervalo_ilac_horas",
    }
    assert acciones_esperadas.issubset(SIGNIFICADOS.keys())
    for accion, texto in SIGNIFICADOS.items():
        assert texto.strip(), f"'{accion}' no tiene declaración de significado"
