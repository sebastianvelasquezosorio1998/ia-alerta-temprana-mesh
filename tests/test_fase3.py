"""Pruebas del motor de encadenamiento hacia adelante (Fase 3)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fase3.motor_inferencia import CASO_N10, REGLAS, encadenamiento_adelante  # noqa: E402


class PruebasMotor(unittest.TestCase):
    def test_caso_n10(self):
        conocidos, pasos = encadenamiento_adelante(CASO_N10, REGLAS)
        for h in ("EmitirAlertaTemprana", "RecalcularRutas", "AjustarPotencia", "InspeccionPrioritaria"):
            self.assertIn(h, conocidos)
        self.assertNotIn("FallaEnergia", conocidos)
        self.assertEqual([p.regla.nombre for p in pasos], ["R4", "R3", "R6", "R5", "R7", "R8", "R9"])

    def test_falla_de_energia(self):
        conocidos, _ = encadenamiento_adelante(["SinLatido", "BateriaBaja"], REGLAS)
        self.assertIn("ProgramarMantenimiento", conocidos)
        self.assertNotIn("EmitirAlertaTemprana", conocidos)

    def test_sin_hechos_no_infiere(self):
        conocidos, pasos = encadenamiento_adelante([], REGLAS)
        self.assertEqual(conocidos, set())
        self.assertEqual(pasos, [])


if __name__ == "__main__":
    unittest.main()
