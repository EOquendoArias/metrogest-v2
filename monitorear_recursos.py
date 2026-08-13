"""
monitorear_recursos.py — Monitoreo de memoria/CPU para PQ-6 (Fase 2.3)
========================================================================
Ver docs/calidad/PLAN_PRUEBAS_CARGA.md §7 y
docs/calidad/validacion_farma/PQ_CALIFICACION_DESEMPENO.md §3 (PQ-6).

Muestrea cada N segundos la memoria (RSS) y CPU% del proceso padre de
Uvicorn y de todos sus workers hijos, y los escribe a un CSV. Al final se
revisa si el RSS total creció de forma acotada (normal, por caché/buffers
que se estabilizan) o sin límite (fuga de memoria real).

Uso — en una TERCERA ventana de terminal, con el servidor de carga (puerto
8001, --workers 4) YA corriendo:

    venv\\Scripts\\activate
    python monitorear_recursos.py [duracion_min] [intervalo_seg] [archivo_salida.csv]

    # Ejemplo para la corrida sostenida de 25 minutos, muestreando cada 15s:
    python monitorear_recursos.py 25 15 monitoreo_pq6.csv

No toca la base de datos ni el servidor -- solo lee metadatos de procesos
del sistema operativo (memoria/CPU), vía psutil.
"""
import csv
import datetime
import sys
import time

import psutil


def encontrar_proceso_padre():
    """Busca el proceso de Uvicorn escuchando en el puerto 8001 y devuelve
    el padre de la familia (el que lanzó los --workers, no uno de ellos)."""
    candidatos = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = p.info["cmdline"] or []
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        texto = " ".join(cmdline)
        if "uvicorn" in texto and "8001" in texto:
            candidatos.append(p)

    if not candidatos:
        sys.exit(
            "[ERROR] No se encontró ningún proceso de uvicorn escuchando en "
            "el puerto 8001. ¿Está corriendo el servidor de carga?"
        )

    pids = {p.pid for p in candidatos}
    for p in candidatos:
        try:
            if p.ppid() not in pids:
                return p
        except psutil.NoSuchProcess:
            continue
    return candidatos[0]


def main():
    duracion_min = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    intervalo_seg = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    salida = sys.argv[3] if len(sys.argv) > 3 else "monitoreo_recursos.csv"

    padre = encontrar_proceso_padre()
    print(f">>> Proceso padre detectado: PID {padre.pid}")
    print(f">>> Muestreando cada {intervalo_seg}s durante {duracion_min} minutos "
          f"-> {salida}")

    # Primera llamada a cpu_percent() siempre da 0.0 (necesita un intervalo
    # de referencia) -- se descarta antes de empezar a registrar en serio.
    procesos_iniciales = [padre] + padre.children(recursive=True)
    for p in procesos_iniciales:
        try:
            p.cpu_percent(None)
        except psutil.NoSuchProcess:
            pass

    fin = time.time() + duracion_min * 60
    muestra = 0

    with open(salida, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "pid", "rol", "rss_mb", "cpu_percent"])

        while time.time() < fin:
            time.sleep(intervalo_seg)
            muestra += 1
            ts = datetime.datetime.now().isoformat(timespec="seconds")

            try:
                hijos = padre.children(recursive=True)
            except psutil.NoSuchProcess:
                print("[ADVERTENCIA] El proceso padre ya no existe -- "
                      "¿se cerró el servidor? Deteniendo el monitoreo.")
                break

            total_rss_mb = 0.0
            procesos = [("padre", padre)] + [("worker", h) for h in hijos]
            for rol, p in procesos:
                try:
                    rss_mb = p.memory_info().rss / (1024 * 1024)
                    cpu = p.cpu_percent(None)
                except psutil.NoSuchProcess:
                    continue
                total_rss_mb += rss_mb
                writer.writerow([ts, p.pid, rol, f"{rss_mb:.1f}", f"{cpu:.1f}"])
            f.flush()

            print(f"[{ts}] muestra {muestra}: {len(procesos)} procesos vivos, "
                  f"RSS total = {total_rss_mb:.1f} MB")

    print(f">>> Monitoreo terminado. Resultados en {salida}")


if __name__ == "__main__":
    main()
