"""Figura de la Fase 2: (a) rutas halladas en la red principal y (b) nodos expandidos vs tamaño.

Uso:  python -m experimentos.figura_rutas      (requiere matplotlib y haber corrido el benchmark)
Salida: resultados/figura_rutas.png
"""
from __future__ import annotations

import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from mesh_routing import (ProblemaEnrutamiento, busqueda_a_estrella, busqueda_amplitud,  # noqa: E402
                          busqueda_profundidad, generar_red)
from experimentos.benchmark import RESULTADOS, SEMILLA  # noqa: E402

# Paleta categórica validada (orden fijo); el estilo de línea y el marcador dan una
# segunda codificación para impresión en escala de grises o daltonismo.
ESTILO = {
    "A*":  dict(color="#2a78d6", ls="-",  marker="o", lw=2.4),
    "BFS": dict(color="#eb6834", ls="--", marker="s", lw=1.8),
    "DFS": dict(color="#1baf7a", ls=":",  marker="^", lw=1.8),
    "UCS": dict(color="#eda100", ls="-.", marker="D", lw=1.6),
}
TINTA, TINTA2, REJILLA = "#0b0b0b", "#52514e", "#e6e5e1"


def panel_rutas(ax):
    red = generar_red(60, semilla=SEMILLA)
    origen = red.nodo_mas_lejano()
    p = ProblemaEnrutamiento(red, origen)
    rutas = {"DFS": busqueda_profundidad(p).ruta, "BFS": busqueda_amplitud(p).ruta, "A*": busqueda_a_estrella(p).ruta}
    for a, vec in red.enlaces.items():
        for b in vec:
            if a < b:
                (x1, y1), (x2, y2) = red.posiciones[a], red.posiciones[b]
                ax.plot([x1, x2], [y1, y2], color=REJILLA, lw=0.7, zorder=1)
    xs, ys = zip(*(red.posiciones[n] for n in red.posiciones if n != red.gateway))
    ax.scatter(xs, ys, s=9, color="#9a9994", zorder=2, linewidths=0)
    offsets = {"A*": 0, "BFS": 0, "DFS": 0}
    for nombre in ("DFS", "BFS", "A*"):
        st = ESTILO[nombre]
        px, py = zip(*(red.posiciones[n] for n in rutas[nombre]))
        etiqueta = "A* = UCS (óptima)" if nombre == "A*" else nombre
        ax.plot(px, py, color=st["color"], ls=st["ls"], lw=st["lw"], zorder=3 + offsets[nombre],
                label=f"{etiqueta}: {len(rutas[nombre]) - 1} saltos")
    gx, gy = red.posiciones[red.gateway]
    ax.scatter([gx], [gy], marker="s", s=60, color=TINTA, zorder=6)
    ax.annotate("Gateway", (gx, gy), xytext=(6, 4), textcoords="offset points", fontsize=7.5, color=TINTA)
    ox, oy = red.posiciones[origen]
    ax.scatter([ox], [oy], marker="*", s=120, color=TINTA, zorder=6)
    ax.annotate(f"Origen {origen}", (ox, oy), xytext=(-52, -11), textcoords="offset points", fontsize=7.5, color=TINTA)
    ax.set_title("(a) Rutas de la alerta en la red principal (60 nodos)", fontsize=8.5, color=TINTA, loc="left")
    ax.set_xlabel("x (m)", fontsize=7.5, color=TINTA2)
    ax.set_ylabel("y (m) – parte alta de la ladera", fontsize=7.5, color=TINTA2)
    ax.set_aspect("equal")
    ax.legend(fontsize=7, loc="upper left", frameon=False)


def panel_escalabilidad(ax):
    with open(os.path.join(RESULTADOS, "escalabilidad.csv"), encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    series = {"A*": "A*", "BFS": "BFS", "DFS": "DFS", "UCS": "UCS (A* con h = 0)"}
    for nombre, clave in series.items():
        datos = [(float(r["nodos_conectados"]), float(r["expandidos"])) for r in filas if r["algoritmo"] == clave]
        x, y = zip(*datos)
        st = ESTILO[nombre]
        ax.plot(x, y, color=st["color"], ls=st["ls"], marker=st["marker"], lw=1.6, ms=4, label=nombre)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([50, 100, 200, 400, 800, 1600], ["50", "100", "200", "400", "800", "1600"])
    ax.set_yticks([16, 32, 64, 128, 256, 512, 1024], ["16", "32", "64", "128", "256", "512", "1024"])
    ax.minorticks_off()
    ax.set_title("(b) Nodos expandidos vs. tamaño de red", fontsize=8.5, color=TINTA, loc="left")
    ax.set_xlabel("Nodos conectados al gateway (escala log.)", fontsize=7.5, color=TINTA2)
    ax.set_ylabel("Nodos expandidos (promedio de 30 redes)", fontsize=7.5, color=TINTA2)
    ax.grid(True, which="major", color=REJILLA, lw=0.6)
    ax.legend(fontsize=7, loc="upper left", frameon=False)


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": "#b5b4ae", "axes.linewidth": 0.6,
                         "xtick.labelsize": 7, "ytick.labelsize": 7, "xtick.color": TINTA2, "ytick.color": TINTA2})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.0, 2.9), gridspec_kw={"width_ratios": [1.35, 1]})
    panel_rutas(a1)
    panel_escalabilidad(a2)
    fig.tight_layout(w_pad=1.2)
    salida = os.path.join(RESULTADOS, "figura_rutas.png")
    fig.savefig(salida, dpi=220)
    print("Figura guardada en", salida)


if __name__ == "__main__":
    main()
