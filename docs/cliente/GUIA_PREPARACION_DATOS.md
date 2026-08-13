# Preparación de su información histórica para la migración a MetroGest

> Para la persona del laboratorio que va a reunir la información (gerente
> de calidad, metrólogo, o quien tenga el historial de calibraciones a la
> mano). Sin jerga técnica. Este documento no reemplaza la conversación
> con Edison sobre el servicio de migración — la complementa, para que la
> información llegue organizada desde el primer envío.

## Por qué esto importa

La carga de su historial (equipos, calibraciones, hasta 5 años de
información) es un servicio independiente a la licencia de MetroGest.
Cuanto más organizada llegue su información, más rápido y más económico
es el proceso — la mayoría del tiempo de una migración no se va en
transformar los datos, se va en ir y venir aclarando información que
faltaba o que no era clara desde el principio. Esta guía existe para
evitar esas vueltas.

## Qué necesitamos de usted, antes de empezar

- [ ] **Un listado de todos sus equipos de medición**, cada uno con un
      código único (el que ya usan internamente está bien, siempre que
      no se repita entre dos equipos distintos). Si hoy no tienen códigos
      consistentes, es lo primero que hay que resolver juntos — sin un
      código único por equipo no hay forma confiable de ligar su historial
      de calibraciones al equipo correcto.
- [ ] **El historial de calibraciones**, aunque esté repartido en varias
      hojas o archivos (por ejemplo, uno por año) — no hace falta que
      usted lo consolide, eso lo hacemos nosotros, pero sí que cada
      calibración sea identificable: mismo equipo, misma fecha, mismo
      criterio de qué cuenta como "una calibración realizada".
- [ ] **Los certificados de calibración en PDF**, como archivos
      individuales (no hace falta transcribirlos, solo tenerlos a la
      mano) — idealmente nombrados de forma que se puedan asociar al
      número de certificado que aparece en su registro.
- [ ] **Claridad sobre qué mide cada equipo** — si su registro no separa
      claramente "el equipo" de "la magnitud que mide" (por ejemplo, una
      balanza que además de masa registra temperatura ambiente), avísenos:
      no es un problema, pero necesitamos saberlo de antemano para
      organizarlo bien.
- [ ] **El error máximo permisible (EMP) de cada magnitud**, si lo tienen
      documentado. Sin este dato, MetroGest no puede calcular
      automáticamente el semáforo de conformidad (verde/amarillo/rojo)
      para esa magnitud — el historial igual se carga, pero queda sin ese
      control visual hasta que se defina el EMP.

Si no tiene alguno de estos puntos resuelto, no es un impedimento para
empezar — coméntelo, y lo definimos juntos como parte del proceso.

## Cómo se hace la migración, en resumen

1. Usted nos entrega la información como la tenga (Excel, PDFs de
   certificados) — no necesita reformatearla usted mismo.
2. Nosotros la organizamos y la probamos primero en un modo de
   **verificación**, que no escribe nada todavía en el sistema — solo
   revisa que todo esté completo y consistente.
3. Si esa revisión encuentra algo que no cuadra (un dato faltante, una
   fecha que no se puede leer, una posible calibración duplicada), se lo
   mostramos en un reporte claro — fila por fila, sin tecnicismos — y lo
   revisamos juntos. **Nunca se carga información dudosa sin que usted la
   confirme primero.**
4. Una vez todo quedó revisado y confirmado, se hace la carga real, con
   respaldo de seguridad tomado justo antes.
5. Al final, usted recibe un registro completo de qué se cargó, qué se
   ajustó y por qué — queda como evidencia archivada del proceso, útil
   también de cara a una auditoría.

## Preguntas frecuentes

**¿Tenemos que aprender Power Query o algo técnico?** No. La
transformación de sus datos hacia MetroGest es parte del servicio; usted
solo necesita entregar la información organizada según el checklist de
arriba.

**¿Qué pasa si no tenemos todo el historial de 5 años completo?** Se migra
lo que exista. No es necesario tener el 100% del historial para empezar —
los vacíos quedan documentados, no bloquean el resto de la carga.

**¿Nuestros datos quedan seguros durante el proceso?** Sí — se trabaja
siempre sobre una copia, nunca se toca la instalación real hasta que la
carga fue revisada y aprobada, y se toma un respaldo de seguridad
inmediatamente antes de la carga final.
