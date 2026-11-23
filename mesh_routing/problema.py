"""Formalización del enrutamiento de una alerta como problema de búsqueda.

Abstracción (Fase 2): se toma una "fotografía" de la red en un instante dado. Con ella el
entorno se vuelve **determinista** (enviar a un vecino siempre lleva el mensaje a ese
vecino; la incertidumbre del canal ya está incluida en el costo ETX) y **discreto** (los
estados son nodos de un grafo finito).

Componentes formales (misma interfaz de ``Problem`` de AIMA-Python):

* Estado: nodo de la red donde se encuentra el mensaje de alerta.
* Estado inicial: nodo que detectó el evento (``origen``).
* Acciones(s): transmitir a un vecino ``v`` de ``s`` que esté activo.
* Modelo de transición: Resultado(s, transmitir(v)) = v.
* Prueba de meta: s == gateway.
* Costo de acción: c(s, v) = ETX(s, v); costo de ruta = suma de ETX.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable

from .topologia import RedMesh


class ProblemaEnrutamiento:
    """Problema de búsqueda: llevar una alerta desde ``origen`` hasta el gateway."""

    def __init__(self, red: RedMesh, origen: str, nodos_caidos: Iterable[str] = ()):
        if origen not in red.posiciones:
            raise ValueError(f"El nodo {origen} no existe en la red")
        self.red = red
        self.initial = origen
        self.goal = red.gateway
        self.caidos = set(nodos_caidos)

    # -------------------------------------------------------- componentes formales
    def actions(self, estado: str) -> list[str]:
        """Vecinos activos a los que se puede transmitir (orden alfabético = búsqueda no informada)."""
        return sorted(v for v in self.red.enlaces[estado] if v not in self.caidos)

    def result(self, estado: str, accion: str) -> str:
        """Modelo de transición determinista: el mensaje queda en el vecino elegido."""
        return accion

    def is_goal(self, estado: str) -> bool:
        return estado == self.goal

    def action_cost(self, estado: str, accion: str, resultado: str) -> float:
        """Costo de un salto = ETX del enlace (transmisiones esperadas)."""
        return self.red.enlaces[estado][resultado]

    # ---------------------------------------------------------------- heurísticas
    def h_saltos_simple(self, estado: str) -> float:
        """h1(n) = d(n, GW) / R * ETX_min. Admisible y consistente, pero poco informada."""
        return self.red.distancia(estado, self.goal) / self.red.alcance * self.red.etx_min

    def h_saltos(self, estado: str) -> float:
        """h2(n) = ceil(d(n, GW) / R) * ETX_min.

        Cada salto avanza como máximo R metros, así que se necesitan al menos ceil(d/R)
        saltos, y cada uno cuesta al menos ETX_min.
        """
        d = self.red.distancia(estado, self.goal)
        return math.ceil(d / self.red.alcance - 1e-9) * self.red.etx_min

    def h_avance(self, estado: str) -> float:
        """h3(n) = d(n, GW) / rho_max, con rho_max = max(longitud(e) / ETX(e)).

        Ningún enlace avanza más de rho_max metros por transmisión esperada; por la
        desigualdad triangular, toda ruta desde n cuesta al menos d(n, GW) / rho_max.
        """
        return self.red.distancia(estado, self.goal) / self.red.rho_max

    def h(self, estado: str) -> float:
        """Heurística final: h(n) = max(h2(n), h3(n)).

        El máximo de heurísticas consistentes también es consistente y domina a ambas.
        """
        return max(self.h_saltos(estado), self.h_avance(estado))

    def heuristicas(self) -> dict[str, Callable[[str], float]]:
        return {"h1": self.h_saltos_simple, "h2": self.h_saltos, "h3": self.h_avance, "h": self.h}
