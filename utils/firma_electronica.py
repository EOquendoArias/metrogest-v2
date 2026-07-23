"""
Firma electrónica simple: reautenticación con contraseña + declaración de
significado, dentro de la misma transacción que la operación firmada.

No es firma digital certificada. Es una firma electrónica simple en el
sentido de la Ley 527 de 1999 (Colombia) — válida como prueba de que la
persona autenticada tomó esa decisión en ese momento, pero sin el respaldo
de un certificado de una entidad acreditada.
"""
import models, auth

# Declaración fija por tipo de acción — se muestra al firmante ANTES de pedir
# la contraseña, y queda guardada tal cual en el registro. Fija (no texto
# libre) para que el significado sea siempre el mismo para el mismo tipo de
# acto, algo que se le exige a una firma para tener valor probatorio.
_SIG_CALIBRACION = ("Apruebo que esta calibración fue realizada conforme al procedimiento "
                     "y que el equipo es apto para su uso.")
_SIG_VERIFICACION = ("Confirmo el resultado de esta verificación intermedia y la acción "
                      "tomada sobre el equipo.")
_SIG_ILAC = ("Apruebo el intervalo de calibración definido para esta magnitud, con "
             "base en el método de evaluación aplicado.")
_SIG_ESTADO_EQUIPO = ("Confirmo este cambio de estado del equipo y asumo la responsabilidad "
                       "de esta decisión.")

SIGNIFICADOS = {
    "aprobar_calibracion":            _SIG_CALIBRACION,
    "cerrar_verificacion":            _SIG_VERIFICACION,
    "definir_intervalo_ilac_riesgo":   _SIG_ILAC,
    "definir_intervalo_ilac_estandar": _SIG_ILAC,
    "definir_intervalo_ilac_deriva":   _SIG_ILAC,
    "definir_intervalo_ilac_escalera": _SIG_ILAC,
    "definir_intervalo_ilac_caja_negra": _SIG_ILAC,
    "definir_intervalo_ilac_horas":    _SIG_ILAC,
    "cambiar_estado_equipo":          _SIG_ESTADO_EQUIPO,
}


def verificar_y_firmar(db, request, u, password: str, tabla: str, registro_id: int, accion: str):
    """
    Reautentica al usuario con su contraseña y, si es correcta, agrega el
    registro de firma a la sesión (no hace commit — eso lo hace el caller,
    junto con la operación de negocio que se está firmando).

    Devuelve (ok: bool, error: str | None).
    """
    if not password or not auth.verificar_password(password, u.hashed_password):
        return False, "Contraseña incorrecta. La firma no se registró y el cambio no se guardó."

    significado = SIGNIFICADOS[accion]
    db.add(models.FirmaElectronica(
        tabla=tabla, registro_id=registro_id, accion=accion,
        significado=significado,
        usuario_id=u.id, usuario_nombre_firmado=u.nombre,
        ip=request.client.host if request.client else None,
    ))
    return True, None
