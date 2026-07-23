"""
Validación de archivos subidos por el usuario: extensión + contenido real
(magic bytes) + tamaño máximo. Antes, cada endpoint solo tomaba
os.path.splitext(archivo.filename)[1] y guardaba el archivo tal cual, sin
verificar que el contenido coincidiera con esa extensión ni límite de
tamaño — la puerta clásica para subir un .html/.svg con script embebido
disfrazado de imagen o certificado (XSS almacenado).
"""
import os

from fastapi import HTTPException, UploadFile

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}
EXTENSIONES_DOCUMENTO = {".pdf"}

MAX_TAMANO_IMAGEN_BYTES = 5 * 1024 * 1024      # 5 MB
MAX_TAMANO_DOCUMENTO_BYTES = 15 * 1024 * 1024  # 15 MB

_FIRMAS = {
    ".jpg":  (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png":  (b"\x89PNG\r\n\x1a\n",),
    ".pdf":  (b"%PDF-",),
}


def _extension_valida(nombre: str, permitidas: set) -> str:
    ext = os.path.splitext(nombre or "")[1].lower()
    if ext not in permitidas:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido ({ext or 'sin extensión'}). "
                   f"Permitidos: {', '.join(sorted(permitidas))}",
        )
    return ext


def _contenido_coincide(cabecera: bytes, ext: str) -> bool:
    if ext == ".webp":
        return cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP"
    return any(cabecera.startswith(firma) for firma in _FIRMAS.get(ext, ()))


def guardar_archivo_validado(archivo: UploadFile, destino_sin_extension: str,
                              permitidas: set, max_bytes: int) -> str:
    """
    Valida extensión + firma binaria + tamaño máximo, y solo entonces guarda
    el archivo en `destino_sin_extension + <extensión validada>`. Lanza
    HTTPException(400) si algo no cumple — nunca escribe un archivo que no
    pasó la validación. El caller nunca decide la extensión por su cuenta:
    la recibe de vuelta ya validada, para que el nombre del archivo en disco
    coincida siempre con lo que de verdad se comprobó.

    Devuelve la ruta final donde quedó guardado el archivo.
    """
    ext = _extension_valida(archivo.filename, permitidas)

    cabecera = archivo.file.read(16)
    archivo.file.seek(0)
    if not _contenido_coincide(cabecera, ext):
        raise HTTPException(
            status_code=400,
            detail="El contenido del archivo no coincide con su extensión.",
        )

    destino = f"{destino_sin_extension}{ext}"
    total = 0
    try:
        with open(destino, "wb") as f:
            while True:
                chunk = archivo.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=f"El archivo supera el tamaño máximo permitido "
                               f"({max_bytes // (1024 * 1024)} MB).",
                    )
                f.write(chunk)
    except HTTPException:
        if os.path.exists(destino):
            os.remove(destino)
        raise
    return destino
