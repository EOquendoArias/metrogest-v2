"""
Rate-limiting de login: el bloqueo debe ser por (email, ip) y también
por ip global — no solo por email (eso permitía que cualquiera bloqueara
la cuenta de otra persona sabiendo solo su correo). Ver auth.py.
"""
import auth


def test_login_correcto_no_incrementa_intentos(db):
    ok, _ = auth.esta_bloqueado("nadie@test.com", "1.1.1.1", db)
    assert ok is False


def test_bloqueo_por_cuenta_no_afecta_a_otra_ip(db):
    email = "victima@test.com"
    ip_atacante = "1.2.3.4"
    ip_victima = "9.9.9.9"

    for _ in range(auth.MAX_INTENTOS_CUENTA):
        auth.registrar_fallo(email, ip_atacante, db)

    bloqueado_atacante, _ = auth.esta_bloqueado(email, ip_atacante, db)
    bloqueado_victima, _ = auth.esta_bloqueado(email, ip_victima, db)

    assert bloqueado_atacante is True
    assert bloqueado_victima is False, (
        "La víctima no debería quedar bloqueada desde su propia IP solo "
        "porque alguien más falló el login para su cuenta desde otro lado."
    )


def test_bloqueo_se_activa_justo_en_el_limite(db):
    email = "cuenta2@test.com"
    ip = "2.2.2.2"
    for i in range(auth.MAX_INTENTOS_CUENTA - 1):
        bloqueado_ahora, _ = auth.registrar_fallo(email, ip, db)
        assert bloqueado_ahora is False, f"no debería bloquear en el intento {i + 1}"
    bloqueado_ahora, _ = auth.registrar_fallo(email, ip, db)
    assert bloqueado_ahora is True


def test_login_exitoso_resetea_el_contador_de_esa_cuenta(db):
    email = "cuenta3@test.com"
    ip = "3.3.3.3"
    auth.registrar_fallo(email, ip, db)
    auth.registrar_fallo(email, ip, db)
    auth.resetear_intentos(email, ip, db)
    bloqueado, _ = auth.esta_bloqueado(email, ip, db)
    assert bloqueado is False


def test_ip_que_prueba_muchas_cuentas_queda_bloqueada_globalmente(db):
    ip_spray = "6.6.6.6"
    for i in range(auth.MAX_INTENTOS_IP):
        bloqueado_ahora, _ = auth.registrar_fallo(f"cuenta_falsa_{i}@test.com", ip_spray, db)
    assert bloqueado_ahora is True

    # Una cuenta nueva, nunca antes intentada desde esa IP, también debe bloquear.
    bloqueado, _ = auth.esta_bloqueado("cuenta_nunca_intentada@test.com", ip_spray, db)
    assert bloqueado is True


def test_hash_password_no_es_texto_plano_y_se_verifica_bien():
    hashed = auth.hash_password("MiClaveSegura123")
    assert hashed != "MiClaveSegura123"
    assert auth.verificar_password("MiClaveSegura123", hashed) is True
    assert auth.verificar_password("otra-clave", hashed) is False
