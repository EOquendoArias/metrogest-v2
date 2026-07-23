"""
Recuperación de acceso — genera una contraseña temporal para un administrador.

Reemplaza el backdoor MASTER_KEY (eliminado): antes, cualquiera con esa clave
podía entrar por la pantalla de login como cualquier administrador, sin dejar
rastro. Este script exige en cambio acceso directo al servidor (shell/RDP),
que es un control mucho más fuerte, y la contraseña generada obliga a
cambiarla en el primer login (igual que un usuario nuevo).

Uso:
    python resetear_password_admin.py admin@metrogest.com
"""
import sys

import auth
import models
from database import SessionLocal


def main():
    if len(sys.argv) != 2:
        print("Uso: python resetear_password_admin.py <email>")
        sys.exit(1)

    email = sys.argv[1]
    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(
            models.Usuario.email == email, models.Usuario.activo == True
        ).first()
        if not usuario:
            print(f"No se encontró un usuario activo con el correo: {email}")
            sys.exit(1)

        temp = auth.generar_password_temporal()
        usuario.hashed_password = auth.hash_password(temp)
        usuario.debe_cambiar_password = True
        db.commit()

        print(f"\nContraseña temporal para {email}: {temp}")
        print("Se le pedirá cambiarla en el próximo login.")
        print("Registra este evento (quién, cuándo, por qué) fuera del sistema — no queda auditado aquí todavía.\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
