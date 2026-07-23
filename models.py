from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, Text, ForeignKey, and_
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"
    id               = Column(Integer, primary_key=True, index=True)
    nombre           = Column(String(150), nullable=False)
    email            = Column(String(150), unique=True, nullable=False)
    hashed_password  = Column(String(200), nullable=False)
    rol              = Column(String(30), default="operador")
    activo           = Column(Boolean, default=True)
    debe_cambiar_password = Column(Boolean, default=False, nullable=False)
    created_at       = Column(DateTime, server_default=func.now())


class IntentoLogin(Base):
    __tablename__ = "intentos_login"
    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(150), unique=True, index=True, nullable=False)
    intentos        = Column(Integer, default=0, nullable=False)
    ultimo_intento  = Column(DateTime, nullable=True)
    bloqueado_hasta = Column(DateTime, nullable=True)


class ConfigLaboratorio(Base):
    __tablename__ = "config_laboratorio"
    id                          = Column(Integer, primary_key=True)
    nombre                      = Column(String(200), default="Laboratorio de Metrología")
    razon_social                = Column(String(200), nullable=True)
    direccion                   = Column(String(300), nullable=True)
    ciudad                      = Column(String(100), nullable=True)
    telefono                    = Column(String(50),  nullable=True)
    email_lab                   = Column(String(150), nullable=True)
    logo_path                   = Column(String(300), nullable=True)
    codigo_formato_analisis     = Column(String(50), default="FOR-MET-001")
    codigo_formato_verificacion = Column(String(50), default="FOR-MET-002")
    codigo_formato_mantenimiento= Column(String(50), default="FOR-MET-003")
    codigo_formato_baja         = Column(String(50), default="FOR-MET-004")
    codigo_formato_auditoria    = Column(String(50), default="FOR-MET-005")
    codigo_formato_ilac         = Column(String(50), default="FOR-MET-006")
    version_analisis            = Column(String(10), default="1.0")
    version_verificacion        = Column(String(10), default="1.0")
    version_mantenimiento       = Column(String(10), default="1.0")
    version_baja                = Column(String(10), default="1.0")
    version_auditoria           = Column(String(10), default="1.0")
    version_ilac                = Column(String(10), default="1.0")
    elaborado_por               = Column(String(150), nullable=True)
    revisado_por                = Column(String(150), nullable=True)
    aprobado_por                = Column(String(150), nullable=True)


class Equipo(Base):
    __tablename__ = "equipos"
    id                   = Column(Integer, primary_key=True, index=True)
    codigo               = Column(String(50), unique=True, nullable=False)
    nombre               = Column(String(200), nullable=False)
    descripcion          = Column(Text,        nullable=True)
    marca                = Column(String(100), nullable=True)
    modelo               = Column(String(100), nullable=True)
    numero_serie         = Column(String(100), nullable=True)
    numero_inventario    = Column(String(100), nullable=True)
    fecha_adquisicion    = Column(Date,        nullable=True)
    costo                = Column(Float,       nullable=True)
    area                 = Column(String(100), nullable=True)
    ubicacion            = Column(String(200), nullable=True)
    responsable          = Column(String(150), nullable=True)
    foto_path            = Column(String(300), nullable=True)
    manual_path          = Column(String(300), nullable=True)
    estado               = Column(String(40),  default="en_espera_calibracion")
    apto_para_uso        = Column(Boolean, default=False)
    confirmacion_metrologica = Column(Boolean, default=False)
    created_at           = Column(DateTime, server_default=func.now())

    magnitudes        = relationship("MagnitudEquipo", back_populates="equipo",
                                      cascade="all, delete-orphan",
                                      order_by="MagnitudEquipo.orden")
    historial_estados = relationship("HistorialEstado", back_populates="equipo",
                                      cascade="all, delete-orphan",
                                      order_by="HistorialEstado.fecha.desc()")
    mantenimientos    = relationship("Mantenimiento", back_populates="equipo",
                                      cascade="all, delete-orphan")
    plan_mantenimiento= relationship("PlanMantenimiento", back_populates="equipo",
                                      uselist=False, cascade="all, delete-orphan")


class HistorialEstado(Base):
    __tablename__ = "historial_estados"
    id              = Column(Integer, primary_key=True, index=True)
    equipo_id       = Column(Integer, ForeignKey("equipos.id"), nullable=False)
    usuario_id      = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    estado_anterior = Column(String(50), nullable=True)
    estado_nuevo    = Column(String(50), nullable=False)
    motivo          = Column(Text, nullable=True)
    fecha           = Column(DateTime, server_default=func.now())

    equipo  = relationship("Equipo", back_populates="historial_estados")
    usuario = relationship("Usuario")


