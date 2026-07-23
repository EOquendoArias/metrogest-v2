"""Funciones puras de cálculo metrológico — no necesitan base de datos."""
from types import SimpleNamespace

from utils.calculos import calcular_intervalo_inicial, calcular_regresiones, calcular_semaforo


class TestCalcularSemaforo:
    def test_dentro_de_tolerancia_con_incertidumbre(self):
        # |error| + U <= EMP -> 0.5 + 0.2 = 0.7 <= 1.0
        assert calcular_semaforo(error=0.5, incertidumbre=0.2, emp=1.0) is True

    def test_fuera_de_tolerancia_con_incertidumbre(self):
        assert calcular_semaforo(error=0.9, incertidumbre=0.2, emp=1.0) is False

    def test_sin_incertidumbre_usa_solo_el_error(self):
        assert calcular_semaforo(error=0.9, incertidumbre=None, emp=1.0) is True

    def test_sin_emp_no_se_puede_evaluar(self):
        assert calcular_semaforo(error=0.1, incertidumbre=0.0, emp=None) is None

    def test_sin_error_no_se_puede_evaluar(self):
        assert calcular_semaforo(error=None, incertidumbre=0.0, emp=1.0) is None


class TestCalcularIntervaloInicial:
    def test_sin_factores_devuelve_12_por_defecto(self):
        assert calcular_intervalo_inicial([]) == 12

    def test_riesgo_muy_alto_da_3_meses(self):
        assert calcular_intervalo_inicial([1, 1, 1, 1]) == 3

    def test_riesgo_bajo_da_18_meses_tope(self):
        assert calcular_intervalo_inicial([5, 5, 5, 5]) == 18

    def test_riesgo_normal_da_12_meses(self):
        assert calcular_intervalo_inicial([3, 3, 3, 3]) == 12

    def test_recomendacion_fabricante_mas_corta_prevalece(self):
        # riesgo bajo (18 meses) pero el fabricante recomienda 6
        assert calcular_intervalo_inicial([5, 5, 5, 5], fabricante_meses=6) == 6

    def test_recomendacion_fabricante_mas_larga_no_extiende(self):
        # riesgo alto (6 meses) y el fabricante permite 24 -> no debe subir a 24
        assert calcular_intervalo_inicial([1.8, 1.8], fabricante_meses=24) == 6


class TestCalcularRegresiones:
    def _puntos(self, xs, ys):
        return [SimpleNamespace(valor_patron=x, valor_indicado=y) for x, y in zip(xs, ys)]

    def test_menos_de_dos_puntos_no_da_regresiones(self):
        assert calcular_regresiones(self._puntos([1.0], [1.0])) == []

    def test_relacion_lineal_perfecta_da_r2_uno(self):
        puntos = self._puntos([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        resultados = calcular_regresiones(puntos, max_grado=1)
        assert resultados, "debería encontrar al menos el grado 1"
        assert resultados[0]["r2"] == 1.0

    def test_resultados_ordenados_por_r2_descendente(self):
        puntos = self._puntos([1, 2, 3, 4, 5, 6], [2.1, 3.9, 6.2, 7.8, 10.3, 11.9])
        resultados = calcular_regresiones(puntos)
        r2s = [r["r2"] for r in resultados]
        assert r2s == sorted(r2s, reverse=True)
