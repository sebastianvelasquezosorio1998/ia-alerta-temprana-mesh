"""Algoritmos de búsqueda instrumentados: BFS, DFS, costo uniforme (UCS) y A*.

Siguen el pseudocódigo de Russell y Norvig (2021, cap. 3) y la interfaz de AIMA-Python,
pero cada algoritmo cuenta lo que necesita el benchmark de la Fase 2:

* nodos expandidos: nodos a los que se les generaron sucesores;
* nodos generados: nodos hijos creados;
* frontera máxima: tamaño máximo de la frontera (memoria);
* alcanzados: tamaño final de la tabla de estados alcanzados (memoria);
* costo de la solución (suma de ETX) y longitud en saltos.
"""
from __future__ import annotations

import heapq
import itertools
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from .problema import ProblemaEnrutamiento


@dataclass
class Nodo:
    """Nodo del árbol de búsqueda."""

    estado: str
    padre: "Nodo | None" = None
    costo: float = 0.0       # g(n): costo acumulado (suma de ETX)
    profundidad: int = 0     # número de saltos desde el origen

    def ruta(self) -> list[str]:
        nodo, ruta = self, []
        while nodo is not None:
            ruta.append(nodo.estado)
            nodo = nodo.padre
        return ruta[::-1]


@dataclass
class Resultado:
    algoritmo: str
    ruta: list[str] | None
    costo: float
    expandidos: int
    generados: int
    frontera_max: int
    alcanzados: int
    tiempo_ms: float = 0.0

    @property
    def saltos(self) -> int | None:
        return None if self.ruta is None else len(self.ruta) - 1


def expandir(problema: ProblemaEnrutamiento, nodo: Nodo):
    """Genera los nodos hijos aplicando cada acción posible."""
    s = nodo.estado
    for accion in problema.actions(s):
        s2 = problema.result(s, accion)
        costo = nodo.costo + problema.action_cost(s, accion, s2)
        yield Nodo(s2, nodo, costo, nodo.profundidad + 1)


def _resultado(nombre, nodo, exp, gen, fmax, alc) -> Resultado:
    if nodo is None:
        return Resultado(nombre, None, float("inf"), exp, gen, fmax, alc)
    return Resultado(nombre, nodo.ruta(), round(nodo.costo, 2), exp, gen, fmax, alc)


# ------------------------------------------------------------------ no informadas
def busqueda_amplitud(problema: ProblemaEnrutamiento) -> Resultado:
    """BFS (búsqueda en grafo, cola FIFO, prueba de meta temprana).

    Encuentra la ruta con MENOS SALTOS, no necesariamente la de menor ETX.
    """
    nodo = Nodo(problema.initial)
    if problema.is_goal(nodo.estado):
        return _resultado("BFS", nodo, 0, 0, 1, 1)
    frontera = deque([nodo])
    alcanzados = {problema.initial}
    exp = gen = 0
    fmax = 1
    while frontera:
        nodo = frontera.popleft()
        exp += 1
        for hijo in expandir(problema, nodo):
            gen += 1
            if problema.is_goal(hijo.estado):
                return _resultado("BFS", hijo, exp, gen, fmax, len(alcanzados) + 1)
            if hijo.estado not in alcanzados:
                alcanzados.add(hijo.estado)
                frontera.append(hijo)
        fmax = max(fmax, len(frontera))
    return _resultado("BFS", None, exp, gen, fmax, len(alcanzados))


def busqueda_profundidad(problema: ProblemaEnrutamiento) -> Resultado:
    """DFS (búsqueda en grafo, pila LIFO, prueba de meta temprana).

    Sigue una sola rama hasta el fondo; no es óptima y suele devolver rutas largas.
    """
    nodo = Nodo(problema.initial)
    if problema.is_goal(nodo.estado):
        return _resultado("DFS", nodo, 0, 0, 1, 1)
    frontera = [nodo]
    alcanzados = {problema.initial}
    exp = gen = 0
    fmax = 1
    while frontera:
        nodo = frontera.pop()
        exp += 1
        for hijo in expandir(problema, nodo):
            gen += 1
            if problema.is_goal(hijo.estado):
                return _resultado("DFS", hijo, exp, gen, fmax, len(alcanzados) + 1)
            if hijo.estado not in alcanzados:
                alcanzados.add(hijo.estado)
                frontera.append(hijo)
        fmax = max(fmax, len(frontera))
    return _resultado("DFS", None, exp, gen, fmax, len(alcanzados))


# --------------------------------------------------------------------- informadas
def busqueda_primero_mejor(problema: ProblemaEnrutamiento, f: Callable[[Nodo], float], nombre: str) -> Resultado:
    """Best-first search de AIMA (4.ª ed.) con tabla de alcanzados y cola de prioridad por f."""
    nodo = Nodo(problema.initial)
    contador = itertools.count()          # desempate estable (FIFO entre iguales)
    frontera = [(f(nodo), next(contador), nodo)]
    alcanzados = {problema.initial: nodo}
    exp = gen = 0
    fmax = 1
    while frontera:
        _, _, nodo = heapq.heappop(frontera)
        if nodo.costo > alcanzados[nodo.estado].costo:
            continue                      # entrada obsoleta: ya hay un camino más barato
        if problema.is_goal(nodo.estado):
            return _resultado(nombre, nodo, exp, gen, fmax, len(alcanzados))
        exp += 1
        for hijo in expandir(problema, nodo):
            gen += 1
            s = hijo.estado
            if s not in alcanzados or hijo.costo < alcanzados[s].costo:
                alcanzados[s] = hijo
                heapq.heappush(frontera, (f(hijo), next(contador), hijo))
        fmax = max(fmax, len(frontera))
    return _resultado(nombre, None, exp, gen, fmax, len(alcanzados))


def busqueda_costo_uniforme(problema: ProblemaEnrutamiento) -> Resultado:
    """UCS / Dijkstra: f(n) = g(n). Óptima; sirve de referencia (equivale a A* con h = 0)."""
    return busqueda_primero_mejor(problema, lambda n: n.costo, "UCS")


def busqueda_a_estrella(problema: ProblemaEnrutamiento, h: Callable[[str], float] | None = None,
                        nombre: str = "A*") -> Resultado:
    """A*: f(n) = g(n) + h(n). Con h admisible y consistente devuelve la ruta de menor ETX."""
    h = h or problema.h
    cache: dict[str, float] = {}          # cada estado calcula su h una sola vez

    def h_memo(s: str) -> float:
        v = cache.get(s)
        if v is None:
            v = cache[s] = h(s)
        return v

    return busqueda_primero_mejor(problema, lambda n: n.costo + h_memo(n.estado), nombre)


# ----------------------------------------------------------------------- medición
def medir(fn: Callable[[], Resultado], repeticiones: int = 30) -> Resultado:
    """Ejecuta ``fn`` varias veces y guarda la mediana del tiempo en milisegundos."""
    tiempos = []
    res = None
    for _ in range(repeticiones):
        t0 = time.perf_counter_ns()
        res = fn()
        tiempos.append(time.perf_counter_ns() - t0)
    tiempos.sort()
    res.tiempo_ms = tiempos[len(tiempos) // 2] / 1e6
    return res
