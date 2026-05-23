# MetroGest v2 — Guía Técnica del Proyecto

> Sistema de Gestión Metrológica conforme a **ISO/IEC 10012:2003** y **ILAC G24:2017**  
> Versión: 2.0 · Estado: Pre-MVP · Modelo: Suscripción (desktop → SaaS)

---

## 1. Resumen del Producto

MetroGest v2 es una aplicación web de escritorio para la gestión integral de la confirmación metrológica de equipos de medición en laboratorios industriales y de calibración. Permite controlar el ciclo de vida completo de cada instrumento: desde su inventario hasta la trazabilidad de calibraciones, verificaciones intermedias, mantenimientos y evaluación de riesgos según ILAC G24.

### Propuesta de valor
- Cumplimiento documentado con ISO/IEC 10012 e ILAC G24
- Control visual (semáforo) de conformidad de calibraciones
- Generación automática de PDFs para auditorías
- Alertas de vencimientos en dashboard y calendario
- Trazabilidad completa por equipo

### Modelo de negocio
- **Fase 1 (actual):** Instalación local en el ordenador del cliente + licencia por suscripción anual
- **Fase 2 (futura):** Migración a SaaS web multi-tenant con suscripción mensual/anual

---

## 2. Stack Tecnológico

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Backend | FastAPI | Latest |
| Servidor ASGI | Uvicorn | w/ standard extras |
| ORM | SQLAlchemy | 2.0+ |
| Base de datos | SQLite | 3.x |
| Plantillas | Jinja2 | 3.1+ |
| Middleware | Starlette (sessiones) | Latest |
| Autenticación | passlib[bcrypt] | Latest |
| PDF | ReportLab | 4.5+ |
| Cálculos | NumPy | Latest |
| Gráficas | Matplotlib | Latest |
| Manejo de fechas | python-dateutil | Latest |
| Archivos async | aiofiles | Latest |
| Formularios | python-multipart | Latest |
| Runtime | Python | 3.10+ |
| Inicio (Windows) | iniciar.bat | — |

### Justificación de elecciones
- **SQLite:** Perfecto para instalación desktop de un solo usuario/empresa. Sin servidor de BD. Migración a PostgreSQL posible cuando se pase a SaaS.
- **FastAPI:** Tipado, rápido, genera OpenAPI automáticamente. Fácil de escalar a API REST cuando se construya frontend SPA.
- **Jinja2 SSR:** Sin complejidad de frontend framework. Funciona offline sin necesidad de CDN.
- **ReportLab:** PDFs controlados con headers de formato y firmas, sin dependencias externas.

---

## 3. Arquitectura del Proyecto

```
metrogest_v2/
├── main.py                    # Punto de entrada FastAPI, registro de routers
├── database.py                # Engine SQLAlchemy, get_db dependency
├── models.py                  # 13 tablas ORM (declarative style)
├── auth.py                    # Autenticación, autorización, obtener_usuario_actual()
├── licencia.py                # Sistema de licencias HMAC-SHA256
├── migrar.py                  # Migraciones de schema
├── migrar_plan_mant.py        # Migración específica plan_mantenimiento
├── iniciar.bat                # Arranque Windows
├── requirements.txt           # Dependencias Python
├── metrogest.db               # Base de datos SQLite (auto-creada)
│
├── routers/                   # 14 módulos de rutas (≈1,825 líneas)
│   ├── usuarios.py
│   ├── equipos.py
│   ├── magnitudes.py
│   ├── calibraciones.py
│   ├── analisis.py
│   ├── verificaciones.py
│   ├── mantenimientos.py
│   ├── plan_mantenimiento.py
│   ├── ilac.py
│   ├── dashboard.py
│   ├── calendario.py
│   ├── config_lab.py
│   ├── auditoria.py
│   └── __init__.py
│
├── templates/                 # 24 plantillas Jinja2
│   ├── base.html              # Layout maestro + sidebar
│   ├── login.html
│   ├── equipos/               # lista, formulario, detalle
│   ├── magnitudes/            # lista, formulario
│   ├── calibraciones/         # formulario, historial
│   ├── analisis/              # analisis.html (página compleja)
│   ├── verificaciones/        # nueva, historial, plan, puntos
│   ├── mantenimientos/        # formulario, lista, plan
│   ├── ilac/                  # riesgo, nuevo_periodo
│   ├── dashboard/             # dashboard.html
│   ├── calendario/            # calendario.html
│   ├── config_lab/            # config.html
│   ├── usuarios/              # formulario, lista
│   └── auditoria/             # resumen.html
│
├── utils/                     # Lógica de negocio y generación de documentos
│   ├── calculos.py            # Regresión, semáforo, desviación %
│   ├── pdf_header.py          # Headers/footers controlados para PDFs
│   ├── pdf_analisis.py        # PDF de análisis de calibración
│   ├── pdf_docs.py            # PDF de verificación y mantenimiento
│   ├── pdf_dashboard.py       # PDF del dashboard
│   └── excel_dashboard.py     # Export Excel del dashboard
│
└── static/
    ├── css/style.css          # Estilos globales
    ├── favicon.svg
    ├── img/                   # Logos e iconos del sistema
    └── uploads/               # Fotos, manuales, certificados subidos por usuarios
```

