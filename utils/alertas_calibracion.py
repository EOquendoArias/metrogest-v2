import os
import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session

from utils.email_sender import send_email

logger = logging.getLogger(__name__)

# Intervalos de alerta en días relativos al vencimiento
# Negativos = días ANTES, 0 = día exacto, positivos = días DESPUÉS
INTERVALOS = {
    "antes_30":   -30,
    "antes_15":   -15,
    "antes_7":     -7,
    "antes_1":     -1,
    "dia_0":        0,
    "despues_1":    1,
    "despues_7":    7,
}


def _tipo_alerta_para_dia(dias_para_vencer: int) -> str | None:
    """Devuelve el tipo_alerta que corresponde a los días dados, o None si no aplica."""
    for tipo, umbral in INTERVALOS.items():
        if dias_para_vencer == umbral:
            return tipo
    return None


def _ya_enviada(db: Session, equipo_id: int, magnitud_id: int, tipo_alerta: str) -> bool:
    import models
    return db.query(models.HistorialAlertas).filter_by(
        equipo_id=equipo_id,
        magnitud_id=magnitud_id,
        tipo_alerta=tipo_alerta,
    ).first() is not None


def _registrar_envio(db: Session, equipo_id: int, magnitud_id: int, tipo_alerta: str) -> None:
    import models
    db.add(models.HistorialAlertas(
        equipo_id=equipo_id,
        magnitud_id=magnitud_id,
        tipo_alerta=tipo_alerta,
    ))
    db.commit()


def _meta_para_tipo(tipo: str, dias: int) -> dict:
    """Devuelve asunto, color de badge y texto de encabezado según urgencia."""
    if tipo.startswith("antes_"):
        return {
            "emoji":    "⚠️",
            "prefijo":  "Proximo a vencer",
            "color":    "#dc2626" if dias >= -7 else "#d97706",
            "bg":       "#fef2f2" if dias >= -7 else "#fffbeb",
            "etiqueta": f"Vence en {abs(dias)} dia{'s' if abs(dias) != 1 else ''}",
        }
    if tipo == "dia_0":
        return {
            "emoji":    "🔴",
            "prefijo":  "Vence HOY",
            "color":    "#dc2626",
            "bg":       "#fef2f2",
            "etiqueta": "Vence HOY",
        }
    # despues_*
    return {
        "emoji":    "❌",
        "prefijo":  "VENCIDO",
        "color":    "#7f1d1d",
        "bg":       "#fef2f2",
        "etiqueta": f"Vencido hace {abs(dias)} dia{'s' if abs(dias) != 1 else ''}",
    }