class MagnitudEquipo(Base):
    __tablename__ = "magnitudes_equipo"
    id                   = Column(Integer, primary_key=True, index=True)
    equipo_id            = Column(Integer, ForeignKey("equipos.id"), nullable=False)
    nombre               = Column(String(150), nullable=False)
    simbolo              = Column(String(20),  nullable=True)
    unidad               = Column(String(50),  nullable=True)
    rango_min            = Column(Float,       nullable=True)
    rango_max            = Column(Float,       nullable=True)
    resolucion           = Column(String(100), nullable=True)
    emp_texto            = Column(String(200), nullable=True)
    emp_valor            = Column(Float,       nullable=True)
    emp_unidad           = Column(String(50),  nullable=True)
    clase_exactitud      = Column(String(50),  nullable=True)
    tipo_instrumento     = Column(String(30),  default="continuo")
    umbral_alerta_pct    = Column(Float, default=70.0)
    umbral_fuera_pct     = Column(Float, default=100.0)
    activa               = Column(Boolean, default=True)
    motivo_desactivacion = Column(Text, nullable=True)
    orden                = Column(Integer, default=1)
    notas                = Column(Text, nullable=True)
    created_at           = Column(DateTime, server_default=func.now())

    equipo            = relationship("Equipo", back_populates="magnitudes")
    calibraciones     = relationship("Calibracion", back_populates="magnitud",
                                      cascade="all, delete-orphan",
                                      order_by="Calibracion.fecha_calibracion.desc()")
    plan_verificacion = relationship("PlanVerificacion", back_populates="magnitud",
                                      uselist=False, cascade="all, delete-orphan")
    evaluacion_riesgo = relationship("EvaluacionRiesgo", back_populates="magnitud",
                                      uselist=False, cascade="all, delete-orphan")
    config_ilac       = relationship("ConfigILAC", back_populates="magnitud",
                                      uselist=False, cascade="all, delete-orphan")


class Calibracion(Base):
    __tablename__ = "calibraciones"
    id                       = Column(Integer, primary_key=True, index=True)
    magnitud_id              = Column(Integer, ForeignKey("magnitudes_equipo.id"), nullable=False)
    equipo_id                = Column(Integer, ForeignKey("equipos.id"),           nullable=False)
    numero_certificado       = Column(String(100), nullable=True)
    laboratorio              = Column(String(200), nullable=True)
    acreditacion_laboratorio = Column(String(100), nullable=True)
    fecha_calibracion        = Column(Date, nullable=False)
    proxima_calibracion      = Column(Date, nullable=True)
    patrones_utilizados      = Column(Text, nullable=True)
    metodo_calibracion       = Column(String(200), nullable=True)
    temperatura_ambiente     = Column(Float, nullable=True)
    humedad_relativa         = Column(Float, nullable=True)
    trazabilidad             = Column(Text, nullable=True)
    observaciones            = Column(Text, nullable=True)
    certificado_path         = Column(String(300), nullable=True)
    costo                    = Column(Float, nullable=True)
    resultado                = Column(String(30), default="pendiente")
    grado_regresion_sel      = Column(Integer, nullable=True)
    metodo_analisis          = Column(String(20), default="regresion")   # "regresion" | "lagrange"
    usar_incertidumbre       = Column(Boolean, default=True)
    metodo_periodo           = Column(String(30),  nullable=True)
    justificacion_periodo    = Column(Text,        nullable=True)
    aprobado_por_id          = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_aprobacion         = Column(DateTime, nullable=True)
    created_at               = Column(DateTime, server_default=func.now())

    magnitud     = relationship("MagnitudEquipo", back_populates="calibraciones")
    aprobado_por = relationship("Usuario", foreign_keys=[aprobado_por_id])
    puntos       = relationship("PuntoCalibracion", back_populates="calibracion",
                                 cascade="all, delete-orphan",
                                 primaryjoin="and_(Calibracion.id==PuntoCalibracion.calibracion_id, "
                                             "PuntoCalibracion.eliminado==False)",
                                 order_by="PuntoCalibracion.numero_punto")