---

## 4. Base de Datos — Esquema Completo

### 4.1 Tabla: `usuarios`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK Integer | — |
| nombre | str(150) | Nombre completo |
| email | str(150) UNIQUE | Login |
| hashed_password | str(200) | bcrypt |
| rol | str(30) | `administrador` · `operador` · `solo_lectura` |
| activo | bool | Puede desactivarse sin borrar |
| created_at | DateTime | Auto |

### 4.2 Tabla: `equipos`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK | — |
| codigo | str(50) UNIQUE | Código interno del equipo |
| nombre | str(200) | Nombre descriptivo |
| descripcion | Text | — |
| marca, modelo | str | Datos del fabricante |
| numero_serie | str | — |
| numero_inventario | str | Código de activo fijo |
| fecha_adquisicion | Date | — |
| costo | Float | Valor de adquisición |
| area, ubicacion | str | Organización física |
| responsable | str(150) | Custodio del equipo |
| foto_path | str(300) | Ruta en `static/uploads/` |
| manual_path | str(300) | Ruta del manual técnico |
| estado | str(40) | Máquina de estados (ver §6.1) |
| apto_para_uso | bool | Confirmación metrológica |
| confirmacion_metrologica | bool | Estado de aprobación global |
| created_at | DateTime | — |

**Relaciones:** magnitudes (1:N) · historial_estados (1:N) · mantenimientos (1:N) · plan_mantenimiento (1:1)

### 4.3 Tabla: `magnitudes_equipo`
Cada equipo puede medir múltiples magnitudes (temperatura, presión, masa, etc.)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK | — |
| equipo_id | FK → equipos | — |
| nombre | str(150) | Ej: "Temperatura" |
| simbolo | str(20) | Ej: "T" |
| unidad | str(50) | Ej: "°C" |
| rango_min, rango_max | Float | Rango de medición |
| resolucion | str(100) | Ej: "0.1 °C" |
| emp_texto | str(200) | EMP en texto (p.ej. "± 0.5 °C") |
| emp_valor | Float | EMP numérico para cálculos |
| emp_unidad | str(50) | — |
| clase_exactitud | str(50) | — |
| tipo_instrumento | str(30) | `continuo` · `discreto` |
| umbral_alerta_pct | Float | % del EMP que activa alerta (default 70) |
| umbral_fuera_pct | Float | % del EMP que indica fuera de tolerancia (default 100) |
| activa | bool | Se puede desactivar con justificación |
| motivo_desactivacion | Text | — |
| orden | Integer | Orden de presentación |
| notas | Text | — |

**Relaciones:** calibraciones (1:N) · plan_verificacion (1:1) · evaluacion_riesgo (1:1) · config_ilac (1:1)

### 4.4 Tabla: `calibraciones`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK | — |
| magnitud_id | FK | — |
| equipo_id | FK | — |
| numero_certificado | str(100) | Nº de certificado del laboratorio |
| laboratorio | str(200) | Nombre del laboratorio de calibración |
| acreditacion_laboratorio | str(100) | Código de acreditación |
| fecha_calibracion | Date | — |
| proxima_calibracion | Date | Fecha de vencimiento |
| patrones_utilizados | Text | Trazabilidad metrológica |
| metodo_calibracion | str(200) | Norma/procedimiento aplicado |
| temperatura_ambiente, humedad_relativa | Float | Condiciones ambientales |
| trazabilidad | Text | Cadena de trazabilidad |
| certificado_path | str(300) | Archivo del certificado |
| costo | Float | Costo de la calibración |
| resultado | str(30) | `pendiente` · `aprobado` |
| grado_regresion_sel | Integer | Grado de polinomio seleccionado (1-5) |
| usar_incertidumbre | bool | Incluir U en decisión de conformidad |
| aprobado_por_id | FK → usuarios | — |
| fecha_aprobacion | DateTime | — |

