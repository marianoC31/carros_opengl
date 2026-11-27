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
        self._planear_vuelta()
        
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
    
    def _planear_vuelta(self):
        """al entrar a una calle: decidir a donde voy a dar vuelta al final de ella"""
        opciones = self.red.opciones_en_cruce(self.arista)
        permitidas = [o for o in opciones if self._vuelta_permitida(o)]
        sig = self.model.random.choice(permitidas or opciones)     # por ahora al azar (luego: aprendiendo)
        pts = self.red.curva_en_cruce(self.arista, self.carril, sig, self.carril)
        self.plan = {"pts": pts, "acum": longitudes_acumuladas(pts), "sig": sig}

    def _vuelta_permitida(self, sig):
        """carril 0 (izquierdo): derecho o izquierda.  carril 1 (derecho): derecho o derecha"""
        d1, d2 = self.arista["direccion"], sig["direccion"]
        cruz = d1[0] * d2[2] - d1[2] * d2[0]
        if abs(cruz) < 1e-6:
            return True                     # seguir derecho: se puede desde cualquier carril
        if cruz > 0:
            return self.carril == 1         # vuelta a la derecha: solo desde el carril derecho
        return self.carril == 0             # vuelta a la izquierda: solo desde el carril izquierdo

    def _entrar_al_cruce(self):
        sobra = self.s - self.arista["longitud"]
        self.cruce = self.plan              # la curva ya estaba planeada
        self.s = sobra

    def _salir_del_cruce(self):
        sobra = self.s - self.cruce["acum"][-1]
        self.arista = self.cruce["sig"]
        self.cruce = None
        self.s = sobra
        self._planear_vuelta()              # calle nueva -> planear la siguiente vuelta
    #--dibujarlo---
    
    def _actualizar_pose(self):
        if self.en_cruce():
            self.pos, self.yaw = punto_en_curva(self.cruce["pts"],
                                                self.cruce["acum"], self.s)
        else:
            self.pos, self.yaw = self.red.punto_en_carril(self.arista, self.carril, self.s)
if __name__ == "__main__":
    import collections
    modelo = ap.Model()
    modelo.red = Red()
    modelo.random.seed(1)
    calle = modelo.red.aristas["1_1->2_1"]          # llega a 2_1: puede ir derecho, derecha o izquierda

    def tipo_de_vuelta(c):
        d1, d2 = c.arista["direccion"], c.plan["sig"]["direccion"]
        cruz = d1[0] * d2[2] - d1[2] * d2[0]
        if abs(cruz) < 1e-6:
            return "derecho"
        return "derecha" if cruz > 0 else "izquierda"

    for carril in (0, 1):
        cuenta = collections.Counter()
        for _ in range(300):
            c = Carro(modelo, arista=calle, carril=carril, s=0.0)     # setup ya planea su vuelta
            cuenta[tipo_de_vuelta(c)] += 1
        print("carril", carril, "->", dict(cuenta))