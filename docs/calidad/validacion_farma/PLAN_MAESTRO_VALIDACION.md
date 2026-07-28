# Plan Maestro de Validación (VMP) — MetroGest v2

> Documento marco que define el enfoque de validación de sistemas
> computarizados (CSV) para instalaciones de MetroGest v2 en clientes de
> industria farmacéutica. No reemplaza el Plan de Validación específico
> que cada cliente debe aprobar bajo su propio sistema de calidad — este
> VMP es la base que MetroGest (el proveedor) entrega como evidencia de
> que el producto fue diseñado y probado con esos requisitos en mente.

## 1. Propósito y alcance

MetroGest v2 gestiona registros que respaldan decisiones de conformidad
metrológica (calibraciones, verificaciones intermedias, mantenimientos) en
laboratorios que pueden operar bajo normativa GxP. Este plan cubre la
validación del **software tal como se entrega** (no la validación de un
proceso de manufactura del cliente, que es responsabilidad de cada
cliente).

Quedan **fuera de alcance** de este VMP: la infraestructura física del
servidor del cliente (temperatura del datacenter, UPS, etc.) y la
capacitación de los usuarios finales del cliente — ambos son
responsabilidad del cliente, aunque MetroGest documenta los requisitos
mínimos de entorno en la Calificación de Instalación (IQ).

## 2. Categorización GAMP5

**Categoría de trabajo (borrador, a confirmar en la primera ejecución
formal):** **Categoría 4 (producto configurado)**, con elementos de
Categoría 5 (código a medida) en los módulos de cálculo metrológico
(`utils/calculos.py`, `utils/deriva.py`, `utils/escalera.py`) y en la
lógica de riesgo ILAC G24 (`routers/ilac.py`).

Justificación: MetroGest se construye sobre un framework estándar
(FastAPI + SQLAlchemy) y gran parte de su comportamiento es configuración
(umbrales de alerta, plantillas de PDF, campos de laboratorio) — típico de
Categoría 4 — pero las fórmulas de regresión, semáforo de conformidad e
intervalos ILAC son lógica de negocio a medida, no configuración de un
producto comercial genérico — eso empuja partes del sistema hacia
Categoría 5, que exige mayor rigor de prueba unitaria sobre esa lógica
(ya existe una base real: `tests/test_calculos.py`, `tests/test_deriva.py`).

**Consecuencia práctica:** el enfoque de prueba no es uniforme — los
módulos de cálculo metrológico (Categoría 5) requieren cobertura de
pruebas unitarias exhaustiva por valor límite y caso borde; el resto del
sistema (Categoría 4) se valida principalmente por prueba funcional a
nivel de flujo (OQ) y de configuración correcta (IQ).

## 3. Enfoque de aseguramiento: basado en riesgo (CSA), documentación formal IQ/OQ/PQ

Se combinan dos decisiones tomadas con el usuario:

1. **Priorización por riesgo** (espíritu de la guía CSA de la FDA, 2022):
   el esfuerzo de prueba se concentra donde el impacto de un fallo es
   mayor para la calidad del dato o la decisión metrológica — ej.
   cálculo del semáforo de conformidad, aprobación de calibración, firma
   electrónica, rastro de auditoría — no en pantallas de bajo riesgo como
   la configuración de logo del laboratorio.
2. **Empaquetado formal completo** (IQ/OQ/PQ): aunque la *priorización*
   es por riesgo, el *entregable* que ve el cliente/auditor sigue el
   formato tradicional que la mayoría de auditores farmacéuticos todavía
   esperan — tres protocolos separados y firmables.

### Clasificación de riesgo por funcionalidad (para priorizar OQ)

| Riesgo | Funcionalidad | Justificación |
|---|---|---|
| **Alto** | Cálculo de semáforo de calibración, aprobación de calibración, firma electrónica, rastro de auditoría, control de acceso por rol, licencia (bloqueo de escritura) | Afectan directamente la validez de un registro de conformidad metrológica o pueden permitir una acción no autorizada |
| **Medio** | Cálculo de intervalo ILAC G24, verificaciones intermedias, generación de PDF/Excel, alertas de vencimiento | Afectan la planificación y trazabilidad, pero no alteran retroactivamente un registro ya aprobado |
| **Bajo** | Configuración del laboratorio (logo, nombres de formato), calendario, búsqueda global | No afectan la integridad de un registro metrológico |

## 4. Ciclo de vida de validación

```
Especificación (este VMP + GAP_ANALISIS_REGULATORIO.md)
        │
        ▼
Calificación de Instalación (IQ) ── entorno correcto, versiones correctas
        │
        ▼
Calificación Operacional (OQ) ── cada función hace lo que dice que hace,
        │                         incluyendo casos límite y de error
        ▼
Calificación de Desempeño (PQ) ── el sistema sostiene el desempeño
        │                         esperado con datos y carga reales
        ▼
Informe de Validación + aprobación
        │
        ▼
Mantenimiento del estado validado: control de cambios (ver §6),
revalidación parcial ante cambios significativos
```

## 5. Roles y responsabilidades (a completar con nombres reales antes de ejecutar)

| Rol | Responsabilidad | Quién (pendiente) |
|---|---|---|
| Dueño del proceso / Sponsor | Aprueba el VMP y el informe final de validación | Edison (proveedor) |
| Ejecutor de pruebas | Corre los protocolos IQ/OQ/PQ, registra evidencia | — |
| Revisor de calidad | Revisa que la evidencia sea completa y las desviaciones estén justificadas | — |
| Representante del cliente | Co-firma la validación en el sitio del cliente (la instalación específica) | — |

## 6. Control de cambios y mantenimiento del estado validado

- Todo cambio de esquema pasa por Alembic (ya es la práctica del repo,
  ver `CLAUDE.md` §7) — sirve como registro de control de cambios de base
  de datos.
- Todo commit queda en el historial de git con mensaje descriptivo — sirve
  como bitácora de cambios de código, pero **no sustituye** un
  procedimiento formal de control de cambios que el cliente pueda auditar.
  Pendiente: definir un procedimiento corto (`docs/calidad/validacion_farma/CONTROL_CAMBIOS.md`,
  fase futura) que clasifique cambios como "menores" (no requieren
  re-ejecutar OQ/PQ) vs. "significativos" (sí requieren) — ej. cambiar la
  fórmula de semáforo es significativo; cambiar el color de un botón no.
- Cada versión de release debería quedar etiquetada en git (`git tag`) y
  asociada a qué versión de este paquete de validación aplica — no
  implementado todavía.

## 7. Entregables de este VMP

Ver la tabla en [`README.md`](README.md) de esta carpeta — gap analysis,
IQ, OQ, PQ y anexos por marco regulatorio.

## 8. Limitaciones conocidas de este borrador

- Este VMP es un punto de partida redactado por Claude a partir del código
  real del repositorio — falta la revisión y aprobación formal de Edison
  (y, cuando aplique, del cliente) antes de poder llamarlo "aprobado".
- No sustituye asesoría legal/regulatoria especializada — para un cliente
  con requisitos estrictos de INVIMA, FDA o EMA, se recomienda que su
  propio departamento de calidad revise este paquete antes de aceptarlo
  como evidencia de validación.
