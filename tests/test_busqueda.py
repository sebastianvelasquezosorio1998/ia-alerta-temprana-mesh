"""Pruebas unitarias de la Fase 2.  Ejecutar con:  python -m unittest discover -s tests -v"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mesh_routing import (ProblemaEnrutamiento, RedMesh, busqueda_a_estrella, busqueda_amplitud,  # noqa: E402
                          busqueda_costo_uniforme, busqueda_profundidad, generar_red)


def red_pequena() -> RedMesh:
    """Red de 5 nodos donde la ruta de menos saltos NO es la de menor ETX.

        A --(5.0)-- GW            A -> GW directo: 1 salto, ETX 5.0
        A --(1.1)-- B --(1.2)-- C --(1.1)-- GW   3 saltos, ETX 3.4
        A --(2.0)-- D --(4.0)-- GW               2 saltos, ETX 6.0
    """
    pos = {"GW": (0, 0), "A": (150, 0), "B": (110, 30), "C": (60, 30), "D": (80, -40)}
    e = {n: {} for n in pos}

    def enlace(a, b, c):
        e[a][b] = c
        e[b][a] = c

    enlace("A", "GW", 5.0)
    enlace("A", "B", 1.1)
    enlace("B", "C", 1.2)
    enlace("C", "GW", 1.1)
    enlace("A", "D", 2.0)
    enlace("D", "GW", 4.0)
    return RedMesh(pos, e, "GW", 180.0)


def ruta_valida(red: RedMesh, ruta) -> bool:
    return ruta[-1] == red.gateway and all(b in red.enlaces[a] for a, b in zip(ruta, ruta[1:]))


class PruebasRedPequena(unittest.TestCase):
    def setUp(self):
        self.red = red_pequena()
        self.p = ProblemaEnrutamiento(self.red, "A")

    def test_bfs_minimiza_saltos(self):
        r = busqueda_amplitud(self.p)
        self.assertEqual(r.ruta, ["A", "GW"])
        self.assertEqual(r.saltos, 1)

    def test_a_estrella_minimiza_etx(self):
        r = busqueda_a_estrella(self.p)
        self.assertEqual(r.ruta, ["A", "B", "C", "GW"])
        self.assertAlmostEqual(r.costo, 3.4)

    def test_ucs_coincide_con_a_estrella(self):
        self.assertAlmostEqual(busqueda_costo_uniforme(self.p).costo, busqueda_a_estrella(self.p).costo)

    def test_dfs_devuelve_ruta_valida(self):
        r = busqueda_profundidad(self.p)
        self.assertTrue(ruta_valida(self.red, r.ruta))

    def test_nodo_caido_obliga_a_reenrutar(self):
        p = ProblemaEnrutamiento(self.red, "A", nodos_caidos={"B"})
        r = busqueda_a_estrella(p)
        self.assertNotIn("B", r.ruta)
        self.assertAlmostEqual(r.costo, 5.0)


class PruebasRedesAleatorias(unittest.TestCase):
    """Propiedades que deben cumplirse en cualquier red generada."""

    def test_etx_mayor_o_igual_a_uno(self):
        red = generar_red(80, semilla=7)
        self.assertTrue(all(c >= 1.0 for vec in red.enlaces.values() for c in vec.values()))

    def test_misma_semilla_misma_red(self):
        self.assertEqual(generar_red(60, semilla=2026).enlaces, generar_red(60, semilla=2026).enlaces)

    def test_heuristica_admisible_y_consistente(self):
        for semilla in range(5):
            red = generar_red(80, semilla=semilla)
            p = ProblemaEnrutamiento(red, red.nodo_mas_lejano())
            # costo real h*(n) desde cada nodo hasta el gateway (UCS desde cada nodo)
            for n in red.posiciones:
                real = busqueda_costo_uniforme(ProblemaEnrutamiento(red, n)).costo
                for nombre, h in p.heuristicas().items():
                    self.assertLessEqual(h(n), real + 1e-9, f"{nombre} sobreestima en {n}")
            for a, vec in red.enlaces.items():          # consistencia: h(a) <= c(a,b) + h(b)
                for b, c in vec.items():
                    self.assertLessEqual(p.h(a), c + p.h(b) + 1e-9)

    def test_a_estrella_es_optimo_y_expande_menos(self):
        for semilla in range(10):
            red = generar_red(100, semilla=100 + semilla)
            p = ProblemaEnrutamiento(red, red.nodo_mas_lejano())
            ucs, ast = busqueda_costo_uniforme(p), busqueda_a_estrella(p)
            self.assertTrue(math.isclose(ucs.costo, ast.costo))
            self.assertLessEqual(ast.expandidos, ucs.expandidos)
            for r in (busqueda_amplitud(p), busqueda_profundidad(p)):
                self.assertTrue(ruta_valida(red, r.ruta))
                self.assertGreaterEqual(r.costo, ucs.costo - 1e-9)


if __name__ == "__main__":
    unittest.main()
