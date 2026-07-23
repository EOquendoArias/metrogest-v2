"""Smoke test de la infraestructura misma: confirma que la fixture `db`
aísla correctamente los tests entre sí, incluso cuando el código bajo
prueba llama a db.commit() (como hace casi toda la app)."""
import models


def test_commit_no_se_filtra_al_siguiente_test_1(db):
    assert db.query(models.Usuario).count() == 0
    u = models.Usuario(nombre="Test", email="infra1@test.com",
                        hashed_password="x", rol="operador")
    db.add(u)
    db.commit()  # como hace la app de verdad
    assert db.query(models.Usuario).count() == 1


def test_commit_no_se_filtra_al_siguiente_test_2(db):
    # Si el aislamiento funcionara mal, aquí ya habría 1 fila del test anterior.
    assert db.query(models.Usuario).count() == 0
