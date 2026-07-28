# MetroGest v2

**Sistema de Gestión Metrológica** para laboratorios industriales y de calibración, alineado con **ISO/IEC 10012:2003** e **ILAC G24:2017**.

![Estado](https://img.shields.io/badge/estado-pre--MVP-orange)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red)
![Licencia](https://img.shields.io/badge/licencia-propietario-lightgrey)

---

## Descripcion del producto

MetroGest v2 es una aplicacion web de escritorio (instalacion local) para la gestion integral de la confirmacion metrologica de equipos de medicion. Controla el ciclo de vida completo de cada instrumento: inventario, calibraciones, verificaciones intermedias, mantenimientos y evaluacion de riesgos segun ILAC G24.

### Propuesta de valor

- Cumplimiento documentado con ISO/IEC 10012 e ILAC G24
- Control visual (semaforo verde/amarillo/rojo) de conformidad de calibraciones
- Generacion automatica de PDFs con encabezado de formato para auditorias
- Alertas de vencimientos en dashboard y calendario mensual
- Trazabilidad completa de cada equipo: historial unificado de calibraciones, verificaciones y mantenimientos
- Sistema de licencias por suscripcion anual con HMAC-SHA256

### Modelo de negocio

- **Fase 1 (actual):** Instalacion local + licencia por suscripcion anual entregada como archivo JSON firmado
- **Fase 2 (futura):** Migracion a SaaS web multi-tenant

---

## Modulos principales

| Modulo | Descripcion |
|--------|-------------|
| Equipos | Inventario con foto, manual tecnico, estados y historial de cambios |
| Magnitudes | Cada equipo puede tener multiples magnitudes de medicion (temperatura, presion, masa, etc.) |
| Calibraciones | Registro de certificados, puntos de medicion con incertidumbre, regresion polinomial (grados 1-5) |
| Analisis | Semaforo de conformidad con EMP, seleccion de grado de regresion, aprobacion de calibracion |
| Verificaciones intermedias | Plan de verificacion, registro de puntos, calculo de desviacion %, cierre con accion correctiva |
| Mantenimientos | Preventivos y correctivos, internos y externos, con ordenes de trabajo |
| ILAC G24 | Evaluacion de riesgo con 14 factores, calculo del intervalo de recalibracion, ajuste de periodos |
| Dashboard | KPIs en tiempo real: equipos operativos, calibraciones vencidas, proximas actividades (30 dias) |
| Calendario | Vista mensual de calibraciones, verificaciones y mantenimientos programados |
| Auditoria | Listado de estado de todos los equipos con fechas proximas |
| Config. Laboratorio | Nombre, logo, codigos de formato de documentos, firmantes para PDFs |
| Usuarios | Roles: administrador, operador, solo_lectura |

---

## Requisitos del sistema

- **Python:** 3.10 o superior
- **Base de datos:** PostgreSQL 14+ (produccion). SQLite queda como fallback automatico si no se define `DATABASE_URL`, mas indicado solo para pruebas locales rapidas.
- **Sistema operativo:** Windows 10/11 (probado), Linux/macOS compatible
- **Disco:** ~200 MB incluyendo entorno virtual
- **RAM:** 256 MB minimo
- **Puerto:** 8000 (configurable en `main.py`)
- **Navegador:** cualquier navegador moderno (Chrome, Firefox, Edge)

---

## Instalacion

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/metrogest-v2.git
cd metrogest-v2

# 2. Crear entorno virtual
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env
# Editar .env: DATABASE_URL, SESSION_SECRET, credenciales de correo, etc.

# 5. Aplicar migraciones de base de datos (crea/actualiza el esquema en PostgreSQL)
alembic upgrade head

# 6. Iniciar la aplicacion
python main.py

# Alternativa en Windows: doble clic en iniciar.bat
# (crea el entorno virtual, instala dependencias, corre las migraciones
#  y levanta el servidor, todo en un solo paso)
```

Abrir en el navegador: `http://localhost:8000`

**Credenciales iniciales:**

En el primer arranque, si no existe ningun usuario, la aplicacion crea automaticamente un administrador (`admin@metrogest.com`) con una **contrasena temporal aleatoria** que se imprime una sola vez en la consola/log (`logs/app.log`) al iniciar. El sistema obliga a cambiarla en el primer login.

> Ya no existe una contrasena por defecto tipo `admin123` — fue eliminada como parte de las mejoras de seguridad (ver seccion "Deuda tecnica").

**¿Olvidaste la contrasena de administrador?** Con el servidor detenido, corre:

```bash
python resetear_password_admin.py admin@metrogest.com
```

Esto genera una nueva contrasena temporal para ese usuario y obliga a cambiarla en el proximo login. Requiere acceso directo al servidor (shell/RDP) — es la via de recuperacion soportada, no hay backdoor por la pantalla de login.

---

## Estructura del proyecto

```
metrogest_v2/
├── main.py                    # Punto de entrada FastAPI, registro de routers, lifespan
├── database.py                # Engine SQLAlchemy, dependencia get_db()
├── models.py                  # 14 tablas ORM (declarative style)
├── auth.py                    # Autenticacion bcrypt, roles, sesion
├── licencia.py                # Sistema de licencias HMAC-SHA256 (CLI + API)
├── migrar.py                  # Migraciones de esquema de BD (legado, ver alembic/)
├── migrar_plan_mant.py        # Migracion especifica tabla plan_mantenimiento
├── migrar_a_postgres.py       # Migracion de datos SQLite -> PostgreSQL
├── alembic/                   # Migraciones de esquema versionadas (alembic upgrade head)
├── alembic.ini                # Configuracion de Alembic (lee DATABASE_URL de .env)
├── backup_db.py                # Respaldo automatico de PostgreSQL + verificacion de restauracion
├── resetear_password_admin.py # Recuperacion de acceso: genera password temporal para un admin
├── .env / .env.example        # Variables de entorno (no versionar .env)
├── iniciar.bat                # Arranque rapido Windows (venv + deps + migraciones + servidor)
├── requirements.txt           # Dependencias Python
│
├── routers/                   # 13 modulos de rutas
│   ├── usuarios.py            # Login, logout, gestion de usuarios
│   ├── equipos.py             # CRUD equipos + historial unificado
│   ├── magnitudes.py          # CRUD magnitudes por equipo
│   ├── calibraciones.py       # Registro de calibraciones
│   ├── analisis.py            # Analisis de puntos, regresion, aprobacion, PDF
│   ├── verificaciones.py      # Plan, registro e historial de verificaciones
│   ├── mantenimientos.py      # CRUD mantenimientos + PDF
│   ├── plan_mantenimiento.py  # Plan preventivo por equipo
│   ├── ilac.py                # Evaluacion ILAC G24, periodos, frecuencias
│   ├── dashboard.py           # KPIs, exportar PDF y Excel
│   ├── calendario.py          # Vista mensual de actividades
│   ├── config_lab.py          # Configuracion del laboratorio
│   └── auditoria.py           # Listado general con exportacion
│
├── templates/                 # 25 plantillas Jinja2
│   ├── base.html              # Layout maestro con sidebar
│   ├── login.html
│   ├── equipos/               # lista.html, formulario.html, detalle.html
│   ├── magnitudes/            # lista.html, formulario.html
│   ├── calibraciones/         # formulario.html, historial.html
│   ├── analisis/              # analisis.html
│   ├── verificaciones/        # nueva.html, historial.html, plan.html, puntos.html
│   ├── mantenimientos/        # formulario.html, lista.html, plan.html
│   ├── ilac/                  # riesgo.html, nuevo_periodo.html, frecuencias.html
│   ├── dashboard/             # dashboard.html
│   ├── calendario/            # calendario.html
│   ├── config_lab/            # config.html
│   ├── usuarios/              # formulario.html, lista.html
│   └── auditoria/             # resumen.html
│
├── utils/                     # Logica de negocio y generacion de documentos
│   ├── calculos.py            # Regresion polinomial, semaforo, calculo ILAC
│   ├── pdf_header.py          # Encabezados y pies de pagina para PDFs
│   ├── pdf_analisis.py        # PDF del analisis de calibracion
│   ├── pdf_docs.py            # PDF de verificacion, mantenimiento, plan, ILAC, listado
│   ├── pdf_dashboard.py       # PDF del dashboard
│   └── excel_dashboard.py     # Exportacion Excel del dashboard y listado general
│
└── static/
    ├── css/style.css          # Estilos globales (paleta azul/dorado)
    ├── favicon.svg
    └── img/                   # Logos e iconos del sistema
```

---

## Variables de entorno

Configuracion via `.env` (no versionar; ver `.env.example` como plantilla):

| Variable | Descripcion |
|----------|-------------|
| `SESSION_SECRET` | Clave de firma de sesiones de Starlette |
| `FORZAR_HTTPS` | `true` solo si el servidor corre detras de HTTPS real (cookie Secure + HSTS). En local sobre HTTP debe quedar en `false` |
| `DATABASE_URL` | Cadena de conexion SQLAlchemy. Postgres en produccion; si se omite, cae a `sqlite:///./metrogest.db` |
| `POSTGRES_ADMIN_PASSWORD` | Password del superusuario `postgres`, usado solo por `backup_db.py` para la base temporal de verificacion de respaldos |
| `BACKUP_RETENCION_DIAS` | Dias que se conservan los `.dump` en `backups/` antes de podarse |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USER` / `EMAIL_PASSWORD` / `EMAIL_FROM` | SMTP para alertas de vencimientos y fallos de respaldo |
| `EMAIL_DESTINATARIO` | Destinatario por defecto de las alertas |

Ejemplo de `.env`:

```env
SESSION_SECRET=tu-clave-muy-larga-y-aleatoria
FORZAR_HTTPS=false

DATABASE_URL=postgresql+psycopg2://usuario:contrasena@localhost:5432/metrogest
POSTGRES_ADMIN_PASSWORD=
BACKUP_RETENCION_DIAS=30

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=
EMAIL_PASSWORD=
EMAIL_FROM=MetroGest <contacto@metrogest.com.co>
EMAIL_DESTINATARIO=
```

---

## Tecnologias utilizadas

| Capa | Tecnologia | Version |
|------|-----------|---------|
| Backend | FastAPI | 0.136.1 |
| Servidor ASGI | Uvicorn | 0.46.0 |
| ORM | SQLAlchemy | 2.0+ |
| Base de datos | PostgreSQL (produccion) / SQLite (fallback local) | 14+ / 3.x |
| Driver PostgreSQL | psycopg2-binary | — |
| Migraciones de esquema | Alembic | — |
| Plantillas | Jinja2 | 3.1.6 |
| Middleware | Starlette (sesiones) | 1.0.0 |
| Firma de sesiones | itsdangerous | — |
| Autenticacion | passlib + bcrypt | 1.7.4 / 5.0.0 |
| PDFs | ReportLab | 4.5.0 |
| Excel | openpyxl | 3.1.5 |
| Calculos | NumPy | 2.4.4 |
| Graficas | Matplotlib | 3.10.9 |
| Fechas | python-dateutil | 2.9.0 |
| Runtime | Python | 3.10+ |

---

## Endpoints principales

### Autenticacion (`/usuarios`)
| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET/POST | `/usuarios/login` | Formulario de inicio de sesion |
| GET | `/usuarios/logout` | Cerrar sesion |
| GET/POST | `/usuarios/nuevo` | Crear usuario (solo administrador) |

### Equipos (`/equipos`)
| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/equipos/` | Lista de equipos |
| GET/POST | `/equipos/nuevo` | Registrar nuevo equipo |
| GET | `/equipos/{id}` | Detalle del equipo con historial |
| POST | `/equipos/{id}/estado` | Cambiar estado con auditoria |

### Analisis (`/analisis`)
| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/analisis/{id}` | Analisis completo de calibracion |
| POST | `/analisis/{id}/punto` | Agregar punto de medicion |
| POST | `/analisis/{id}/aprobar` | Aprobar calibracion |
| GET | `/analisis/{id}/pdf` | Exportar PDF de analisis |

### Dashboard (`/dashboard`)
| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/dashboard/` | Panel principal con KPIs |
| GET | `/dashboard/pdf` | Exportar PDF del dashboard |
| GET | `/dashboard/excel` | Exportar Excel del dashboard |

---

## Sistema de licencias

MetroGest usa un sistema de licencias basado en HMAC-SHA256. El archivo `licencia.json` se entrega al cliente y debe colocarse en la raiz de la aplicacion.

```json
{
  "cliente": "Empresa ABC S.A.S",
  "modulos": [],
  "vence": "2026-12-31",
  "generada": "2025-05-14",
  "firma": "abc123..."
}
```

### Comandos CLI para el proveedor

```bash
# Generar licencia basica
python licencia.py generar "Empresa ABC S.A.S" 2026-12-31

# Generar licencia con modulos premium
python licencia.py generar "Empresa ABC S.A.S" 2026-12-31 avanzado_ilac

# Verificar estado de la licencia instalada
python licencia.py verificar
```

### Estados de licencia

| Estado | Comportamiento |
|--------|----------------|
| Activa | Funcionalidad completa |
| Vencida | Solo lectura + banner de alerta |
| Sin licencia | Solo lectura + banner urgente |
| Proxima a vencer (<= 15 dias) | Funcionalidad completa + aviso |

---

## Roles de usuario

| Rol | Descripcion |
|-----|-------------|
| `administrador` | Acceso total: usuarios, configuracion, todos los modulos |
| `operador` | Puede crear y editar equipos, calibraciones, mantenimientos |
| `solo_lectura` | Solo visualizacion, sin creacion ni edicion |

---

## Flujo de trabajo tipico

1. Registrar equipo con datos, foto y manual tecnico
2. Definir magnitudes de medicion (temperatura, presion, etc.)
3. Evaluar riesgo ILAC G24 con los 14 factores normalizados
4. Configurar intervalo de calibracion adoptado
5. Definir plan de verificacion intermedia
6. Definir plan de mantenimiento preventivo
7. Registrar la primera calibracion e ingresar puntos de medicion
8. Analizar conformidad con semaforo y aprobar la calibracion
9. Equipo pasa a estado "operativo"
10. Monitorear vencimientos en el dashboard y calendario

---

## Roadmap — Funcionalidades planificadas

### v2.1 (proximas)
- [ ] Portal web de gestion de licencias para el proveedor
- [ ] Renovacion de licencia desde la aplicacion (clave de renovacion)
- [ ] Limites de equipos por plan (Basico ≤25 / Estandar ≤100 / Ilimitado)
- [ ] Backup y restauracion de la base de datos desde la UI

### v2.2
- [ ] Notificaciones por email de vencimientos proximos
- [ ] Exportacion de inventario completo en Excel
- [ ] Pegado de puntos de calibracion desde Excel (entrada masiva)
- [ ] Responsive movil para dashboard y calendario

### v3.0 (SaaS)
- [x] Migracion a PostgreSQL
- [ ] Arquitectura multi-tenant
- [ ] Autenticacion JWT con refresh tokens
- [ ] Panel de administracion SaaS para el proveedor
- [ ] API REST publica con autenticacion por API key

### Deuda tecnica
- [x] Mover secret keys y credenciales a variables de entorno
- [x] Forzar cambio de contrasena admin en primer uso
- [x] Configurar logging a archivo (`logs/app.log`, `logs/backup.log`, `logs/alertas.log`)
- [ ] Validacion de tamano maximo de archivos subidos
- [x] Pagina de error 500 generica (sin stacktrace al usuario)
- [ ] Paginas de error 404 personalizada

---

## Desarrollo

### Agregar un nuevo router

```python
# 1. Crear routers/nuevo_modulo.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
import auth

router = APIRouter()

@router.get("/")
def listar(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    # ...

# 2. Registrar en main.py: agregar "nuevo_modulo" a la lista _mods
```

---

## Contacto y licencia

Este es un proyecto propietario en desarrollo activo. Para consultas sobre licencias comerciales, contactar al desarrollador.

- **Desarrollador:** Independiente (Colombia)
- **Normas de referencia:** ISO/IEC 10012:2003, ILAC G24:2017

---

*MetroGest v2 — Confidencial*
