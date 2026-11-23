"""Fase 3: base de conocimiento y motor de reglas para diagnosticar un nodo silencioso.

Micro-dominio: diagnóstico de fallas en la red Mesh de alerta temprana. Cuando un nodo deja
de reportar, el agente debe decidir si se trata de una falla de energía, de un enlace
degradado por la lluvia o de un posible movimiento en masa que desplazó el nodo.

El motor implementa encadenamiento hacia adelante con Modus Ponens sobre cláusulas de Horn,
siguiendo el algoritmo PL-FC-ENTAILS? de Russell y Norvig (2021, cap. 7): cada regla lleva
un contador de premisas pendientes y una agenda guarda los hechos por procesar. El costo es
lineal en el tamaño de la base de conocimiento.

Uso:  python -m fase3.motor_inferencia
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

# --------------------------------------------------------------- diccionario de proposiciones
PROPOSICIONES = {
    # observables (hechos que llegan de los sensores y del gateway)
    "SinLatido": "El gateway no recibe el latido (heartbeat) del nodo desde hace 3 periodos (15 min).",
    "BateriaBaja": "El último voltaje reportado por el nodo fue menor a 3,4 V.",
    "BateriaNormal": "El último voltaje reportado por el nodo fue de al menos 3,6 V.",
    "VecinosActivos": "Los vecinos del nodo siguen enviando su latido con normalidad.",
    "RSSIBajo": "Antes del silencio, los vecinos recibían al nodo con RSSI menor a -85 dBm.",
    "LluviaIntensa": "El pluviómetro de la zona registra más de 20 mm/h.",
    "SueloSaturado": "La humedad volumétrica del suelo de la zona supera el 40 %.",
    "InclinacionBrusca": "El último reporte del inclinómetro del nodo cambió más de 5° frente a su línea base.",
    # derivadas (diagnósticos)
    "FallaEnergia": "El silencio del nodo se explica por batería agotada.",
    "EnlaceDegradado": "La lluvia y la vegetación mojada degradaron el enlace del nodo.",
    "PosibleMovimientoMasa": "Hay evidencia de un posible movimiento en masa en la zona.",
    "NodoComprometido": "El nodo pudo ser desplazado o dañado por el terreno.",
    # acciones del agente
    "ProgramarMantenimiento": "Programar cambio de batería o revisión del panel solar.",
    "RecalcularRutas": "Recalcular rutas con A* excluyendo el nodo silencioso (Fase 2).",
    "AjustarPotencia": "Ordenar a los vecinos aumentar su potencia de transmisión.",
    "EmitirAlertaTemprana": "Emitir alerta temprana a la comunidad y al IDIGER.",
    "InspeccionPrioritaria": "Enviar una inspección prioritaria al sitio del nodo.",
}


@dataclass(frozen=True)
class Regla:
    nombre: str
    premisas: tuple[str, ...]
    conclusion: str

    def __str__(self) -> str:
        return f"{self.nombre}: {' ∧ '.join(self.premisas)} → {self.conclusion}"


REGLAS = [
    Regla("R1", ("SinLatido", "BateriaBaja"), "FallaEnergia"),
    Regla("R2", ("FallaEnergia",), "ProgramarMantenimiento"),
    Regla("R3", ("RSSIBajo", "LluviaIntensa"), "EnlaceDegradado"),
    Regla("R4", ("SinLatido", "VecinosActivos"), "RecalcularRutas"),
    Regla("R5", ("EnlaceDegradado",), "AjustarPotencia"),
    Regla("R6", ("LluviaIntensa", "SueloSaturado", "InclinacionBrusca"), "PosibleMovimientoMasa"),
    Regla("R7", ("PosibleMovimientoMasa",), "EmitirAlertaTemprana"),
    Regla("R8", ("SinLatido", "BateriaNormal", "PosibleMovimientoMasa"), "NodoComprometido"),
    Regla("R9", ("NodoComprometido",), "InspeccionPrioritaria"),
]

# Caso de entrada: nodo N10 (zona alta Z3) en una noche de lluvia fuerte
CASO_N10 = ["SinLatido", "BateriaNormal", "VecinosActivos", "RSSIBajo",
            "LluviaIntensa", "SueloSaturado", "InclinacionBrusca"]


@dataclass
class Paso:
    numero: int
    hecho_procesado: str
    regla: Regla
    nuevo_hecho: str


def encadenamiento_adelante(hechos: list[str], reglas: list[Regla]):
    """Aplica Modus Ponens hasta que no se puedan inferir hechos nuevos (punto fijo).

    Devuelve (hechos conocidos, pasos de inferencia en el orden en que ocurrieron).
    """
    pendientes = {r: len(set(r.premisas)) for r in reglas}   # premisas aún no satisfechas
    agenda = deque(hechos)
    inferido: set[str] = set()
    pasos: list[Paso] = []
    while agenda:
        p = agenda.popleft()
        if p in inferido:
            continue
        inferido.add(p)
        for r in reglas:
            if p in r.premisas:
                pendientes[r] -= 1
                if pendientes[r] == 0:                     # todas las premisas son hechos:
                    pasos.append(Paso(len(pasos) + 1, p, r, r.conclusion))   # Modus Ponens
                    agenda.append(r.conclusion)
    return inferido, pasos


def main() -> None:
    print("Hechos iniciales:", ", ".join(CASO_N10), "\n")
    conocidos, pasos = encadenamiento_adelante(CASO_N10, REGLAS)
    for paso in pasos:
        print(f"Paso {paso.numero}: al procesar '{paso.hecho_procesado}' se cumplen todas las premisas de "
              f"{paso.regla}  ⇒  {paso.nuevo_hecho}")
    no_disparadas = [r.nombre for r in REGLAS if r not in {p.regla for p in pasos}]
    print("\nReglas no disparadas:", ", ".join(no_disparadas))
    acciones = [h for h in ("EmitirAlertaTemprana", "RecalcularRutas", "AjustarPotencia",
                            "InspeccionPrioritaria", "ProgramarMantenimiento") if h in conocidos]
    print("Decisión del agente:")
    for a in acciones:
        print("  -", PROPOSICIONES[a])

    # Acción RecalcularRutas: se reutiliza la búsqueda A* de la Fase 2 sin el nodo N10
    if "RecalcularRutas" in conocidos:
        from mesh_routing import ProblemaEnrutamiento, busqueda_a_estrella, generar_red
        red = generar_red(60, semilla=2026)
        antes = busqueda_a_estrella(ProblemaEnrutamiento(red, "N35"))
        despues = busqueda_a_estrella(ProblemaEnrutamiento(red, "N35", nodos_caidos={"N10"}))
        print(f"\nRuta de N35 antes:   {' > '.join(antes.ruta)}  (ETX {antes.costo})")
        print(f"Ruta de N35 sin N10: {' > '.join(despues.ruta)}  (ETX {despues.costo})")


if __name__ == "__main__":
    main()