**Relaciones:** puntos (1:N → puntos_calibracion)

### 4.5 Tabla: `puntos_calibracion`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| calibracion_id | FK | — |
| numero_punto | Integer | Orden del punto |
| valor_patron | Float | Valor del patrón de referencia |
| valor_indicado | Float | Valor leído en el instrumento |
| error | Float | Diferencia (indicado - patron) |
| tolerancia_inf, tolerancia_sup | Float | Límites de tolerancia |
| incertidumbre | Float | Incertidumbre expandida U |
| abs_error_mas_u | Float | |error| + U para decisión de conformidad |
| emp_punto | Float | EMP aplicado a este punto |
| dentro_tolerancia | bool | Resultado del semáforo |

### 4.6 Tabla: `historiales_estados`
Auditoría de cambios de estado del equipo.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| equipo_id | FK | — |
| usuario_id | FK | — |
| estado_anterior, estado_nuevo | str(50) | — |
| motivo | Text | Justificación del cambio |
| fecha | DateTime | — |

### 4.7 Tabla: `planes_verificacion`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| magnitud_id | FK | — |
| equipo_id | FK | — |
| frecuencia_meses | Integer | Periodicidad de la verificación intermedia |
| procedimiento | Text | Procedimiento a seguir |
| patron_referencia | str(200) | Patrón de referencia usado |
| umbral_alerta_pct | Float | % desviación para alerta |
| umbral_fuera_pct | Float | % desviación para reprobado |
| activo | bool | — |
| justificacion_no_aplica | Text | Si no se aplica |

### 4.8 Tabla: `verificaciones_intermedias`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| plan_id | FK | — |
| equipo_id, magnitud_id | FK | — |
| fecha | Date | Fecha de realización |
| proxima_verificacion | Date | — |
| tipo | str(50) | `programada` · `especial` |
| realizada_por | str(150) | — |
| patron_usado | str(200) | — |
| resultado | str(30) | `pendiente` · `aprobado` · `reprobado` · `alerta` |
| accion_tomada | str(50) | Corrección aplicada |
| observaciones | Text | — |
| archivo_path | str(300) | Documento adjunto |
| max_desviacion_pct | Float | Máxima desviación registrada |

### 4.9 Tabla: `puntos_verificacion`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| verificacion_id | FK | — |
| numero_punto | Integer | — |
| valor_patron | Float | — |
| valor_indicado | Float | — |
| error | Float | — |
| tolerancia_inf, tolerancia_sup | Float | — |
| desviacion_pct | Float | (|error| / |emp|) × 100 |
| resultado | str(20) | `ok` · `alerta` · `fuera` |

### 4.10 Tabla: `mantenimientos`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| equipo_id | FK | — |
| tipo | str(30) | `preventivo` · `correctivo` |
| origen | str(20) | `programado` · `demanda` |
| titulo | str(200) | — |
| descripcion | Text | — |
| responsable_interno | str(150) | — |
| empresa_externa, tecnico_externo | str | Servicio externo |
| orden_trabajo | str(100) | Referencia OT |
| fecha_programada, fecha_inicio, fecha_fin | Date | — |
| estado | str(30) | `programado` · `en_ejecucion` · `completado` |
| falla_encontrada | Text | — |
| trabajo_realizado | Text | — |
| repuestos_utilizados | Text | — |
| costo | Float | — |
| requiere_calibracion | bool | Si se requiere recalibrar |
| afecta_medicion | bool | — |
| observaciones_metrologicas | Text | — |
| archivo_path | str(300) | — |

### 4.11 Tabla: `planes_mantenimiento`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| equipo_id | FK | — |
| frecuencia_meses | Integer | — |
| tipo | str(30) | `preventivo` |
| descripcion | Text | Tareas del mantenimiento |
| responsable | str(150) | — |
| activo | bool | — |

