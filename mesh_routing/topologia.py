"""Generación de la red Mesh de alerta temprana y cálculo del costo ETX de cada enlace.

La red representa nodos ESP32 instalados en una ladera (eje ``y`` = parte alta de la
ladera) que se comunican con ESP-NOW y entregan sus mensajes a un gateway ubicado en la
parte baja, donde hay energía y cobertura 4G.

El costo de cada enlace es el ETX (Expected Transmission Count) de De Couto et al. (2003):

    ETX = 1 / (d_f * d_r)

donde ``d_f`` y ``d_r`` son las tasas de entrega en los dos sentidos del enlace. El ETX es
el número esperado de transmisiones (incluidas las retransmisiones) para entregar un
paquete por ese enlace; por eso siempre es >= 1.
"""
from __future__ import annotations

import json
import math
import random
from collections import deque
from dataclasses import dataclass, field

GATEWAY = "GW"


@dataclass
class RedMesh:
    """Grafo no dirigido y ponderado de la red Mesh.

    Atributos:
        posiciones: nodo -> (x, y) en metros.
        enlaces: nodo -> {vecino: ETX del enlace}. Es simétrico.
        gateway: identificador del nodo pasarela (meta de la búsqueda).
        alcance: longitud máxima (m) de un enlace utilizable.
    """

    posiciones: dict[str, tuple[float, float]]
    enlaces: dict[str, dict[str, float]]
    gateway: str = GATEWAY
    alcance: float = 180.0
    _etx_min: float | None = field(default=None, init=False, repr=False)
    _rho_max: float | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------ geometría
    def distancia(self, a: str, b: str) -> float:
        """Distancia euclidiana en metros entre dos nodos."""
        (xa, ya), (xb, yb) = self.posiciones[a], self.posiciones[b]
        return math.hypot(xa - xb, ya - yb)

    # ------------------------------------------------------------- estadísticas
    @property
    def nodos(self) -> list[str]:
        return list(self.posiciones)

    @property
    def num_enlaces(self) -> int:
        return sum(len(v) for v in self.enlaces.values()) // 2

    @property
    def grado_promedio(self) -> float:
        """Factor de ramificación promedio b (vecinos por nodo)."""
        return 2 * self.num_enlaces / len(self.posiciones)

    @property
    def etx_min(self) -> float:
        """Menor ETX de toda la red (costo mínimo posible de un salto)."""
        if self._etx_min is None:
            self._etx_min = min(c for vec in self.enlaces.values() for c in vec.values())
        return self._etx_min

    @property
    def rho_max(self) -> float:
        """Máximo avance geográfico por transmisión esperada: max(longitud / ETX) en metros.

        Para cualquier enlace e se cumple ETX(e) >= longitud(e) / rho_max, propiedad que
        hace admisible y consistente a la heurística ``h_avance``.
        """
        if self._rho_max is None:
            self._rho_max = max(
                self.distancia(a, b) / c for a, vec in self.enlaces.items() for b, c in vec.items()
            )
        return self._rho_max

    def componente_gateway(self) -> set[str]:
        """Nodos que tienen al menos un camino hasta el gateway."""
        vistos, cola = {self.gateway}, deque([self.gateway])
        while cola:
            u = cola.popleft()
            for v in self.enlaces[u]:
                if v not in vistos:
                    vistos.add(v)
                    cola.append(v)
        return vistos

    def es_conexa(self) -> bool:
        """True si todos los nodos pueden llegar al gateway."""
        return len(self.componente_gateway()) == len(self.posiciones)

    def nodo_mas_lejano(self) -> str:
        """Nodo más alejado del gateway (peor caso para enrutar una alerta)."""
        return max((n for n in self.posiciones if n != self.gateway), key=lambda n: self.distancia(n, self.gateway))

    # ------------------------------------------------------------- persistencia
    def a_json(self, ruta: str) -> None:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"gateway": self.gateway, "alcance": self.alcance,
                       "posiciones": self.posiciones, "enlaces": self.enlaces}, f, indent=1)

    @classmethod
    def desde_json(cls, ruta: str) -> "RedMesh":
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        pos = {k: tuple(v) for k, v in d["posiciones"].items()}
        return cls(pos, d["enlaces"], d["gateway"], d["alcance"])


