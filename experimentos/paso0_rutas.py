"""
Paso 0 - Juguete: 100 conductores, 2 rutas y una calle que se cierra.
Sirve para entender Hedge, FixedShare y EXP3 (trafico/aprendizaje.py) antes de meterlos a la ciudad.

  python experimentos/paso0_rutas.py
"""
import os
import random
import sys

# permite importar el paquete "trafico" aunque este script viva en la carpeta experimentos/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from trafico.aprendizaje import EXP3, FixedShare, Hedge  # noqa: E402

#   Ruta 0 = AVENIDA:  rapida pero se congestiona mucho  -> costo = 0.2 + 0.6 * (fraccion en avenida)
#   Ruta 1 = CALLE:    mas lenta pero aguanta mas        -> costo = 0.4 + 0.3 * (fraccion en calle)
#   Dias 100 a 199: la AVENIDA esta CERRADA -> quien la elige llega, da la vuelta: costo 1.0
#
#   Equilibrio (nadie gana cambiandose solo):
#     avenida abierta  -> 55.6% en avenida, costo 0.533 para todos
#     avenida cerrada  ->  0%   en avenida, costo 0.700
DIA_CIERRE, DIA_REAPERTURA, DIAS = 100, 200, 300


def costo_rutas(fraccion_avenida, avenida_cerrada):
    costo_avenida = 1.0 if avenida_cerrada else 0.2 + 0.6 * fraccion_avenida
    costo_calle = 0.4 + 0.3 * (1 - fraccion_avenida)
    return [costo_avenida, costo_calle]


def simular(crear_aprendiz, info_completa, n_conductores=100, semilla=1):
    random.seed(semilla)
    conductores = [crear_aprendiz() for _ in range(n_conductores)]
    mi_perdida = [0.0] * n_conductores      # para calcular el regret de cada conductor
    perdida_rutas = [0.0, 0.0]              # perdida acumulada si SIEMPRE hubiera ido por cada ruta
    historia = []
    for dia in range(DIAS):
        cerrada = DIA_CIERRE <= dia < DIA_REAPERTURA
        # 1) cada conductor decide (sin saber que haran los demas)
        elecciones = [c.elegir() for c in conductores]
        fraccion_avenida = elecciones.count(0) / n_conductores
        # 2) el "mundo" calcula cuanto costo cada ruta ese dia (depende de TODOS)
        costos = costo_rutas(fraccion_avenida, cerrada)
        # 3) cada conductor aprende de lo que paso
        for k, (c, e) in enumerate(zip(conductores, elecciones)):
            if info_completa:
                c.actualizar(costos)            # me entero del costo de ambas rutas
            else:
                c.actualizar(e, costos[e])      # solo se lo que me paso a mi
            mi_perdida[k] += costos[e]
        perdida_rutas[0] += costos[0]
        perdida_rutas[1] += costos[1]
        costo_promedio = sum(costos[e] for e in elecciones) / n_conductores
        historia.append((fraccion_avenida, costo_promedio))
    regret_promedio = sum(mi_perdida) / n_conductores - min(perdida_rutas)
    return historia, regret_promedio / DIAS


def demo():
    algoritmos = [
        # (nombre, como crear un conductor, recibe info completa?)
        ("Hedge", lambda: Hedge(2, eta=0.5), True),
        ("FixedShare", lambda: FixedShare(2, eta=0.5, alfa=0.005), True),
        ("EXP3", lambda: EXP3(2, eta=0.3, gamma=0.04), False),
        ("EXP3.S", lambda: EXP3(2, eta=0.3, gamma=0.04, alfa=0.003), False),
    ]
    resultados = [(nombre, *simular(f, info)) for nombre, f, info in algoritmos]

    print("Porcentaje de conductores en la AVENIDA (y costo promedio del dia)")
    print("Equilibrio: abierta = 55.6% / 0.533   cerrada = 0% / 0.700\n")
    print(f"{'dia':>4} {'avenida':>8} | " + " | ".join(f"{n:^14}" for n, _, _ in resultados))
    for dia in (0, 1, 2, 5, 10, 20, 50, 99, 100, 101, 103, 105, 110, 150, 199,
                200, 201, 205, 210, 220, 240, 260, 299):
        estado = "CERRADA" if DIA_CIERRE <= dia < DIA_REAPERTURA else "abierta"
        celdas = [f"{h[dia][0] * 100:5.1f}% {h[dia][1]:.3f}" for _, h, _ in resultados]
        print(f"{dia:>4} {estado:>8} | " + " | ".join(f"{c:^14}" for c in celdas))
    print("\nRegret promedio por dia (contra la mejor ruta fija en retrospectiva):")
    for nombre, _, r in resultados:
        print(f"  {nombre:<11} {r:+.4f}")


if __name__ == "__main__":
    demo()