### 4.12 Tabla: `evaluaciones_riesgo` (ILAC G24)
14 factores de riesgo, escala 1-5:

| Factor | Descripción |
|--------|-------------|
| f_incertidumbre | Nivel de incertidumbre de la medición |
| f_tipo | Tipo de instrumento y su estabilidad |
| f_riesgo_emp | Riesgo asociado al EMP del proceso |
| f_fabricante | Recomendación del fabricante |
| f_deriva | Historial de deriva del instrumento |
| f_uso | Intensidad de uso |
| f_ambiental | Condiciones ambientales de uso |
| f_magnitud | Importancia de la magnitud medida |
| f_similares | Comportamiento de equipos similares |
| f_comparaciones | Resultados de comparaciones inter-laboratorio |
| f_verificaciones | Historial de verificaciones intermedias |
| f_transporte | Riesgo por transporte o manejo |
| f_personal | Competencia del personal operador |
| f_legal | Requisitos legales o reglamentarios |

Campos adicionales:
| Campo | Descripción |
|-------|-------------|
| puntuacion_total | Promedio de factores |
| intervalo_sugerido_meses | Calculado por fórmula ILAC |
| intervalo_adoptado_meses | Selección del usuario |
| justificacion | Justificación del intervalo adoptado |
| justificacion_exceso | Requerida si adoptado > sugerido |

### 4.13 Tabla: `config_ilac`
| Campo | Descripción |
|-------|-------------|
| metodo | Método ILAC seleccionado (m1-m5) |
| intervalo_inicial_meses | Punto de partida (default 12) |
| intervalo_actual_meses | Vigente |
| intervalo_minimo/maximo | Límites (default 1-60 meses) |
| porcentaje_escalera | Factor de ajuste (default 80%) |

### 4.14 Tabla: `config_laboratorio`
Configuración del laboratorio: nombre, razón social, dirección, logo, códigos de formato de documentos, versiones, firmantes (elaborado/revisado/aprobado por).

---

## 5. API y Rutas

### 5.1 Autenticación — `/usuarios`
| Método | Ruta | Descripción | Rol mínimo |
|--------|------|-------------|-----------|
| GET | `/usuarios/login` | Formulario de login | — |
| POST | `/usuarios/login` | Autenticar (email/pass o master key) | — |
| GET | `/usuarios/logout` | Cerrar sesión | Cualquiera |
| GET | `/usuarios/` | Lista de usuarios | Administrador |
| GET | `/usuarios/nuevo` | Formulario nuevo usuario | Administrador |
| POST | `/usuarios/nuevo` | Crear usuario | Administrador |
| POST | `/usuarios/{uid}/cambiar-password` | Cambiar contraseña | Administrador |
| POST | `/usuarios/{uid}/toggle-activo` | Activar/desactivar usuario | Administrador |

### 5.2 Equipos — `/equipos`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/equipos/` | Lista de equipos con estados |
| GET | `/equipos/nuevo` | Formulario nuevo equipo |
| POST | `/equipos/nuevo` | Crear equipo (con fotos y manual) |
| GET | `/equipos/{eid}` | Detalle + línea de tiempo unificada |
| GET | `/equipos/{eid}/editar` | Formulario edición |
| POST | `/equipos/{eid}/editar` | Actualizar equipo |
| POST | `/equipos/{eid}/estado` | Cambiar estado con log |

### 5.3 Magnitudes — `/magnitudes`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/magnitudes/equipo/{eid}` | Lista de magnitudes |
| GET | `/magnitudes/equipo/{eid}/nueva` | Formulario nueva magnitud |
| POST | `/magnitudes/equipo/{eid}/nueva` | Crear magnitud |
| GET | `/magnitudes/{mid}/editar` | Editar magnitud |
| POST | `/magnitudes/{mid}/editar` | Actualizar |
| POST | `/magnitudes/{mid}/toggle-activa` | Activar/desactivar |

### 5.4 Calibraciones — `/calibraciones`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/calibraciones/magnitud/{mid}` | Historial de calibraciones |
| GET | `/calibraciones/magnitud/{mid}/nueva` | Nueva calibración |
| POST | `/calibraciones/magnitud/{mid}/nueva` | Registrar calibración |

