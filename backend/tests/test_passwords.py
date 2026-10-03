import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from passwords import generar_password_secuencial


class PasswordSecuencialTests(unittest.TestCase):
    def test_genera_seis_digitos_consecutivos(self):
        self.assertEqual(generar_password_secuencial(1), "000001")
        self.assertEqual(generar_password_secuencial(42), "000042")
        self.assertEqual(generar_password_secuencial(999999), "999999")

    def test_rechaza_indices_fuera_del_rango(self):
        with self.assertRaises(ValueError):
            generar_password_secuencial(0)

        with self.assertRaises(ValueError):
            generar_password_secuencial(1000000)


if __name__ == "__main__":
    unittest.main()