class PuntoCalibracion(Base):
    __tablename__ = "puntos_calibracion"
    id                = Column(Integer, primary_key=True, index=True)
    calibracion_id    = Column(Integer, ForeignKey("calibraciones.id"), nullable=False)
    numero_punto      = Column(Integer, nullable=False)
    valor_patron      = Column(Float,   nullable=False)
    valor_indicado    = Column(Float,   nullable=False)
    error             = Column(Float,   nullable=True)
    tolerancia_inf    = Column(Float,   nullable=True)
    tolerancia_sup    = Column(Float,   nullable=True)
    incertidumbre     = Column(Float,   nullable=True)
    abs_error_mas_u   = Column(Float,   nullable=True)
    emp_punto         = Column(Float,   nullable=True)
    dentro_tolerancia = Column(Boolean, nullable=True)
    observacion       = Column(String(200), nullable=True)
    eliminado         = Column(Boolean, default=False, nullable=False)
    eliminado_en      = Column(DateTime, nullable=True)
    eliminado_por_id  = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    calibracion    = relationship("Calibracion",
                                   back_populates="puntos",
                                   primaryjoin="Calibracion.id==PuntoCalibracion.calibracion_id")
    eliminado_por  = relationship("Usuario", foreign_keys=[eliminado_por_id])


class EvaluacionRiesgo(Base):
    __tablename__ = "evaluaciones_riesgo"
    id           = Column(Integer, primary_key=True, index=True)
    magnitud_id  = Column(Integer, ForeignKey("magnitudes_equipo.id"), unique=True, nullable=False)
    f_incertidumbre  = Column(Integer, default=3)
    f_tipo           = Column(Integer, default=3)
    f_riesgo_emp     = Column(Integer, default=3)
    f_fabricante     = Column(Integer, default=3)
    f_deriva         = Column(Integer, default=3)
    f_uso            = Column(Integer, default=3)
    f_ambiental      = Column(Integer, default=3)
    f_magnitud       = Column(Integer, default=3)
    f_similares      = Column(Integer, default=3)
    f_comparaciones  = Column(Integer, default=3)
    f_verificaciones = Column(Integer, default=3)
    f_transporte     = Column(Integer, default=3)
    f_personal       = Column(Integer, default=3)
    f_legal          = Column(Integer, default=3)
    intervalo_fabricante_meses = Column(Integer, nullable=True)
    puntuacion_total           = Column(Float,   nullable=True)
    intervalo_sugerido_meses   = Column(Integer, nullable=True)
    intervalo_adoptado_meses   = Column(Integer, nullable=True)
    justificacion              = Column(Text,    nullable=True)
    # Justificación requerida cuando adoptado > sugerido
    justificacion_exceso       = Column(Text,    nullable=True)
    evaluado_por               = Column(String(150), nullable=True)
    fecha_evaluacion           = Column(Date,    nullable=True)

    magnitud = relationship("MagnitudEquipo", back_populates="evaluacion_riesgo")


class ConfigILAC(Base):
    __tablename__ = "config_ilac"
    id                      = Column(Integer, primary_key=True, index=True)
    magnitud_id             = Column(Integer, ForeignKey("magnitudes_equipo.id"), unique=True)
    metodo                  = Column(String(20), default="m1")
    intervalo_inicial_meses = Column(Integer, default=12)
    intervalo_actual_meses  = Column(Integer, default=12)
    intervalo_minimo_meses  = Column(Integer, default=1)
    intervalo_maximo_meses  = Column(Integer, default=60)
    porcentaje_escalera     = Column(Float,   default=80.0)
    horas_uso_limite        = Column(Float,   nullable=True)
    horas_uso_acumuladas    = Column(Float,   default=0.0)

    magnitud = relationship("MagnitudEquipo", back_populates="config_ilac")


class PlanVerificacion(Base):
    __tablename__ = "planes_verificacion"
    id                      = Column(Integer, primary_key=True, index=True)
    magnitud_id             = Column(Integer, ForeignKey("magnitudes_equipo.id"), nullable=False)
    equipo_id               = Column(Integer, ForeignKey("equipos.id"),           nullable=False)
    frecuencia_meses        = Column(Integer, nullable=True)  # nullable cuando no aplica
    procedimiento           = Column(Text,    nullable=True)
    patron_referencia       = Column(String(200), nullable=True)
    umbral_alerta_pct       = Column(Float, default=70.0)
    umbral_fuera_pct        = Column(Float, default=100.0)
    activo                  = Column(Boolean, default=True)
    justificacion_no_aplica = Column(Text,  nullable=True)
    aprobado_por_nombre     = Column(String(150), nullable=True)
    aprobado_por_cargo      = Column(String(150), nullable=True)
    fecha_aprobacion        = Column(Date,        nullable=True)

    magnitud       = relationship("MagnitudEquipo", back_populates="plan_verificacion")
    verificaciones = relationship("VerificacionIntermedia", back_populates="plan",
                                   cascade="all, delete-orphan",
                                   order_by="VerificacionIntermedia.fecha.desc()")