### 5.5 Análisis — `/analisis`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/analisis/{cid}` | Análisis completo + regresión |
| POST | `/analisis/{cid}/punto` | Agregar punto de calibración |
| POST | `/analisis/{cid}/punto/{pid}/eliminar` | Eliminar punto |
| POST | `/analisis/{cid}/toggle-incertidumbre` | Toggle uso de incertidumbre |
| POST | `/analisis/{cid}/regresion` | Seleccionar grado polinomio |
| POST | `/analisis/{cid}/aprobar` | Aprobar calibración → equipo operativo |
| GET | `/analisis/{cid}/pdf` | Generar PDF del análisis |

### 5.6 Verificaciones — `/verificaciones`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/verificaciones/plan/{mid}` | Plan de verificación |
| POST | `/verificaciones/plan/{mid}` | Guardar plan |
| GET | `/verificaciones/historial/{mid}` | Historial de verificaciones |
| GET | `/verificaciones/nueva/{mid}` | Nueva verificación |
| POST | `/verificaciones/nueva/{mid}` | Crear registro |
| GET | `/verificaciones/{vid}/puntos` | Ingresar puntos |
| POST | `/verificaciones/{vid}/punto` | Agregar punto |
| POST | `/verificaciones/{vid}/punto/{pid}/eliminar` | Eliminar punto |
| POST | `/verificaciones/{vid}/cerrar` | Cerrar verificación |
| GET | `/verificaciones/{vid}/pdf` | PDF de verificación |

### 5.7 Mantenimientos — `/mantenimientos`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/mantenimientos/equipo/{eid}` | Historial de mantenimiento |
| GET | `/mantenimientos/equipo/{eid}/nuevo` | Formulario nuevo |
| POST | `/mantenimientos/equipo/{eid}/nuevo` | Crear registro |
| POST | `/mantenimientos/{mid}/pdf` | PDF del mantenimiento |

### 5.8 Plan de mantenimiento — `/plan-mantenimiento`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/plan-mantenimiento/equipo/{eid}` | Ver/editar plan |
| POST | `/plan-mantenimiento/equipo/{eid}` | Guardar plan |

### 5.9 ILAC G24 — `/ilac`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/ilac/riesgo/{mid}` | Formulario evaluación de riesgo |
| POST | `/ilac/riesgo/{mid}` | Guardar evaluación |
| GET | `/ilac/nuevo_periodo` | Configuración de período |
| POST | `/ilac/nuevo_periodo` | Guardar configuración ILAC |

### 5.10 Dashboard — `/dashboard`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/dashboard/` | KPIs + tablas de estado |
| GET | `/dashboard/pdf` | Exportar PDF |
| GET | `/dashboard/excel` | Exportar Excel |

### 5.11 Calendario — `/calendario`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/calendario/` | Vista mensual + actividades próximas |

### 5.12 Configuración del laboratorio — `/config-lab`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/config-lab/` | Formulario de configuración |
| POST | `/config-lab/guardar` | Guardar + subir logo |

### 5.13 Auditoría — `/auditoria`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/auditoria/` | Resumen estado de todos los equipos |

---

## 6. Lógica de Negocio Clave

### 6.1 Máquina de estados del equipo

```
en_espera_calibracion
        │
        ▼
    operativo ◄──────────────────────┐
        │                            │
        ├──► en_calibracion          │
        │         │                  │
        │         ▼                  │
        │    [análisis aprobado] ─────┘
        │
        ├──► en_mantenimiento
        │         │
        │         ▼
        │    [mantenimiento completado] ──► requiere_calibracion?
        │                                        │yes: en_espera_calibracion
        │                                        │no:  operativo
        │
        └──► fuera_de_uso ──► dado_de_baja
```

### 6.2 Semáforo de calibración

```python
# Con incertidumbre activada:
verde = (abs(error) + incertidumbre) <= abs(emp)

# Sin incertidumbre:
verde = abs(error) <= abs(emp)

# Amarillo (alerta):
amarillo = abs(error) <= abs(emp) * (umbral_alerta_pct / 100)
```

### 6.3 Cálculo del intervalo ILAC G24

