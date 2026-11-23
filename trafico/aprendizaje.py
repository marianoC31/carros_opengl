"""
aprendizaje.py  -  Algoritmos de aprendizaje no-regret para los agentes.

Este archivo NO sabe nada de carros ni de OpenGL. Solo sabe esto:
    "tengo N acciones, elijo una, me dicen que tan mal me fue, y ajusto".
La demo con 2 rutas y una calle cerrada esta en  experimentos/paso0_rutas.py

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
