# MetroGest v2 — Resumen ejecutivo

> Para el decisor de negocio del cliente (gerente de calidad, director de
> laboratorio). Sin jerga técnica — pensado para leerse en una reunión, no
> para auditoría. El detalle técnico completo, con evidencia de pruebas,
> está en [`ANEXO_TECNICO.md`](ANEXO_TECNICO.md).

## El problema que resuelve

Un laboratorio con decenas o miles de equipos de medición necesita poder
demostrar, en cualquier momento y ante cualquier auditoría, que cada
instrumento está calibrado, verificado y mantenido conforme a norma — y
que puede probarlo con registros completos, no con hojas de cálculo
dispersas ni carpetas físicas. MetroGest centraliza ese control: inventario
de equipos, calibraciones, verificaciones intermedias, mantenimientos y
evaluación de riesgo, todo en un solo lugar, con trazabilidad completa de
cada cambio.

## Cumplimiento normativo

MetroGest implementa **ISO/IEC 10012:2003** (sistemas de gestión de las
mediciones) e **ILAC G24:2017** (intervalos de calibración) de forma
nativa: no son un módulo aparte, son el criterio con el que el sistema
calcula el semáforo de conformidad de cada calibración y sugiere cuándo
debe recalibrarse cada equipo, según 14 factores de riesgo normalizados.

Para clientes de industria farmacéutica o regulada, el sistema además
incorpora rastro de auditoría automático de cada cambio, firma electrónica
con reautenticación por contraseña en las decisiones críticas (aprobar una
calibración, cerrar una verificación), y un paquete de validación de
sistemas computarizados (IQ/OQ/PQ) preparado para ejecutarse en la
instalación del cliente — ver la sección de evidencia técnica en el anexo.

## Qué obtiene el cliente

- **Control visual inmediato**: semáforo verde/amarillo/rojo de
  conformidad de cada calibración, sin necesidad de interpretar cifras.
- **Alertas de vencimiento** en el dashboard y el calendario, para no
  descubrir un equipo vencido en medio de una auditoría.
- **Documentos listos para auditoría**: PDF con encabezado de formato del
  propio laboratorio, generados automáticamente a partir de los datos
  registrados.
- **Trazabilidad completa por equipo**: historial unificado de
  calibraciones, verificaciones, mantenimientos y cambios de estado.
- **Control de acceso por rol**: administrador, operador y solo lectura —
  cada usuario ve y puede hacer solo lo que su rol permite.

## Capacidad soportada, con evidencia

El sistema fue probado con una carga sintética de **1,600 equipos** y
**15-20 usuarios concurrentes** — el volumen y la concurrencia que definen
el objetivo de negocio de esta versión — no solo se diseñó para eso, se
midió. Bajo esa carga sostenida (25 minutos continuos), el dashboard y el
listado de equipos responden en cuestión de milisegundos en el caso
típico, la generación de documentos PDF/Excel no bloquea a los demás
usuarios mientras ocurre, y no se observó ninguna pérdida de datos, error
del sistema ni fuga de memoria. El detalle completo de esa prueba —
metodología, cifras exactas y las dos rondas de corrección que se hicieron
antes de aprobarla — está documentado en el anexo técnico, disponible para
el equipo de TI del cliente o un auditor que quiera verificarlo.

## Modelo de entrega

Instalación local en el servidor del cliente (los datos nunca salen de su
infraestructura), con licencia de suscripción anual. El sistema queda
protegido por un mecanismo de licencia firmado digitalmente: sin licencia
vigente, el acceso pasa automáticamente a modo solo lectura — nunca se
pierden datos, solo se restringe la escritura hasta renovar.

## Siguiente paso

El anexo técnico (`ANEXO_TECNICO.md`) contiene la arquitectura, el detalle
de seguridad, el modelo de datos, el plan de respaldo/recuperación y la
evidencia completa de las pruebas de calidad y de carga — recomendado para
el equipo técnico del cliente antes de la instalación, o para cualquier
auditoría posterior.
