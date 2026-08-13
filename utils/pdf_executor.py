"""
Pool de procesos compartido para generación de PDF/Excel (ver ADR-001 en
docs/arquitectura/DECISIONES.md). ReportLab/openpyxl consumen CPU real; con
un solo proceso Python, generar un documento acapara el GIL y bloquea a
todos los demás usuarios mientras dura. Mandar la generación a un proceso
hijo libera al proceso principal para seguir atendiendo al resto.

Los routers deben pasar solo datos ya "snapshoteados" (ver
utils/orm_snapshot.py) — nunca objetos ORM vivos atados a una Session.

Uso típico en un router:

    from utils.pdf_executor import pool
    from utils.orm_snapshot import snapshot
    import asyncio

    @router.get("/{cid}/pdf")
    async def pdf(cid: int, ...):
        ...  # cargar y tocar relaciones necesarias mientras la sesión sigue abierta
        cal_snap = snapshot(cal)
        loop = asyncio.get_running_loop()
        pdf_bytes = await loop.run_in_executor(pool, generar_pdf_analisis, cal_snap, ...)
"""
import os
from concurrent.futures import ProcessPoolExecutor

# Pocos workers a propósito: son tareas pesadas de CPU (una por click de
# usuario), no un pool de alta concurrencia — 2 alcanza para que un PDF y un
# Excel no se bloqueen entre sí sin disparar el uso de RAM. Configurable por
# si el servidor del cliente tiene más núcleos disponibles.
_MAX_WORKERS = int(os.getenv("PDF_EXECUTOR_WORKERS", "2"))

pool = ProcessPoolExecutor(max_workers=_MAX_WORKERS)