class VerificacionIntermedia(Base):
    __tablename__ = "verificaciones_intermedias"
    id                   = Column(Integer, primary_key=True, index=True)
    plan_id              = Column(Integer, ForeignKey("planes_verificacion.id"), nullable=False)
    equipo_id            = Column(Integer, ForeignKey("equipos.id"),             nullable=False)
    magnitud_id          = Column(Integer, ForeignKey("magnitudes_equipo.id"),   nullable=False)
    fecha                = Column(Date, nullable=False)
    proxima_verificacion = Column(Date, nullable=True)
    tipo                 = Column(String(50), default="programada")
    realizada_por        = Column(String(150), nullable=True)
    patron_usado         = Column(String(200), nullable=True)
    resultado            = Column(String(30),  default="pendiente")
    accion_tomada        = Column(String(50),  nullable=True)
    observaciones        = Column(Text,        nullable=True)
    archivo_path         = Column(String(300), nullable=True)
    max_desviacion_pct   = Column(Float,       nullable=True)
    created_at           = Column(DateTime, server_default=func.now())

    plan     = relationship("PlanVerificacion",  back_populates="verificaciones")
    puntos   = relationship("PuntoVerificacion", back_populates="verificacion",
                             cascade="all, delete-orphan",
                             primaryjoin="and_(VerificacionIntermedia.id==PuntoVerificacion.verificacion_id, "
                                         "PuntoVerificacion.eliminado==False)",
                             order_by="PuntoVerificacion.numero_punto")
    equipo   = relationship("Equipo",          foreign_keys=[equipo_id])
    magnitud = relationship("MagnitudEquipo",  foreign_keys=[magnitud_id])


class PuntoVerificacion(Base):
    __tablename__ = "puntos_verificacion"
    id              = Column(Integer, primary_key=True, index=True)
    verificacion_id = Column(Integer, ForeignKey("verificaciones_intermedias.id"), nullable=False)
    numero_punto    = Column(Integer, nullable=False)
    valor_patron    = Column(Float,   nullable=False)
    valor_indicado  = Column(Float,   nullable=True)
    error           = Column(Float,   nullable=True)
    tolerancia_inf  = Column(Float,   nullable=True)
    tolerancia_sup  = Column(Float,   nullable=True)
    desviacion_pct  = Column(Float,   nullable=True)
    resultado       = Column(String(20), nullable=True)
    observacion     = Column(String(200), nullable=True)
    eliminado         = Column(Boolean, default=False, nullable=False)
    eliminado_en      = Column(DateTime, nullable=True)
    eliminado_por_id  = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    verificacion  = relationship("VerificacionIntermedia",
                                  back_populates="puntos",
                                  primaryjoin="VerificacionIntermedia.id==PuntoVerificacion.verificacion_id")
    eliminado_por = relationship("Usuario", foreign_keys=[eliminado_por_id])


class PlanMantenimiento(Base):
    """Plan de mantenimiento preventivo para un equipo."""
    __tablename__ = "planes_mantenimiento"
    id                      = Column(Integer, primary_key=True, index=True)
    equipo_id               = Column(Integer, ForeignKey("equipos.id"), nullable=False)
    frecuencia_meses        = Column(Integer, nullable=False, default=6)
    tipo                    = Column(String(30), default="preventivo")
    descripcion             = Column(Text, nullable=True)
    responsable             = Column(String(150), nullable=True)
    activo                  = Column(Boolean, default=True)
    created_at              = Column(DateTime, server_default=func.now())

    equipo = relationship("Equipo", back_populates="plan_mantenimiento", foreign_keys=[equipo_id])


