from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth

router = APIRouter()
T = Jinja2Templates(directory="templates")


def _get_config(db: Session) -> models.ConfigNotificaciones:
    cfg = db.query(models.ConfigNotificaciones).first()
    if not cfg:
        cfg = models.ConfigNotificaciones()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("/", response_class=HTMLResponse)
def config_page(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")
    cfg = _get_config(db)
    return T.TemplateResponse(request, "notificaciones/config.html", {
        "usuario_actual": u,
        "cfg": cfg,
        "ok":    request.query_params.get("ok"),
        "error": request.query_params.get("error"),
    })


@router.post("/guardar")
async def guardar(
    request: Request,
    email_destinatario: str = Form(""),
    alerta_antes_30:  str = Form(None),
    alerta_antes_15:  str = Form(None),
    alerta_antes_7:   str = Form(None),
    alerta_antes_1:   str = Form(None),
    alerta_dia_0:     str = Form(None),
    alerta_despues_1: str = Form(None),
    alerta_despues_7: str = Form(None),
    alerta_licencia:  str = Form(None),
    db: Session = Depends(get_db),
):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")

    cfg = _get_config(db)
    cfg.email_destinatario = email_destinatario.strip() or None
    cfg.alerta_antes_30    = alerta_antes_30  is not None
    cfg.alerta_antes_15    = alerta_antes_15  is not None
    cfg.alerta_antes_7     = alerta_antes_7   is not None
    cfg.alerta_antes_1     = alerta_antes_1   is not None
    cfg.alerta_dia_0       = alerta_dia_0     is not None
    cfg.alerta_despues_1   = alerta_despues_1 is not None
    cfg.alerta_despues_7   = alerta_despues_7 is not None
    cfg.alerta_licencia    = alerta_licencia  is not None

    from sqlalchemy.sql import func
    cfg.updated_at = func.now()
    db.commit()

    return RedirectResponse(url="/notificaciones/?ok=1", status_code=302)


@router.post("/prueba", response_class=JSONResponse)
async def envio_prueba(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return JSONResponse({"ok": False, "msg": "Sin permiso"}, status_code=403)

    # Acepta email desde JSON body (campo "email") o desde la config guardada
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    cfg = _get_config(db)
    destinatario = (body.get("email") or cfg.email_destinatario or "").strip()
    if not destinatario:
        return JSONResponse({"ok": False, "msg": "No hay email destinatario configurado."})

    from utils.email_sender import send_email
    from datetime import date

    hoy = date.today().strftime("%d/%m/%Y")
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px;">
  <tr><td align="center">
    <table width="520" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:12px;
                  box-shadow:0 4px 20px rgba(0,0,0,0.08);overflow:hidden;">
      <tr>
        <td style="background:linear-gradient(135deg,#1a4f8a,#0f3460);padding:28px 32px;">
          <div style="font-size:22px;font-weight:800;color:#fff;">MetroGest</div>
          <div style="font-size:13px;color:rgba(255,255,255,0.7);margin-top:2px;">
            Sistema de Gestion Metrologica
          </div>
        </td>
      </tr>
      <tr>
        <td style="padding:32px;">
          <div style="background:#f0fdf4;border-left:4px solid #22c55e;
                      border-radius:8px;padding:16px 20px;margin-bottom:24px;">
            <div style="font-size:16px;font-weight:700;color:#15803d;">
              Prueba de conexion exitosa
            </div>
          </div>
          <p style="color:#374151;font-size:14px;line-height:1.8;margin:0 0 20px;">
            Este es un mensaje de prueba enviado desde la pantalla de
            <strong>Configuracion de Notificaciones</strong> de MetroGest.<br><br>
            Si recibes este correo, la configuracion SMTP esta funcionando correctamente
            y las alertas automaticas se enviaran a esta direccion.
          </p>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f8fafc;border:1px solid #e2e8f0;
                        border-radius:8px;font-size:13px;overflow:hidden;">
            <tr>
              <td style="padding:12px 18px;border-bottom:1px solid #e2e8f0;
                         color:#64748b;font-weight:600;">Enviado el</td>
              <td style="padding:12px 18px;border-bottom:1px solid #e2e8f0;
                         color:#1e293b;">{hoy}</td>
            </tr>
            <tr>
              <td style="padding:12px 18px;color:#64748b;font-weight:600;">
                Enviado por</td>
              <td style="padding:12px 18px;color:#1e293b;">{u.nombre}</td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="background:#f8fafc;border-top:1px solid #e2e8f0;
                   padding:18px 32px;text-align:center;">
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            Mensaje de prueba — MetroGest v2
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""

    ok = send_email(destinatario, "MetroGest — Prueba de configuracion SMTP", html)
    if ok:
        return JSONResponse({"ok": True,
                             "msg": f"Email de prueba enviado correctamente a {destinatario}"})
    return JSONResponse({"ok": False,
                         "msg": "No se pudo enviar el email. Revisa la configuracion SMTP en el archivo .env."})