```
promedio = suma(14 factores) / 14

Tabla de intervalos sugeridos:
  promedio ≤ 1.5  →  3 meses   (riesgo muy alto)
  promedio ≤ 2.0  →  6 meses   (riesgo alto)
  promedio ≤ 2.5  →  9 meses   (riesgo medio)
  promedio ≤ 3.0  → 12 meses   (estándar)
  promedio > 3.0  → 18 meses   (riesgo bajo, máximo permitido)

Si intervalo_adoptado > intervalo_sugerido → justificación obligatoria
Si fabricante_meses < intervalo_calculado → prevalece el fabricante
```

### 6.4 Análisis de regresión

- Polinomios grados 1-5 usando `numpy.polyfit`
- Se calcula R² para cada grado
- El usuario selecciona el grado óptimo
- Ecuación y residuales se muestran en el análisis
- El grado seleccionado se almacena en `calibracion.grado_regresion_sel`

### 6.5 Desviación en verificaciones

```
desviacion_pct = (abs(error) / abs(emp)) × 100

resultado:
  < umbral_alerta_pct   → ok (verde)
  < umbral_fuera_pct    → alerta (amarillo)
  ≥ umbral_fuera_pct    → fuera (rojo) → reprobado
```

---

## 7. Sistema de Licencias

### 7.1 Funcionamiento actual

El sistema usa HMAC-SHA256 para firmar un archivo `licencia.json` que se entrega al cliente junto con la aplicación.

```json
{
  "cliente": "Empresa ABC S.A.S",
  "modulos": [],
  "vence": "2026-12-31",
  "generada": "2025-05-14",
  "firma": "a3f5c8..."
}
```

### 7.2 Estados de licencia

| Estado | `esta_activa()` | `puede_escribir()` | Comportamiento |
|--------|----------------|-------------------|----------------|
| Activa | `True` | `True` | Funcionalidad completa |
| Vencida | `False` | `False` | Solo lectura + banner de alerta |
| Sin licencia | `False` | `False` | Solo lectura + banner urgente |
| ≤15 días | `True` | `True` | Funcionalidad completa + banner de aviso |

### 7.3 Generar licencia (CLI)

```bash
# Licencia básica
python licencia.py generar "Empresa ABC S.A.S" 2026-12-31

# Con módulos premium
python licencia.py generar "Empresa ABC S.A.S" 2026-12-31 avanzado_ilac,reportes_avanzados

# Verificar estado
python licencia.py verificar
```

### 7.4 Proceso de renovación (manual actual)

1. Cliente paga la suscripción
2. Proveedor genera nueva `licencia.json` con nueva fecha de vencimiento
3. Se envía archivo al cliente
4. Cliente reemplaza el archivo en la carpeta de la aplicación

### 7.5 Pendiente — Portal de suscripciones (MVP)

Se debe agregar:
- Panel web de administración de clientes y licencias (para el proveedor)
- Renovación automática (cliente ingresa clave de renovación)
- Control de número de equipos por plan
- Planes: Básico (≤25 equipos) / Estándar (≤100) / Ilimitado

---

## 8. Autenticación y Roles

### 8.1 Roles del sistema

| Rol | Descripción | Restricciones |
|-----|-------------|---------------|
| `administrador` | Acceso total | — |
| `operador` | Puede crear/editar datos | No gestiona usuarios |
| `solo_lectura` | Solo visualización | No puede crear ni editar |

### 8.2 Credenciales por defecto

- **Admin inicial:** `admin@metrogest.com` / `admin123` ← **cambiar en producción**
- **Master key soporte:** cualquier email + contraseña `MetroGest2024Soporte` ← confidencial

### 8.3 Sesiones

- Sesión en cookie usando `SessionMiddleware` de Starlette
- Secret key: `"metrogest-2024-secret"` ← **cambiar en producción**
- Sin expiración automática (cerrar sesión al cerrar navegador)

---

## 9. Generación de PDFs

Todos los PDFs siguen un formato controlado con:
- Header: logo del laboratorio, nombre, código del documento, versión, fecha
- Footer: numeración de páginas
- Campos de firma: Elaborado por / Revisado por / Aprobado por
- Datos tomados de `config_laboratorio`

### Tipos de PDFs generados

| Tipo | Ruta | Módulo |
|------|------|--------|
| Análisis de calibración | `/analisis/{id}/pdf` | `utils/pdf_analisis.py` |
| Verificación intermedia | `/verificaciones/{id}/pdf` | `utils/pdf_docs.py` |
| Mantenimiento | `/mantenimientos/{id}/pdf` | `utils/pdf_docs.py` |
| Dashboard de estado | `/dashboard/pdf` | `utils/pdf_dashboard.py` |

