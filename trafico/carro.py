"""
carro.py - agente carrro

Estado del carro:
    arista, carril -> en que calle y carril va
    s -> metros recorridos (en la calle o sobre la curva si esta crurzando)
    v -> velocidad (m/s)
    cruce -> None si va en calle; si esta cruzando: la curva y la calle sig
    
    SIn OPENGL
"""

import math
import agentpy as ap

from trafico.red import Red, longitudes_acumuladas, punto_en_curva
from trafico.semaforo import AMARILLO, ROJO, Semaforo


class Carro(ap.Agent):
    LARGO = 4.2 #metros
    
    A_MAX = 2.5
    B_COMODO = 4.0
    DIST_MIN = 2.5
    T_SEG = 1.2
    T_CHOQUE = 10.0 #Segundos que se queda despues de chocar
    
    def setup(self, arista, carril, s, v = 8.0):
        self.red = self.model.red
        self.arista = arista
        self.carril = carril
        self.s = s
        self.v = v
        self.cruce = None
        self.t_chocado = 0.0
        self.choques = 0
        self.factor_vel = 1.0 # 1.0 respeta limite, 1.2 va mas rápido
        self.pos, self.yaw = self.red.punto_en_carril(arista, carril, s)
    
    def chocar(self):
        """el mudno avisa que chocaste: se detiene y esperas T_CHOQUE"""
        
        self.choques += 1
        self.t_chocado = self.T_CHOQUE
        self.v = 0.0
        
    def esta_chocado(self):
        return self.t_chocado>0
     
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
                if not o.en_cruce() and o.s > self.s:
                    return o.s - self.s
                if o.en_cruce():
                    return (self.arista["longitud"] - self.s) + o.s 
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
        if self.esta_chocado():
            self.t_chocado = max(0.0, self.t_chocado -dt)
            return
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
        sig = self.model.random.choice(self.red.opciones_en_cruce(self.arista))
        
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
    modelo = ap.Model()
    modelo.red = Red()
    modelo.random.seed(1)
    dt = 0.1
    calle = modelo.red.aristas["0_0->1_0"]
    adelante = Carro(modelo, arista=calle, carril=1, s=20.0, v=8.0)
    atras = Carro(modelo, arista=calle, carril=1, s=5.0, v=8.0)
    carros = [adelante, atras]
    for paso in range(1, 161):
        if paso == 10:
            adelante.chocar()                   # simulamos que el de adelante choco
            print("   *** t=1.0s: el de adelante choca ***")
        for c in carros:
            c.step(dt, carros=carros)
        if paso % 10 == 0:
            gap, _ = atras._ver_lider(carros)
            estado = f"CHOCADO (faltan {adelante.t_chocado:4.1f} s)" if adelante.esta_chocado() else "libre"
            print(f"t={paso * dt:4.1f}s  adelante v={adelante.v:5.2f} {estado:<24} atras v={atras.v:5.2f}  distancia {gap:5.1f} m")
    print("choques: adelante", adelante.choques, "| atras", atras.choques)