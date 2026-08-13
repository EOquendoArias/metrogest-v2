import asyncio
import io
from datetime import date
from functools import partial
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
import utils.firma_electronica as firma
from utils.calculos import calcular_regresiones
from utils.orm_snapshot import snapshot
from utils.pdf_executor import pool as _pdf_pool
import services.analisis_service as svc

router = APIRouter()
T = Jinja2Templates(directory="templates")


# ── PÁGINA PRINCIPAL DE ANÁLISIS ──────────────────────────────────────────────

@router.get("/{cid}", response_class=HTMLResponse)
def analisis_page(cid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    cal = svc.obtener_calibracion(db, cid)
    if not cal: raise HTTPException(status_code=404)

    datos = svc.datos_pagina_analisis(db, cal)

    return T.TemplateResponse(request, "analisis/analisis.html", {
        "usuario_actual":      u,
        "calibracion":         cal,
        "error_firma":         request.query_params.get("error_firma"),
        "significado_aprobar": firma.SIGNIFICADOS["aprobar_calibracion"],
        **datos,
    })


# ── TOGGLE INCERTIDUMBRE ──────────────────────────────────────────────────────

@router.post("/{cid}/toggle-incertidumbre")
def toggle_incertidumbre(cid: int, request: Request,
                          usar: str = Form("true"), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/analisis/{cid}", status_code=303)
    cal = svc.obtener_calibracion(db, cid)
    svc.toggle_incertidumbre(db, cal, usar == "true")
    return RedirectResponse(url=f"/analisis/{cid}", status_code=303)


# ── SELECCIONAR MÉTODO DE ANÁLISIS ────────────────────────────────────────────

@router.post("/{cid}/metodo")
def sel_metodo(cid: int, request: Request,
               metodo: str = Form("regresion"), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/analisis/{cid}", status_code=303)
    cal = svc.obtener_calibracion(db, cid)
    svc.seleccionar_metodo(db, cal, metodo)
    return RedirectResponse(url=f"/analisis/{cid}", status_code=303)


# ── AGREGAR PUNTOS (en lote — una o varias filas en un solo envío) ────────────

@router.post("/{cid}/punto")
def agregar_punto(cid: int, request: Request,
    valor_patron: float = Form(...), valor_indicado: float = Form(...),
    incertidumbre: str = Form(""), tolerancia_inf: str = Form(""),
    tolerancia_sup: str = Form(""), emp_punto: str = Form(""),
    observacion: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/analisis/{cid}", status_code=303)
    cal = svc.obtener_calibracion(db, cid)
    if not cal: raise HTTPException(status_code=404)
    svc.agregar_punto(db, cal, valor_patron, valor_indicado,
                       incertidumbre, tolerancia_inf, tolerancia_sup,
                       emp_punto, observacion)
    return RedirectResponse(url=f"/analisis/{cid}", status_code=303)


@router.post("/{cid}/puntos/lote")
def agregar_puntos_lote(cid: int, request: Request,
    valor_patron: list[str] = Form([]), valor_indicado: list[str] = Form([]),
    incertidumbre: list[str] = Form([]), tolerancia_inf: list[str] = Form([]),
    tolerancia_sup: list[str] = Form([]), emp_punto: list[str] = Form([]),
    observacion: list[str] = Form([]), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/analisis/{cid}", status_code=303)
    cal = svc.obtener_calibracion(db, cid)
    if not cal: raise HTTPException(status_code=404)
    svc.agregar_puntos_lote(db, cal, valor_patron, valor_indicado, incertidumbre,
                             tolerancia_inf, tolerancia_sup, emp_punto, observacion)
    return RedirectResponse(url=f"/analisis/{cid}", status_code=303)


# ── ELIMINAR PUNTO ────────────────────────────────────────────────────────────

@router.post("/{cid}/punto/{pid}/eliminar")
def eliminar_punto(cid: int, pid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/analisis/{cid}", status_code=303)
    svc.eliminar_punto(db, cid, pid, u.id)
    return RedirectResponse(url=f"/analisis/{cid}", status_code=303)


# ── SELECCIONAR REGRESIÓN ─────────────────────────────────────────────────────

@router.post("/{cid}/regresion")
def sel_regresion(cid: int, request: Request,
                   grado: int = Form(...), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/analisis/{cid}", status_code=303)
    cal = svc.obtener_calibracion(db, cid)
    svc.seleccionar_regresion(db, cal, grado)
    return RedirectResponse(url=f"/analisis/{cid}", status_code=303)


# ── APROBAR ───────────────────────────────────────────────────────────────────

@router.post("/{cid}/aprobar")
def aprobar(cid: int, request: Request,
            obs_aprobacion: str = Form(""), password: str = Form(""),
            db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/analisis/{cid}", status_code=303)
    cal = svc.obtener_calibracion(db, cid)
    if not cal: raise HTTPException(status_code=404)

    ok, error = svc.aprobar_calibracion(db, request, u, cal, obs_aprobacion, password)
    if not ok:
        return RedirectResponse(url=f"/analisis/{cid}?error_firma=1", status_code=303)
    return RedirectResponse(url=f"/analisis/{cid}", status_code=303)


# ── PDF ───────────────────────────────────────────────────────────────────────

@router.get("/{cid}/pdf")
async def pdf(cid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    cal = svc.obtener_calibracion(db, cid)
    if not cal: raise HTTPException(status_code=404)
    regs = calcular_regresiones(cal.puntos) if len(cal.puntos) >= 2 else []
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    usar_u = cal.usar_incertidumbre if hasattr(cal, "usar_incertidumbre") else True

    # Tocar (mientras la sesión sigue abierta) todas las relaciones que
    # utils/pdf_analisis.py navega, para que snapshot() las encuentre ya
    # cargadas — ver ADR-001 y utils/orm_snapshot.py.
    mag = cal.magnitud
    _ = mag.equipo if mag else None
    _ = mag.config_ilac if mag else None
    _ = cal.aprobado_por

    from utils.pdf_analisis import generar_pdf_analisis
    cal_snap = snapshot(cal)
    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(
        _pdf_pool,
        partial(generar_pdf_analisis, cal_snap, cal_snap.puntos, regs,
                cal.grado_regresion_sel, snapshot(u), snapshot(config), usar_u),
    )
    nombre = f"analisis_{cal.numero_certificado or cid}_{date.today().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})
