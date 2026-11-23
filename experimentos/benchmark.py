"""Benchmark de la Fase 2: BFS, DFS, UCS y A* sobre la red Mesh de alerta temprana.

Uso (desde la raíz del repositorio):

    python -m experimentos.benchmark            # experimento principal + escalabilidad
    python -m experimentos.benchmark --rapido   # escalabilidad con menos repeticiones

Genera en ``resultados/``:
    benchmark_principal.csv   experimento sobre una misma red y un mismo estado inicial
    heuristicas.csv           comparación de las heurísticas de A*
    escalabilidad.csv         promedios para redes de 50 a 1600 nodos
    red_principal.json        topología usada (para reproducir el experimento)
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import statistics as st

from mesh_routing import (ProblemaEnrutamiento, busqueda_a_estrella, busqueda_amplitud,
                          busqueda_costo_uniforme, busqueda_profundidad, generar_red, medir)

RESULTADOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resultados")
SEMILLA = 2026


def factor_ramificacion_efectivo(expandidos: int, profundidad: int) -> float:
    """b* tal que N + 1 = 1 + b* + b*^2 + ... + b*^d (Russell y Norvig, 2021, cap. 3)."""
    if profundidad <= 0:
        return 0.0
    objetivo = expandidos + 1

    def total(b: float) -> float:           # 1 + b + ... + b^d, sin desbordamiento
        if abs(b - 1.0) < 1e-12:
            return profundidad + 1.0
        lg = (profundidad + 1) * math.log(b)
        return float("inf") if lg > 700 else (math.exp(lg) - 1.0) / (b - 1.0)

    lo, hi = 1.0, max(2.0, float(expandidos))
    for _ in range(100):
        mid = (lo + hi) / 2
        if total(mid) < objetivo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def algoritmos(p: ProblemaEnrutamiento):
    return [
        ("BFS", lambda: busqueda_amplitud(p)),
        ("DFS", lambda: busqueda_profundidad(p)),
        ("UCS (A* con h = 0)", lambda: busqueda_costo_uniforme(p)),
        ("A*", lambda: busqueda_a_estrella(p, p.h, "A*")),
    ]


def experimento_principal(repeticiones: int = 200):
    red = generar_red(60, semilla=SEMILLA)
    os.makedirs(RESULTADOS, exist_ok=True)
    red.a_json(os.path.join(RESULTADOS, "red_principal.json"))
    origen = red.nodo_mas_lejano()
    p = ProblemaEnrutamiento(red, origen)
    print(f"Red: {len(red.posiciones)} nodos (incluido el gateway), {red.num_enlaces} enlaces, "
          f"b = {red.grado_promedio:.2f}, ETX_min = {red.etx_min}, rho_max = {red.rho_max:.1f} m")
    print(f"Estado inicial: {origen} a {red.distancia(origen, red.gateway):.0f} m del gateway\n")

    filas = []
    optimo = busqueda_costo_uniforme(p).costo
    print(f"{'Algoritmo':20} {'Exp.':>5} {'Gen.':>5} {'Front.':>6} {'Alc.':>5} {'Saltos':>6} {'Costo ETX':>9} {'Tiempo ms':>9}  Óptimo")
    for nombre, fn in algoritmos(p):
        r = medir(fn, repeticiones)
        opt = "Sí" if abs(r.costo - optimo) < 1e-9 else f"No (+{100 * (r.costo / optimo - 1):.0f} %)"
        filas.append({"algoritmo": nombre, "expandidos": r.expandidos, "generados": r.generados,
                      "frontera_max": r.frontera_max, "alcanzados": r.alcanzados, "saltos": r.saltos,
                      "costo_etx": r.costo, "tiempo_ms": round(r.tiempo_ms, 4), "optimo": opt,
                      "ruta": " > ".join(r.ruta)})
        print(f"{nombre:20} {r.expandidos:5} {r.generados:5} {r.frontera_max:6} {r.alcanzados:5} {r.saltos:6} "
              f"{r.costo:9.2f} {r.tiempo_ms:9.4f}  {opt}")
    _guardar("benchmark_principal.csv", filas)
    print()
    for f in filas:
        print(f"{f['algoritmo']:20} {f['ruta']}")

    print("\nHeurísticas de A* sobre el mismo problema:")
    hs = []
    for clave, desc in [("h0", "h = 0 (UCS)"), ("h1", "h1 = d/R · ETXmin"), ("h2", "h2 = techo(d/R) · ETXmin"),
                        ("h3", "h3 = d / rho_max"), ("h", "h = max(h2, h3)")]:
        fn_h = (lambda s: 0.0) if clave == "h0" else p.heuristicas()[clave]
        r = medir(lambda: busqueda_a_estrella(p, fn_h, clave), repeticiones)
        fila = {"heuristica": desc, "h_origen": round(fn_h(origen), 2), "expandidos": r.expandidos,
                "generados": r.generados, "costo_etx": r.costo, "tiempo_ms": round(r.tiempo_ms, 4),
                "b_efectivo": round(factor_ramificacion_efectivo(r.expandidos, r.saltos), 3)}
        hs.append(fila)
        print(f"  {desc:26} h(origen)={fila['h_origen']:6.2f}  exp={r.expandidos:3}  gen={r.generados:4}  "
              f"costo={r.costo:6.2f}  b*={fila['b_efectivo']:.3f}  t={r.tiempo_ms:.4f} ms")
    _guardar("heuristicas.csv", hs)
    return red, p


def experimento_escalabilidad(tamanos=(50, 100, 200, 400, 800, 1600), redes_por_tamano: int = 30,
                              repeticiones: int = 5):
    print("\nEscalabilidad (densidad constante; promedio de", redes_por_tamano, "redes por tamaño):")
    filas = []
    for n in tamanos:
        acum: dict[str, dict[str, list]] = {}
        bs, ds, nodos_reales = [], [], []
        for k in range(redes_por_tamano):
            red = generar_red(n, semilla=SEMILLA + 1000 * n + k, podar_aislados=True)
            nodos_reales.append(len(red.posiciones) - 1)
            p = ProblemaEnrutamiento(red, red.nodo_mas_lejano())
            optimo = busqueda_costo_uniforme(p).costo
            bs.append(red.grado_promedio)
            for nombre, fn in algoritmos(p):
                r = medir(fn, repeticiones)
                a = acum.setdefault(nombre, {"exp": [], "t": [], "ratio": [], "saltos": [], "fmax": [], "bef": []})
                a["exp"].append(r.expandidos)
                a["t"].append(r.tiempo_ms)
                a["ratio"].append(r.costo / optimo)
                a["saltos"].append(r.saltos)
                a["fmax"].append(r.frontera_max)
                a["bef"].append(factor_ramificacion_efectivo(r.expandidos, r.saltos))
                if nombre == "UCS (A* con h = 0)":
                    ds.append(r.saltos)
        for nombre, a in acum.items():
            fila = {"nodos": n, "nodos_conectados": round(st.mean(nodos_reales), 1), "b_promedio": round(st.mean(bs), 2), "d_optima_saltos": round(st.mean(ds), 1),
                    "algoritmo": nombre, "expandidos": round(st.mean(a["exp"]), 1),
                    "pct_red_expandida": round(100 * st.mean(a["exp"]) / (st.mean(nodos_reales) + 1), 1),
                    "frontera_max": round(st.mean(a["fmax"]), 1), "saltos": round(st.mean(a["saltos"]), 1),
                    "costo_vs_optimo": round(st.mean(a["ratio"]), 3), "tiempo_ms": round(st.mean(a["t"]), 3),
                    "b_efectivo": round(st.mean(a["bef"]), 3)}
            filas.append(fila)
            print(f"  n={n:5} {nombre:20} exp={fila['expandidos']:8.1f} ({fila['pct_red_expandida']:5.1f} %)  "
                  f"saltos={fila['saltos']:6.1f}  costo/óptimo={fila['costo_vs_optimo']:.3f}  "
                  f"t={fila['tiempo_ms']:8.3f} ms  b*={fila['b_efectivo']:.3f}")
    _guardar("escalabilidad.csv", filas)
    return filas


def _guardar(nombre: str, filas: list[dict]) -> None:
    os.makedirs(RESULTADOS, exist_ok=True)
    with open(os.path.join(RESULTADOS, nombre), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rapido", action="store_true", help="menos redes y repeticiones en la escalabilidad")
    args = ap.parse_args()
    experimento_principal(50 if args.rapido else 200)
    if args.rapido:
        experimento_escalabilidad(redes_por_tamano=5, repeticiones=1)
    else:
        experimento_escalabilidad()
