"""
carro.py - agente carrro

Estado del carro:
    arista, carril -> en que calle y carril va
    s -> metros recorridos (en la calle o sobre la curva si esta crurzando)
    v -> velocidad (m/s)
    cruce -> None si va en calle; si esta cruzando: la curva y la calle sig
    
    SIn OPENGL
"""

import random
import math

from trafico.red import Red, longitudes_acumuladas, punto_en_curva
from trafico.semaforo import AMARILLO, ROJO, Semaforo


class Carro:
    LARGO = 4.2 #metros
    
    A_MAX = 2.5
    B_COMODO = 4.0
    DIST_MIN = 2.5
    T_SEG = 1.2
    
    
    def __init__(self, red, arista, carril, s, v = 8.0):
        self.red = red
        self.arista = arista
        self.carril = carril
        self.s = s
        self.v = v
        self.cruce = None
        self.factor_vel = 1.0 # 1.0 respeta limite, 1.2 va mas rápido
        self.pos, self.yaw = red.punto_en_carril(arista, carril, s)
        
    def en_cruce(self):
        return self.cruce is not None
    
    #----paso del tiempo---
    
    def acel_idm(self, gap=None, v_lider=None):
        """Inteligent Driver Model: cuanto acelerar(+) o frenar(-) en m/s^2.
        gap = metros libres hasta lo que tengo enfrente (None 0 calle libre)
        v_lider = velocidad de lo que tengo frente"""
        v0 = self.arista["vel_max"] *  self.factor_vel
        libre = 1 - (self.v / v0) ** 4
        if gap is None:
            return self.A_MAX *  libre
        dv = self.v - v_lider
        
        s_deseada = self.DIST_MIN + max(0.0, self.v * self.T_SEG
                                        + self.v * dv / (2*  math.sqrt(self.A_MAX * self.B_COMODO)))
        return self.A_MAX * (libre - (s_deseada / max(gap, 0.1)) ** 2)
    
    def _acel_por_semaforo(self, semaforos):
        """si debo deterneme en la linea de alto; la acelereación para hacerlo"""
        if self.en_cruce():
            return None #ya crucé
        info = self.red.semaforo_de_arista(self.arista)
        if info is None: #glorieta
            return None
        
        estado = semaforos[info["interseccion"]].estado(info["grupo_fase"])
        restante = self.arista["longitud"] - self.s
        dist_frenado = self.v ** 2 / (2* self.B_COMODO)
        if estado == ROJO or (estado == AMARILLO and restante > dist_frenado + 1):
            return self.acel_idm(gap=restante, v_lider = 0.0)
        return None
        
    def step(self, dt, semaforos = None):
        acc = self.acel_idm()
        if semaforos:
            acc_sem = self._acel_por_semaforo(semaforos)
            if acc_sem is not None:
                acc = min(acc, acc_sem)
            
        self.v = max(0.0, self.v + acc * dt)
        self.s += self.v * dt
        if not self.en_cruce() and self.s >= self.arista["longitud"]:
            self._entrar_al_cruce()
        if self.en_cruce() and self.s >= self.cruce["acum"][-1]:
            self._salir_del_cruce()
        self._actualizar_pose()
        
    #----cambios de modo
    
    def _entrar_al_cruce(self):
        sobra = self.s - self.arista["longitud"]
        sig = random.choice(self.red.opciones_en_cruce(self.arista))
        
        pts = self.red.curva_en_cruce(self.arista, self.carril, sig, self.carril)
        self.cruce = {"pts": pts, "acum": longitudes_acumuladas(pts), "sig":sig}
        self.s = sobra
        
    def _salir_del_cruce(self):
        sobra = self.s - self.cruce["acum"][-1]
        self.arista = self.cruce["sig"]
        self.cruce = None
        self.s = sobra
    
    #--dibujarlo---
    
    def _actualizar_pose(self):
        if self.en_cruce():
            self.pos, self.yaw = punto_en_curva(self.cruce["pts"],
                                                self.cruce["acum"], self.s)
        else:
            self.pos, self.yaw = self.red.punto_en_carril(self.arista, self.carril, self.s)
if __name__ == "__main__":
    random.seed(3)
    red = Red()
    dt = 0.1
    # un agente semaforo por cada interseccion (menos la glorieta)
    semaforos = {n: Semaforo(n, desfase=14.0) for n in red.nodos if not red.es_glorieta(n)}
    carro = Carro(red, red.aristas["0_0->1_0"], carril=1, s=0.0, v=13.9)
    for paso in range(1, 301):
        carro.step(dt, semaforos)
        if paso % 10 == 0:
            if carro.en_cruce():
                donde = "cruzando"
            else:
                info = red.semaforo_de_arista(carro.arista)
                luz = "ninguna" if info is None else semaforos[info["interseccion"]].estado(info["grupo_fase"])
                donde = f"{carro.arista['id']}  luz={luz:<8} faltan {carro.arista['longitud'] - carro.s:4.1f} m"
            print(f"t={paso * dt:4.1f}s  v={carro.v:5.2f} m/s  {donde}")
        for sem in semaforos.values():
            sem.step(dt)                            # los semaforos tambien viven en el tiempo        
    
