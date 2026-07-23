"""
MetroGest — Sistema de licencias
=================================
Genera licencias:
    python licencia.py generar "Empresa ABC" 2026-12-31
    python licencia.py generar "Empresa ABC" 2026-12-31 avanzado_ilac

Verifica:
    python licencia.py verificar
"""
import json, hmac, hashlib, sys, base64 as _b64
from datetime import date
from pathlib import Path

# ─── SECRETO DEL PROVEEDOR — NO modificar ─────────────────────────────────────
_S = b"TWV0cm9HZXN0I1Byb3ZlZWRvciMyMDI0I0xpY2VuY2lhU2VjcmV0YSNOb0NvbXBhcnRpcg=="
_SECRETO = _b64.b64decode(_S).decode()
_ARCHIVO = Path(__file__).parent / "licencia.json"

_cache = None


def _firmar(datos: dict) -> str:
    modulos_str = ','.join(sorted(datos.get('modulos', [])))
    contenido = f"{datos['cliente']}|{modulos_str}|{datos['vence']}"
    return hmac.new(_SECRETO.encode(), contenido.encode(), hashlib.sha256).hexdigest()


def generar_licencia(cliente: str, fecha_vence: str, modulos: list = None) -> dict:
    modulos = modulos or []
    datos = {"cliente": cliente, "modulos": modulos,
             "vence": fecha_vence, "generada": date.today().isoformat()}
    datos["firma"] = _firmar(datos)
    return datos


def guardar_licencia(cliente: str, fecha_vence: str, modulos: list = None,
                     ruta: str = None) -> str:
    lic = generar_licencia(cliente, fecha_vence, modulos or [])
    p = Path(ruta) if ruta else Path(f"licencia_{cliente.replace(' ','_')}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(lic, f, indent=2, ensure_ascii=False)
    return str(p)


def _cargar() -> dict | None:
    global _cache
    if _cache is not None:
        return _cache
    if not _ARCHIVO.exists():
        return None
    try:
        with open(_ARCHIVO, encoding="utf-8") as f:
            datos = json.load(f)
        for campo in ("cliente", "modulos", "vence", "firma"):
            if campo not in datos:
                return None
        firma_ok = hmac.compare_digest(datos["firma"], _firmar(datos))
        if not firma_ok:
            print("  [Licencia] [!] Firma inválida")
            return None
        vence = date.fromisoformat(datos["vence"])
        datos["_vencida"] = vence < date.today()
        datos["_dias_restantes"] = (vence - date.today()).days
        _cache = datos
        return datos
    except Exception as e:
        print(f"  [Licencia] Error: {e}")
        return None


def esta_activa() -> bool:
    """Licencia válida y no vencida."""
    lic = _cargar()
    return lic is not None and not lic.get("_vencida", True)


def esta_vencida() -> bool:
    """Licencia existe pero está vencida — modo solo lectura."""
    lic = _cargar()
    return lic is not None and lic.get("_vencida", False)


def sin_licencia() -> bool:
    """No hay archivo de licencia."""
    return _cargar() is None


def tiene_modulo(modulo: str) -> bool:
    """Módulo premium activo (requiere licencia vigente)."""
    if not esta_activa():
        return False
    lic = _cargar()
    return modulo in lic.get("modulos", [])


def puede_escribir() -> bool:
    """True si puede agregar/editar datos (licencia activa o en gracia)."""
    return esta_activa()


def info() -> dict:
    lic = _cargar()
    if not lic:
        return {"activa": False, "vencida": False, "sin_licencia": True,
                "cliente": None, "modulos": [], "vence": None, "dias": None}
    return {
        "activa": not lic.get("_vencida", True),
        "vencida": lic.get("_vencida", False),
        "sin_licencia": False,
        "cliente": lic["cliente"],
        "modulos": lic.get("modulos", []),
        "vence": lic["vence"],
        "dias": lic.get("_dias_restantes"),
    }


def invalidar_cache():
    global _cache
    _cache = None


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print('  python licencia.py generar "Empresa ABC" 2026-12-31')
        print('  python licencia.py generar "Empresa ABC" 2026-12-31 avanzado_ilac')
        print('  python licencia.py verificar')
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "generar":
        if len(sys.argv) < 4:
            print("Uso: python licencia.py generar <cliente> <fecha_vence> [modulo,...]")
            sys.exit(1)
        cliente     = sys.argv[2]
        fecha_vence = sys.argv[3]
        modulos     = sys.argv[4].split(",") if len(sys.argv) > 4 else []
        try:
            date.fromisoformat(fecha_vence)
        except ValueError:
            print(f"Fecha inválida: {fecha_vence}. Formato: YYYY-MM-DD")
            sys.exit(1)
        ruta = guardar_licencia(cliente, fecha_vence, modulos)
        print(f"\n[OK] Licencia generada: {ruta}")
        print(f"  Cliente : {cliente}")
        print(f"  Módulos : {modulos or ['básico']}")
        print(f"  Vence   : {fecha_vence}")
        print(f"\nEnvía '{ruta}' al cliente — debe copiarlo como 'licencia.json'")

    elif cmd == "verificar":
        invalidar_cache()
        i = info()
        if i["sin_licencia"]:
            print("\n[X] Sin licencia — modo solo lectura activo")
        elif i["activa"]:
            print(f"\n[OK] Licencia activa · {i['dias']} días restantes")
            print(f"  Cliente: {i['cliente']} · Vence: {i['vence']}")
            print(f"  Módulos: {i['modulos'] or ['básico']}")
        else:
            print(f"\n[!] Licencia vencida el {i['vence']} — modo solo lectura")
    else:
        print(f"Comando desconocido: {cmd}")