def _construir_html(equipos: list[dict], hoy: date, tipo_global: str, dias_global: int) -> str:
    meta = _meta_para_tipo(tipo_global, dias_global)

    filas = ""
    for eq in equipos:
        dias = eq["dias"]
        meta_fila = _meta_para_tipo(eq["tipo_alerta"], dias)
        filas += f"""
        <tr>
          <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;
                     font-weight:600;color:#1e293b;">{eq['nombre']}</td>
          <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;
                     color:#64748b;font-family:monospace;">{eq['codigo']}</td>
          <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;
                     color:#374151;">{eq['magnitud']}</td>
          <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;
                     color:#374151;">{eq['proxima_calibracion'].strftime('%d/%m/%Y')}</td>
          <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;text-align:center;">
            <span style="background:{meta_fila['bg']};color:{meta_fila['color']};
                         font-weight:700;padding:4px 12px;border-radius:20px;font-size:13px;">
              {meta_fila['etiqueta']}
            </span>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#f1f5f9;padding:32px 16px;">
  <tr><td align="center">
    <table width="680" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:12px;
                  box-shadow:0 4px 20px rgba(0,0,0,0.08);overflow:hidden;">

      <tr>
        <td style="background:linear-gradient(135deg,#1a4f8a,#0f3460);
                   padding:28px 32px;">
          <div style="font-size:22px;font-weight:800;color:#ffffff;">MetroGest</div>
          <div style="font-size:13px;color:rgba(255,255,255,0.7);margin-top:2px;">
            Sistema de Gestion Metrologica
          </div>
        </td>
      </tr>

      <tr>
        <td style="padding:28px 32px 8px;">
          <div style="background:{meta['bg']};border-left:4px solid {meta['color']};
                      border-radius:8px;padding:14px 18px;margin-bottom:20px;">
            <span style="font-size:15px;font-weight:700;color:{meta['color']};">
              {meta['emoji']} Calibracion — {meta['prefijo']}
            </span>
          </div>
          <p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 20px;">
            Reporte del <strong>{hoy.strftime('%d/%m/%Y')}</strong>.
            Los equipos a continuacion requieren atencion en sus proximas calibraciones.
          </p>
        </td>
      </tr>

      <tr>
        <td style="padding:0 32px 28px;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #e2e8f0;border-radius:8px;
                        overflow:hidden;font-size:13px;">
            <thead>
              <tr style="background:#f8fafc;">
                <th style="padding:11px 16px;text-align:left;font-size:11px;
                           text-transform:uppercase;letter-spacing:0.8px;
                           color:#64748b;font-weight:700;border-bottom:2px solid #e2e8f0;">
                  Equipo</th>
                <th style="padding:11px 16px;text-align:left;font-size:11px;
                           text-transform:uppercase;letter-spacing:0.8px;
                           color:#64748b;font-weight:700;border-bottom:2px solid #e2e8f0;">
                  Codigo</th>
                <th style="padding:11px 16px;text-align:left;font-size:11px;
                           text-transform:uppercase;letter-spacing:0.8px;
                           color:#64748b;font-weight:700;border-bottom:2px solid #e2e8f0;">
                  Magnitud</th>
                <th style="padding:11px 16px;text-align:left;font-size:11px;
                           text-transform:uppercase;letter-spacing:0.8px;
                           color:#64748b;font-weight:700;border-bottom:2px solid #e2e8f0;">
                  Vence</th>
                <th style="padding:11px 16px;text-align:center;font-size:11px;
                           text-transform:uppercase;letter-spacing:0.8px;
                           color:#64748b;font-weight:700;border-bottom:2px solid #e2e8f0;">
                  Estado</th>
              </tr>
            </thead>
            <tbody>{filas}</tbody>
          </table>
        </td>
      </tr>

      <tr>
        <td style="background:#f8fafc;border-top:1px solid #e2e8f0;
                   padding:20px 32px;text-align:center;">
          <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.6;">
            Mensaje generado automaticamente por MetroGest.<br>
            Por favor no respondas a este correo.
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def _get_cfg_notif(db: Session):
    """Devuelve ConfigNotificaciones desde BD, o None si no existe el modelo."""
    try:
        import models
        return db.query(models.ConfigNotificaciones).first()
    except Exception:
        return None


def verificar_calibraciones_por_vencer(db: Session) -> None:
    """
    Revisa calibraciones activas y envía alertas en los intervalos:
    -30, -15, -7, -1, 0, +1, +7 días respecto al vencimiento.
    Solo envía si no se envió ya ese intervalo para ese equipo/magnitud.
    Lee email y toggles desde config_notificaciones (BD) o .env como fallback.
    """
    cfg_notif = _get_cfg_notif(db)
    destinatario = (
        (cfg_notif.email_destinatario if cfg_notif else None)
        or os.getenv("EMAIL_DESTINATARIO", "")
    ).strip()
    if not destinatario:
        logger.warning("Alertas calibracion: EMAIL_DESTINATARIO no configurado")
        return

    # Mapa tipo_alerta → campo Boolean en ConfigNotificaciones
    _toggle_campo = {
        "antes_30":   "alerta_antes_30",
        "antes_15":   "alerta_antes_15",
        "antes_7":    "alerta_antes_7",
        "antes_1":    "alerta_antes_1",
        "dia_0":      "alerta_dia_0",
        "despues_1":  "alerta_despues_1",
        "despues_7":  "alerta_despues_7",
    }

    def _tipo_activo(tipo: str) -> bool:
        if cfg_notif is None:
            return True
        return bool(getattr(cfg_notif, _toggle_campo.get(tipo, ""), True))

    import models
    hoy = date.today()

    # Rango de búsqueda: desde 30 días antes hasta 7 días después
    desde  = hoy + timedelta(days=min(INTERVALOS.values()))   # hoy - 30
    hasta  = hoy + timedelta(days=max(INTERVALOS.values()))   # hoy + 7

    calibraciones = (
        db.query(models.Calibracion)
        .join(models.MagnitudEquipo,
              models.Calibracion.magnitud_id == models.MagnitudEquipo.id)
        .join(models.Equipo,
              models.MagnitudEquipo.equipo_id == models.Equipo.id)
        .filter(
            models.Calibracion.proxima_calibracion != None,
            models.Calibracion.proxima_calibracion >= desde,
            models.Calibracion.proxima_calibracion <= hasta,
            models.MagnitudEquipo.activa == True,
        )
        .order_by(models.Calibracion.proxima_calibracion)
        .all()
    )

    if not calibraciones:
        logger.info("Alertas calibracion: ninguna calibracion en ventana de alerta")
        return

    # Deduplicar por (equipo, magnitud) — quedarse con la calibracion mas reciente
    vistos: dict[tuple, models.Calibracion] = {}
    for cal in calibraciones:
        key = (cal.magnitud.equipo.id, cal.magnitud_id)
        if key not in vistos:
            vistos[key] = cal

    # Agrupar por tipo_alerta para enviar un email consolidado por intervalo
    por_tipo: dict[str, list[dict]] = {}

    for (eq_id, mag_id), cal in vistos.items():
        dias = (cal.proxima_calibracion - hoy).days          # negativo si ya venció
        tipo = _tipo_alerta_para_dia(dias)
        if tipo is None:
            continue

        if not _tipo_activo(tipo):
            logger.info("Alerta '%s' desactivada en configuracion — omitiendo", tipo)
            continue

        if _ya_enviada(db, eq_id, mag_id, tipo):
            logger.info("Alerta '%s' ya enviada para equipo_id=%d mag_id=%d — omitiendo",
                        tipo, eq_id, mag_id)
            continue

        eq  = cal.magnitud.equipo
        mag = cal.magnitud
        por_tipo.setdefault(tipo, []).append({
            "equipo_id":           eq_id,
            "magnitud_id":         mag_id,
            "nombre":              eq.nombre,
            "codigo":              eq.codigo,
            "magnitud":            mag.nombre,
            "proxima_calibracion": cal.proxima_calibracion,
            "dias":                dias,
            "tipo_alerta":         tipo,
        })

    if not por_tipo:
        logger.info("Alertas calibracion: todos los intervalos ya fueron notificados")
        return

    # Enviar un email por cada tipo de intervalo
    for tipo, equipos in por_tipo.items():
        total   = len(equipos)
        dias_ref = equipos[0]["dias"]
        meta    = _meta_para_tipo(tipo, dias_ref)

        if tipo.startswith("antes_"):
            asunto = (f"{meta['emoji']} MetroGest — {meta['prefijo']}: "
                      f"{total} equipo{'s' if total != 1 else ''} "
                      f"({abs(dias_ref)} dias)")
        elif tipo == "dia_0":
            asunto = (f"{meta['emoji']} MetroGest — {meta['prefijo']}: "
                      f"{total} equipo{'s' if total != 1 else ''}")
        else:
            asunto = (f"{meta['emoji']} MetroGest — {meta['prefijo']}: "
                      f"{total} equipo{'s' if total != 1 else ''}")

        html = _construir_html(equipos, hoy, tipo, dias_ref)
        ok   = send_email(destinatario, asunto, html)

        if ok:
            # Registrar envío para no repetirlo
            for eq in equipos:
                _registrar_envio(db, eq["equipo_id"], eq["magnitud_id"], tipo)
            logger.info("Alerta '%s' enviada a %s (%d equipos)", tipo, destinatario, total)
        else:
            logger.error("Alerta '%s': fallo el envio a %s", tipo, destinatario)


def verificar_licencia_por_vencer(db: Session = None) -> None:
    """
    Revisa si la licencia vence en los proximos 30 dias
    y envia un email de alerta al destinatario configurado en BD o .env.
    """
    cfg_notif = _get_cfg_notif(db) if db else None

    if cfg_notif is not None and not cfg_notif.alerta_licencia:
        logger.info("Alerta licencia: desactivada en configuracion — omitiendo")
        return

    destinatario = (
        (cfg_notif.email_destinatario if cfg_notif else None)
        or os.getenv("EMAIL_DESTINATARIO", "")
    ).strip()
    if not destinatario:
        logger.warning("Alerta licencia: EMAIL_DESTINATARIO no configurado")
        return

    import licencia as lic
    lic.invalidar_cache()
    datos = lic.info()

    if datos["sin_licencia"]:
        logger.info("Alerta licencia: no hay archivo de licencia — omitiendo alerta")
        return

    dias = datos.get("dias")
    if dias is None or dias > 30:
        logger.info("Alerta licencia: vence en %s dias — sin alerta", dias)
        return

    cliente = datos.get("cliente", "este sistema")
    fecha   = datos.get("vence", "fecha desconocida")
    hoy     = date.today()

    if dias <= 0:
        color_badge = "#dc2626"
        bg_badge    = "#fef2f2"
        estado_txt  = "VENCIDA"
        intro       = (f"La licencia de <strong>{cliente}</strong> "
                       f"<strong>vencio el {fecha}</strong>. "
                       f"El sistema esta en modo solo lectura.")
    elif dias <= 7:
        color_badge = "#dc2626"
        bg_badge    = "#fef2f2"
        estado_txt  = f"Vence en {dias} dia{'s' if dias != 1 else ''}"
        intro       = (f"La licencia de <strong>{cliente}</strong> vence el "
                       f"<strong>{fecha}</strong>. Renueva con urgencia.")
    else:
        color_badge = "#d97706"
        bg_badge    = "#fffbeb"
        estado_txt  = f"Vence en {dias} dias"
        intro       = (f"La licencia de <strong>{cliente}</strong> vence el "
                       f"<strong>{fecha}</strong>. Quedan {dias} dias para renovar.")

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#f1f5f9;padding:32px 16px;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:12px;
                  box-shadow:0 4px 20px rgba(0,0,0,0.08);overflow:hidden;">
      <tr>
        <td style="background:linear-gradient(135deg,#1a4f8a,#0f3460);padding:28px 32px;">
          <div style="font-size:22px;font-weight:800;color:#ffffff;">MetroGest</div>
          <div style="font-size:13px;color:rgba(255,255,255,0.7);margin-top:2px;">
            Sistema de Gestion Metrologica
          </div>
        </td>
      </tr>
      <tr>
        <td style="padding:32px;">
          <div style="background:{bg_badge};border-left:4px solid {color_badge};
                      border-radius:8px;padding:16px 20px;margin-bottom:24px;">
            <div style="font-size:16px;font-weight:700;color:{color_badge};">
              Licencia por vencer — {estado_txt}
            </div>
          </div>
          <p style="color:#374151;font-size:14px;line-height:1.8;margin:0 0 24px;">
            {intro}
          </p>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f8fafc;border:1px solid #e2e8f0;
                        border-radius:8px;overflow:hidden;font-size:13px;">
            <tr>
              <td style="padding:12px 18px;border-bottom:1px solid #e2e8f0;
                         color:#64748b;font-weight:600;">Cliente</td>
              <td style="padding:12px 18px;border-bottom:1px solid #e2e8f0;
                         color:#1e293b;font-weight:700;">{cliente}</td>
            </tr>
            <tr>
              <td style="padding:12px 18px;border-bottom:1px solid #e2e8f0;
                         color:#64748b;font-weight:600;">Fecha de vencimiento</td>
              <td style="padding:12px 18px;border-bottom:1px solid #e2e8f0;
                         color:#1e293b;">{fecha}</td>
            </tr>
            <tr>
              <td style="padding:12px 18px;color:#64748b;font-weight:600;">
                Dias restantes</td>
              <td style="padding:12px 18px;">
                <span style="background:{bg_badge};color:{color_badge};font-weight:700;
                             padding:3px 12px;border-radius:20px;">
                  {max(dias, 0)} dia{'s' if dias != 1 else ''}
                </span>
              </td>
            </tr>
          </table>
          <div style="margin-top:28px;padding:18px 20px;background:#eff6ff;
                      border-radius:8px;font-size:13px;color:#1e40af;">
            Para renovar tu licencia contacta a soporte MetroGest:<br>
            contacto@metrogest.com.co &nbsp;|&nbsp; WhatsApp +57 316 752 7686
          </div>
        </td>
      </tr>
      <tr>
        <td style="background:#f8fafc;border-top:1px solid #e2e8f0;
                   padding:18px 32px;text-align:center;">
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            Reporte del {hoy.strftime('%d/%m/%Y')} — mensaje automatico, no responder.
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""

    if dias <= 0:
        asunto = f"MetroGest — Licencia VENCIDA ({cliente})"
    else:
        asunto = f"MetroGest — Licencia vence en {dias} dias ({cliente})"

    ok = send_email(destinatario, asunto, html)
    if ok:
        logger.info("Alerta licencia enviada a %s (%d dias restantes)", destinatario, dias)
    else:
        logger.error("Alerta licencia: fallo el envio a %s", destinatario)
