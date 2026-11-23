"""
aprendizaje.py  -  Algoritmos de aprendizaje no-regret para los agentes.

Este archivo NO sabe nada de carros ni de OpenGL. Solo sabe esto:
    "tengo N acciones, elijo una, me dicen que tan mal me fue, y ajusto".
Por eso se puede probar solo:   python aprendizaje.py

Convencion: una PERDIDA siempre va de 0 (perfecto) a 1 (lo peor posible).

Algoritmos:
  Hedge       -> informacion completa: al final me dicen la perdida de TODAS las acciones
                 (como Waze: se cuanto hubiera tardado por cada ruta).
  FixedShare  -> Hedge que nunca olvida del todo una accion (para un mundo que cambia:
                 calles que se cierran y se vuelven a abrir).
  EXP3        -> informacion "bandit": solo conozco la perdida de la accion que tome
                 (si me pase el amarillo, no se que habria pasado si frenaba).
                 Con alfa > 0 tambien comparte peso como FixedShare (version EXP3.S).

Que significa "no-regret":
  regret = (mi perdida total) - (perdida total de la MEJOR accion fija, vista en retrospectiva)
  Un algoritmo es no-regret si  regret / T  ->  0  cuando el numero de rondas T crece.
  En palabras: a la larga, no me arrepiento de no haber usado siempre la mejor opcion.
"""
import math
import random


# =====================================================================
# Hedge (pesos exponenciales / multiplicative weights)
# =====================================================================
class Hedge:
    def __init__(self, n_acciones, eta=0.5):
        self.n = n_acciones
        self.eta = eta                      # tasa de aprendizaje: que tan fuerte castigo
        self.pesos = [1.0 / n_acciones] * n_acciones   # al inicio no prefiero ninguna

    def probabilidades(self):
        total = sum(self.pesos)
        return [w / total for w in self.pesos]

    def elegir(self):
        """sortea una accion: las de mas peso salen mas seguido (pero no siempre)"""
        return random.choices(range(self.n), weights=self.probabilidades())[0]

    def actualizar(self, perdidas):
        """perdidas = lista con la perdida de CADA accion en esta ronda (info completa).
        Regla de Hedge:  w_i  <-  w_i * e^(-eta * perdida_i)
        perdida 0 -> el peso no cambia;  perdida 1 -> el peso se multiplica por e^-eta."""
        for i in range(self.n):
            self.pesos[i] *= math.exp(-self.eta * perdidas[i])
        self._normalizar()

    def _normalizar(self):
        # solo para que los numeros no se hagan diminutos; no cambia las probabilidades
        total = sum(self.pesos)
        self.pesos = [w / total for w in self.pesos]


# =====================================================================
# Fixed-Share (Herbster & Warmuth): Hedge para un mundo que cambia
# =====================================================================
class FixedShare(Hedge):
    def __init__(self, n_acciones, eta=0.5, alfa=0.005):
        super().__init__(n_acciones, eta)
        self.alfa = alfa                    # fraccion de peso que se reparte cada ronda

    def actualizar(self, perdidas):
        super().actualizar(perdidas)        # 1) paso normal de Hedge (pesos ya suman 1)
        # 2) cada accion "dona" alfa de su peso y se reparte por igual entre todas.
        #    Asi ninguna accion baja de alfa/n: si el mundo cambia, se puede recuperar rapido.
        self.pesos = [(1 - self.alfa) * w + self.alfa / self.n for w in self.pesos]


# =====================================================================
# EXP3 (Auer et al.): solo conozco la perdida de lo que hice
# =====================================================================
class EXP3:
    def __init__(self, n_acciones, eta=0.3, gamma=0.04, alfa=0.0):
        self.n = n_acciones
        self.eta = eta
        self.gamma = gamma                  # exploracion: % de veces que pruebo algo al azar
        self.alfa = alfa                    # 0 = EXP3 normal;  > 0 = EXP3.S (comparte peso)
        self.pesos = [1.0 / n_acciones] * n_acciones

    def probabilidades(self):
        # mezcla: (1-gamma) lo que dicen mis pesos + gamma uniforme.
        # Sin exploracion, una accion que tuvo mala suerte una vez nunca se volveria a probar.
        total = sum(self.pesos)
        return [(1 - self.gamma) * w / total + self.gamma / self.n for w in self.pesos]

    def elegir(self):
        return random.choices(range(self.n), weights=self.probabilidades())[0]

    def actualizar(self, accion, perdida):
        """solo recibo la perdida de la accion que tome.
        Internamente trabajo con RECOMPENSA = 1 - perdida (como en el articulo original):
          w_accion  <-  w_accion * e^(eta * recompensa / p)
        Truco clave: divido entre la probabilidad p con que la elegi.
          - si casi nunca la elijo (p chica), cuando la elijo cuenta mucho
          - en promedio, la estimacion es igual a la recompensa real (estimador insesgado)
        Por que recompensas y no perdidas: con perdidas, la accion que mas uso es la que
        mas castigo recibe (solo a ella le llegan castigos) y algunos agentes se quedan
        atorados en la opcion mala por pura mala suerte. Con recompensas eso no pasa."""
        p = self.probabilidades()[accion]
        recompensa_estimada = (1.0 - perdida) / p
        self.pesos[accion] *= math.exp(self.eta * recompensa_estimada)
        total = sum(self.pesos)
        self.pesos = [w / total for w in self.pesos]
        if self.alfa > 0:
            self.pesos = [(1 - self.alfa) * w + self.alfa / self.n for w in self.pesos]


# =====================================================================
# Demostracion (juguete): 100 conductores, 2 rutas, y una calle que se cierra
# =====================================================================
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
