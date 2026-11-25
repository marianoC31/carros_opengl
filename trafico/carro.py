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
    def step(self, dt):
        acc = self.acel_idm()
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
    red = Red()
    dt = 0.1
    print("1) arrancando desde 0, calle libre (limite 13.9 m/s = 50 km/h):")
    carro = Carro(red, red.aristas["0_0->1_0"], carril=1, s=0.0, v=0.0)
    for paso in range(1, 151):
        carro.step(dt)
        if paso % 10 == 0:
            print(f"   t={paso * dt:4.1f}s  v={carro.v:5.2f} m/s  ({carro.v * 3.6:4.1f} km/h)")

    print("2) a 50 km/h, hay un carro DETENIDO 60 m adelante:")
    carro = Carro(red, red.aristas["0_0->1_0"], carril=1, s=0.0, v=13.9)
    x = 0.0
    for paso in range(1, 151):
        acc = carro.acel_idm(gap=60.0 - x, v_lider=0.0)
        carro.v = max(0.0, carro.v + acc * dt)
        x += carro.v * dt
        if paso % 10 == 0:
            print(f"   t={paso * dt:4.1f}s  v={carro.v:5.2f} m/s  acel={acc:6.2f} m/s2  distancia libre={60.0 - x:5.1f} m")        
        
    
