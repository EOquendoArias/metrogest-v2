"""
Rastro de auditoría automático (utils/auditoria_trail.py). Se engancha a
nivel de SQLAlchemy (before_flush/after_flush de Session), así que debería
capturar cambios sobre CUALQUIER Session — incluida la de estos tests —
sin que el test tenga que llamar nada explícito para "activar" el logging.
"""
import models
import utils.auditoria_trail as auditoria_trail


def _crear_usuario(db, email="auditoria_test@test.com"):
    u = models.Usuario(nombre="Usuario Auditado", email=email,
                        hashed_password="hash-no-real", rol="operador")
    db.add(u)
    db.commit()
    return u


def test_crear_registra_una_entrada_con_password_enmascarada(db):
    u = _crear_usuario(db)

    entradas = db.query(models.RegistroAuditoria).filter_by(
        tabla="usuarios", registro_id=u.id, accion="crear").all()

    assert len(entradas) == 1
    assert '"hashed_password": "***"' in entradas[0].valor_nuevo
    assert "hash-no-real" not in entradas[0].valor_nuevo


def test_modificar_un_campo_registra_valor_anterior_y_nuevo(db):
    u = _crear_usuario(db)
    u.rol = "administrador"
    db.commit()

    entradas = db.query(models.RegistroAuditoria).filter_by(
        tabla="usuarios", registro_id=u.id, accion="modificar", campo="rol").all()

    assert len(entradas) == 1
    assert entradas[0].valor_anterior == "operador"
    assert entradas[0].valor_nuevo == "administrador"


def test_eliminar_conserva_una_copia_del_registro_completo(db):
    equipo = models.Equipo(codigo="EQ-AUD-1", nombre="Equipo auditado", estado="operativo")
    db.add(equipo); db.commit()

    magnitud = models.MagnitudEquipo(equipo_id=equipo.id, nombre="Masa", activa=True)
    db.add(magnitud); db.commit()
    cal = models.Calibracion(magnitud_id=magnitud.id, equipo_id=equipo.id,
                              fecha_calibracion="2025-01-01", resultado="pendiente")
    db.add(cal); db.commit()
    punto = models.PuntoCalibracion(calibracion_id=cal.id, numero_punto=1,
                                     valor_patron=10.0, valor_indicado=10.1)
    db.add(punto); db.commit()
    punto_id = punto.id

    db.delete(punto)
    db.commit()

    entradas = db.query(models.RegistroAuditoria).filter_by(
        tabla="puntos_calibracion", registro_id=punto_id, accion="eliminar").all()
    assert len(entradas) == 1
    assert '"valor_patron": 10.0' in entradas[0].valor_anterior


def test_el_registro_queda_atribuido_al_usuario_del_contexto(db):
    # RegistroAuditoria.usuario_id tiene FK a usuarios.id: hace falta un
    # usuario real ya creado para "firmar" el siguiente cambio en su nombre.
    firmante = _crear_usuario(db, email="firmante_ctx@test.com")

    token = auditoria_trail.usuario_actual_id.set(firmante.id)
    try:
        u = _crear_usuario(db, email="con_usuario@test.com")
    finally:
        auditoria_trail.usuario_actual_id.reset(token)

    entrada = db.query(models.RegistroAuditoria).filter_by(
        tabla="usuarios", registro_id=u.id, accion="crear").first()
    assert entrada.usuario_id == firmante.id


def test_sin_usuario_en_contexto_queda_sin_atribuir(db):
    # Ningún test anterior debería filtrar su contextvar hasta acá.
    u = _crear_usuario(db, email="sin_usuario@test.com")
    entrada = db.query(models.RegistroAuditoria).filter_by(
        tabla="usuarios", registro_id=u.id, accion="crear").first()
    assert entrada.usuario_id is None