class Mantenimiento(Base):
    __tablename__ = "mantenimientos"
    id                         = Column(Integer, primary_key=True, index=True)
    equipo_id                  = Column(Integer, ForeignKey("equipos.id"), nullable=False)
    tipo                       = Column(String(30),  nullable=False)
    origen                     = Column(String(20),  nullable=False)
    titulo                     = Column(String(200), nullable=False)
    descripcion                = Column(Text,  nullable=True)
    responsable_interno        = Column(String(150), nullable=True)
    empresa_externa            = Column(String(200), nullable=True)
    tecnico_externo            = Column(String(150), nullable=True)
    orden_trabajo              = Column(String(100), nullable=True)
    fecha_programada           = Column(Date, nullable=True)
    fecha_inicio               = Column(Date, nullable=True)
    fecha_fin                  = Column(Date, nullable=True)
    estado                     = Column(String(30), default="programado")
    falla_encontrada           = Column(Text,  nullable=True)
    trabajo_realizado          = Column(Text,  nullable=True)
    repuestos_utilizados       = Column(Text,  nullable=True)
    costo                      = Column(Float, nullable=True)
    requiere_calibracion       = Column(Boolean, default=False)
    afecta_medicion            = Column(Boolean, default=False)
    observaciones_metrologicas = Column(Text, nullable=True)
    archivo_path               = Column(String(300), nullable=True)
    created_at                 = Column(DateTime, server_default=func.now())

    equipo = relationship("Equipo", back_populates="mantenimientos")


class ConfigNotificaciones(Base):
    __tablename__ = "config_notificaciones"
    id                   = Column(Integer, primary_key=True)
    email_destinatario   = Column(String(200), nullable=True)
    # Calibraciones
    alerta_antes_30      = Column(Boolean, default=True)
    alerta_antes_15      = Column(Boolean, default=True)
    alerta_antes_7       = Column(Boolean, default=True)
    alerta_antes_1       = Column(Boolean, default=True)
    alerta_dia_0         = Column(Boolean, default=True)
    alerta_despues_1     = Column(Boolean, default=True)
    alerta_despues_7     = Column(Boolean, default=True)
    # Licencia
    alerta_licencia      = Column(Boolean, default=True)
    updated_at           = Column(DateTime, default=func.now())


class HistorialAlertas(Base):
    __tablename__ = "historial_alertas"
    id           = Column(Integer, primary_key=True, index=True)
    equipo_id    = Column(Integer, ForeignKey("equipos.id"), nullable=False)
    magnitud_id  = Column(Integer, ForeignKey("magnitudes_equipo.id"), nullable=False)
    tipo_alerta  = Column(String(20), nullable=False)   # "antes_30", "antes_15", "antes_7", "antes_1", "dia_0", "despues_1", "despues_7"
    fecha_envio  = Column(DateTime, default=func.now(), nullable=False)

    equipo   = relationship("Equipo")
    magnitud = relationship("MagnitudEquipo")


class RegistroAuditoria(Base):
    """
    Rastro de auditoría: quién cambió qué campo, de qué valor a cuál, y cuándo.
    Solo se escribe desde utils/auditoria_trail.py (listeners de SQLAlchemy) —
    no hay ninguna ruta que permita editar o borrar estos registros.
    """
    __tablename__ = "registro_auditoria"
    id             = Column(Integer, primary_key=True, index=True)
    tabla          = Column(String(50), nullable=False, index=True)
    registro_id    = Column(Integer, nullable=False, index=True)
    accion         = Column(String(20), nullable=False)   # "crear" | "modificar" | "eliminar"
    campo          = Column(String(100), nullable=True)   # solo aplica a "modificar"
    valor_anterior = Column(Text, nullable=True)
    valor_nuevo    = Column(Text, nullable=True)
    usuario_id     = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha          = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    usuario = relationship("Usuario")


class FirmaElectronica(Base):
    """
    Firma electrónica simple (Ley 527 de 1999 — Colombia): exige reautenticación
    con contraseña en el momento de firmar (no basta con estar logueado) y deja
    una declaración explícita del significado del acto firmado. No es firma
    digital certificada (eso requeriría un proveedor acreditado con
    infraestructura de llave pública, un proyecto aparte).

    Solo se escribe desde utils/firma_electronica.py, junto con la operación de
    negocio que firma, dentro de la misma transacción.
    """
    __tablename__ = "firmas_electronicas"
    id                     = Column(Integer, primary_key=True, index=True)
    tabla                  = Column(String(50), nullable=False, index=True)
    registro_id            = Column(Integer, nullable=False, index=True)
    accion                 = Column(String(50), nullable=False, index=True)
    significado            = Column(Text, nullable=False)
    usuario_id             = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    usuario_nombre_firmado = Column(String(150), nullable=False)  # snapshot: sobrevive si el usuario cambia de nombre
    ip                     = Column(String(50), nullable=True)
    fecha                  = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    usuario = relationship("Usuario")