def tasa_entrega(distancia: float, alcance: float, factor_obstaculo: float) -> float:
    """Modelo simplificado de tasa de entrega de paquetes (PDR) de un sentido del enlace.

    Hasta el 40 % del alcance la entrega es casi perfecta (0,98). Desde ahí cae de forma
    cuadrática hasta 0,40 en el borde del alcance. ``factor_obstaculo`` (0,80 a 1,00)
    representa vegetación, viviendas y relieve entre los dos nodos.
    """
    d0 = 0.4 * alcance
    if distancia <= d0:
        p = 0.98
    else:
        p = 0.98 - 0.58 * ((distancia - d0) / (alcance - d0)) ** 2
    return p * factor_obstaculo


def generar_red(n_nodos: int = 60, ancho: float | None = None, alto: float | None = None,
                alcance: float = 180.0, semilla: int = 2026, etx_max: float = 8.0,
                densidad: float = 62.5e-6, podar_aislados: bool = False,
                max_intentos: int = 500) -> RedMesh:
    """Genera una red Mesh aleatoria y reproducible.

    Args:
        n_nodos: número de nodos sensores (sin contar el gateway).
        ancho, alto: dimensiones del área en metros. Si no se indican, se calculan para
            mantener la densidad dada con proporción 3:2 (60 nodos -> 1200 m x 800 m).
        alcance: distancia máxima de un enlace (m).
        semilla: semilla del generador aleatorio (misma semilla = misma red).
        etx_max: enlaces con ETX mayor se consideran inutilizables y se descartan.
        densidad: nodos por metro cuadrado cuando el área se calcula automáticamente.
        podar_aislados: si es False, se repite el sorteo hasta obtener una red conexa. Si es
            True (redes grandes), se eliminan los nodos que no pueden llegar al gateway, que en
            campo necesitarían un repetidor; se exige que quede al menos el 90 % de la red.
    """
    if ancho is None or alto is None:
        area = n_nodos / densidad
        ancho, alto = math.sqrt(area * 1.5), math.sqrt(area / 1.5)
    rng = random.Random(semilla)
    ancho_id = max(2, len(str(n_nodos)))
    for _ in range(max_intentos):
        pos: dict[str, tuple[float, float]] = {GATEWAY: (ancho / 2, 0.0)}
        for i in range(1, n_nodos + 1):
            pos[f"N{i:0{ancho_id}d}"] = (round(rng.uniform(0, ancho), 1), round(rng.uniform(0, alto), 1))
        ids = list(pos)
        indice = {n: i for i, n in enumerate(ids)}
        # rejilla espacial de celdas de tamaño = alcance: solo se comparan nodos de celdas vecinas
        celdas: dict[tuple[int, int], list[str]] = {}
        for n, (x, y) in pos.items():
            celdas.setdefault((int(x // alcance), int(y // alcance)), []).append(n)
        enlaces: dict[str, dict[str, float]] = {n: {} for n in pos}
        for a in ids:
            cx, cy = int(pos[a][0] // alcance), int(pos[a][1] // alcance)
            candidatos = [b for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                          for b in celdas.get((cx + dx, cy + dy), ()) if indice[b] > indice[a]]
            for b in sorted(candidatos, key=indice.__getitem__):
                d = math.dist(pos[a], pos[b])
                if d > alcance:
                    continue
                pf = tasa_entrega(d, alcance, rng.uniform(0.80, 1.00))
                pr = tasa_entrega(d, alcance, rng.uniform(0.80, 1.00))
                etx = round(1.0 / (pf * pr), 2)
                if etx <= etx_max:
                    enlaces[a][b] = etx
                    enlaces[b][a] = etx
        red = RedMesh(pos, enlaces, GATEWAY, alcance)
        if red.es_conexa():
            return red
        if podar_aislados:
            comp = red.componente_gateway()
            if len(comp) >= 0.9 * len(pos):
                pos2 = {n: p for n, p in pos.items() if n in comp}
                enl2 = {n: {v: c for v, c in enlaces[n].items() if v in comp} for n in pos2}
                return RedMesh(pos2, enl2, GATEWAY, alcance)
    raise RuntimeError("No se logró generar una red conexa; aumente el alcance o la densidad.")
