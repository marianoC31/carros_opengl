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
    
    def _distancia_a(self, o):
        """metros (de centro a centro) hasta el carro 'o' si va DELANTE de mi, en mi camino.
        
        Si no va en mi camino, None."""
        
        mismo_carril = o.carril == self.carril
        if not self.en_cruce():
            #yo voy en la calle
            if o.arista is self.arista and mismo_carril:
                if not o.en_cruce() and mismo_carril:
                    if not o.en_cruce() and o.s > self.s:
                        return o.s - self.s
                    if o.en_cruce():
                        return (self.arsita["longitud"] - self.s) + o 
                return None
            #yo voy en el cruce
        if o.en_cruce() and o.arista is self.arista and mismo_carril and o.s > self.s:
            return o.s - self.s
        if not o.en_cruce() and o.arista is self.cruce["sig"] and mismo_carril:
            return (self.cruce["acum"][-1] - self.s) + o.s 
        return None
        
    def _ver_lider(self, carros):
        """el carro mas cercano enfrente"""
        mas_cerca, v_lider = None, None
        for o in carros:
            if o is self:
                continue
            d = self._distancia_a(o)
            if d is not None and (mas_cerca is None or d < mas_cerca):
                mas_cerca, v_lider = d, o.v
        if mas_cerca is None:
            return None, None
        return mas_cerca - self.LARGO, v_lider
    
    
    def step(self, dt, semaforos = None, carros = None):
        acc = self.acel_idm()
        if carros:
            gap, v_lider = self._ver_lider(carros)
            if gap is not None:
                acc = min(acc, self.acel_idm(gap, v_lider))     
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
    random.seed(1)
    red = Red()
    dt = 0.1
    calle = red.aristas["0_0->1_0"]
    lento = Carro(red, calle, carril=1, s=25.0, v=5.0)
    lento.factor_vel = 5.0 / 13.9               # este conductor quiere ir a 5 m/s (18 km/h)
    rapido = Carro(red, calle, carril=1, s=0.0, v=13.9)
    carros = [lento, rapido]
    for paso in range(1, 151):
        for c in carros:
            c.step(dt, carros=carros)
        if paso % 10 == 0:
            gap, _ = rapido._ver_lider(carros)
            dist = "nadie enfrente" if gap is None else f"distancia libre {gap:5.1f} m"
            print(f"t={paso * dt:4.1f}s  rapido v={rapido.v:5.2f}  lento v={lento.v:4.2f}  {dist}")    