---

## 10. Almacenamiento de Archivos

| Tipo | Directorio | Nombre de archivo |
|------|------------|-------------------|
| Foto de equipo | `static/uploads/` | `foto_{uuid}.ext` |
| Manual técnico | `static/uploads/` | `manual_{uuid}.ext` |
| Certificado de calibración | `static/certificados/` | `cert_{uuid}.ext` |
| Documento de verificación | `static/certificados/` | `verif_{uuid}.ext` |
| Documento de mantenimiento | `static/certificados/` | `mant_{uuid}.ext` |
| Logo del laboratorio | `static/uploads/` | `logo_lab.ext` |

Todos los archivos usan UUID para evitar colisiones y no exponer rutas predecibles.

---

## 11. Configuración y Arranque

### 11.1 Primera instalación

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar migraciones (solo si hay datos existentes)
python migrar.py

# 4. Arrancar
python main.py
# o doble clic en iniciar.bat (Windows)
```

### 11.2 Acceso
- URL: `http://localhost:8000`
- Credenciales iniciales: `admin@metrogest.com` / `admin123`

### 11.3 Secuencia de inicialización (main.py)
1. Crear directorios `static/uploads` y `static/certificados`
2. Auto-crear tablas SQLAlchemy (si no existen)
3. Crear usuario admin inicial (si no hay ninguno)
4. Crear config laboratorio por defecto
5. Registrar todos los routers
6. Iniciar Uvicorn en `0.0.0.0:8000`

---

## 12. Diseño Visual

### 12.1 Paleta de colores

| Variable | Color | Uso |
|----------|-------|-----|
| Primary | `#1a4f8a` | Sidebar, headers, botones principales |
| Accent | `#e8a020` | Dorado para énfasis y logo |
| Success | `#16a34a` | Verde — aprobado, operativo |
| Warning | `#d97706` | Ámbar — alerta, próximo a vencer |
| Danger | `#dc2626` | Rojo — vencido, reprobado |
| Neutral | `#f8fafc` | Fondo de páginas |

### 12.2 Layout

- Sidebar fijo de 250px con navegación por secciones
- Área de contenido principal con topbar
- Diseño responsive con grid CSS
- Tipografía: Segoe UI

### 12.3 Secciones del menú

| Sección | Items |
|---------|-------|
| Operación | Dashboard, Calendario |
| Inventario | Equipos, Magnitudes |
| Análisis | Calibraciones, Verificaciones, ILAC |
| Gestión | Mantenimientos, Auditoría |
| Administración | Usuarios, Config. Laboratorio |

---

## 13. Flujo de Trabajo Típico

### 13.1 Onboarding de nuevo equipo

```
1. Registrar equipo (código, datos, foto, manual)
      │
      ▼
2. Definir magnitudes (temperatura, presión, etc.)
      │
      ▼
3. Evaluar riesgo ILAC G24 (14 factores)
      │
      ▼
4. Configurar intervalo de calibración adoptado
      │
      ▼
5. Definir plan de verificación intermedia
      │
      ▼
6. Definir plan de mantenimiento preventivo
      │
      ▼
7. Estado inicial: en_espera_calibracion
```

### 13.2 Ciclo de calibración

```
Calibración vence / equipo nuevo
        │
        ▼
Registrar certificado de calibración
        │
        ▼
Ingresar puntos (valor patrón, valor indicado, incertidumbre)
        │
        ▼
Seleccionar grado de regresión (analizar R²)
        │
        ▼
Revisar semáforo (verde/amarillo/rojo por punto)
        │
        ▼
¿Todos los puntos aceptables?
        │yes                    │no
        ▼                       ▼
Aprobar calibración       Documentar no conformidad
        │                       │
        ▼                       ▼
Equipo → operativo        Equipo → fuera_de_uso / dado_de_baja
        │
        ▼
Generar PDF para auditoría
```

### 13.3 Verificación intermedia

```
Fecha de verificación programada
        │
        ▼
Crear nueva verificación (tipo, patrón, responsable)
        │
        ▼
Ingresar puntos de verificación
        │
        ▼
Sistema calcula desviación %
        │
        ├── Verde (<70%): aprobado
        ├── Amarillo (70-100%): alerta → acción correctiva
        └── Rojo (>100%): reprobado → calibración requerida
        │
        ▼
Cerrar verificación y generar PDF
```

---

## 14. Estado del MVP — Pendientes

### 14.1 Funciones por completar / mejorar

- [ ] **Portal de gestión de licencias:** Panel web para administrar clientes, generar y renovar licencias
- [ ] **Renovación de licencia desde la app:** Que el cliente pueda ingresar una clave de renovación sin reemplazar el archivo manualmente
- [ ] **Límite de equipos por plan:** Validar que no se excedan los equipos permitidos por la licencia
- [ ] **Notificaciones de vencimiento:** Email/alerta al cliente cuando quedan X días para vencer
- [ ] **Backup y restore de BD:** Función de exportar/importar la base de datos
- [ ] **Exportar inventario completo:** Excel con todos los equipos y estados
- [ ] **Mejoras UX del análisis:** Entrada de puntos más rápida (ej: pegar desde Excel)
- [ ] **Responsive móvil:** Algunas vistas del dashboard y calendario en tablet

### 14.2 Mejoras de diseño identificadas

- [ ] Cards de KPI en dashboard con tendencia (comparar mes anterior)
- [ ] Gráfica de Gantt en el calendario para vista de período
- [ ] Indicador visual de ILAC en el detalle del equipo
- [ ] Foto del equipo visible en el listado (thumbnail)
- [ ] Modo oscuro (opcional para clientes)

### 14.3 Deuda técnica a resolver antes de producción

- [ ] Cambiar secret key de sesión a variable de entorno
- [ ] Cambiar contraseña admin inicial forzosamente en primer uso
- [ ] Configurar logs de aplicación a archivo
- [ ] Manejo de errores 404/500 con páginas personalizadas
- [ ] Validación de tamaño máximo de archivos subidos

---

## 15. Guía de Desarrollo

### 15.1 Agregar un nuevo router

```python
# 1. Crear routers/nuevo_modulo.py
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from database import get_db
import auth

router = APIRouter(prefix="/nuevo", tags=["nuevo"])

@router.get("/")
def listar(request: Request, db: Session = Depends(get_db)):
    usuario = auth.obtener_usuario_actual(request, db)
    if not usuario:
        return RedirectResponse(url="/usuarios/login")
    # ...

# 2. Registrar en main.py
from routers import nuevo_modulo
app.include_router(nuevo_modulo.router)
```

### 15.2 Agregar un nuevo modelo de BD

```python
# En models.py
class NuevoModelo(Base):
    __tablename__ = "nueva_tabla"
    
    id = Column(Integer, primary_key=True, index=True)
    campo = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    equipo_id = Column(Integer, ForeignKey("equipos.id"))
    equipo = relationship("Equipo", back_populates="nuevos_modelos")
```

### 15.3 Control de acceso por rol

```python
# Solo administrador
if usuario.rol != "administrador":
    return RedirectResponse(url="/equipos/")

# Solo lectura bloqueado
if usuario.rol == "solo_lectura":
    return RedirectResponse(url="/equipos/")

# Licencia vencida bloqueada para escritura
import licencia
if not licencia.puede_escribir():
    return RedirectResponse(url="/equipos/")
```

---

## 16. Glosario Metrológico

| Término | Significado |
|---------|-------------|
| EMP | Error Máximo Permisible (límite de tolerancia) |
| Incertidumbre (U) | Incertidumbre expandida de medición |
| Trazabilidad | Cadena ininterrumpida de comparaciones con patrones nacionales/internacionales |
| Calibración | Conjunto de operaciones para establecer relación entre valores de un instrumento y los del patrón |
| Verificación intermedia | Comprobación periódica entre calibraciones para asegurar que el instrumento se mantiene en estado de calibración |
| ILAC G24 | Guía de la ILAC para determinación de intervalos de recalibración |
| ISO/IEC 10012 | Norma de sistemas de gestión de las mediciones |
| Confirmación metrológica | Conjunto de operaciones requeridas para asegurar que el equipo cumple los requisitos para su uso previsto |
| Semáforo | Sistema de colores (verde/amarillo/rojo) para indicar conformidad de puntos de calibración |
| Regresión | Ajuste matemático de la curva de error del instrumento |

---

*Documento generado el 2026-05-14 · MetroGest v2 · Confidencial*
