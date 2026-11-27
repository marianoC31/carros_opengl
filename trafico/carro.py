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
from trafico.colisiones import RADIO, circulos, se_tocan

class Carro(ap.Agent):
    LARGO = 4.2 #metros
    
    A_MAX = 2.5
    B_COMODO = 4.0
    DIST_MIN = 2.5
    T_SEG = 1.2
    T_CHOQUE = 10.0 #Segundos que se queda despues de chocar
    VISTA = 25.0 #metro de mi camino
    PASO_VISTA = 1.0
    
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
    def _mi_camino(self):
        """puntos de mi camino en los prox VISTA metros"""
        puntos = []
        d = self.PASO_VISTA
        while d <= self.VISTA:
            resto = self.s + d
            if not self.en_cruce():
                if resto <= self.arista["longitud"]:
                    p, _ = self.red.punto_en_carril(self.arista, self.carril, resto)
                    puntos.append((d,p[0],p[2]))
                    d += self.PASO_VISTA
                    continue
                resto -= self.arista["longitud"]
            curva = self.cruce if self.en_cruce() else self.plan
            if resto <= curva["acum"][-1]:
                
                p, _ = punto_en_curva(curva["pts"], curva["acum"], resto)
            else:
                sig = curva["sig"]
                p, _ = self.red.punto_en_carril(sig, self.carril, min(resto - curva["acum"][-1], sig["longitud"]))
            puntos.append((d,p[0],p[2]))
            d += self.PASO_VISTA
        return puntos
    
    def _ver_chocado(self, carros):
        """distancia libre hasta el primer chocado"""
        cercanos = [o for o in carros if o is not self and o.esta_chocado()
                    and math.dist(self.pos, o.pos) < self.VISTA + 3 and not se_tocan(self,o)]
        if not cercanos:
            return None
        for d, x, z in self._mi_camino():
            for o in cercanos:
                for q in circulos(o):
                    if math.dist((x,z),q) < 2 * RADIO:
                        return d - self.LARGO / 2 - RADIO
        return None 
    
    def step(self, dt, semaforos = None, carros = None):
        if self.esta_chocado():
            self.t_chocado = max(0.0, self.t_chocado -dt)
            return
        acc = self.acel_idm()
        if carros:
            gap, v_lider = self._ver_lider(carros)
            if gap is not None:
                acc = min(acc, self.acel_idm(gap, v_lider))
            gap_choque = self._ver_chocado(carros)
            if gap_choque is not None:
                acc = min(acc, self.acel_idm(gap_choque, 0.0))
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
    modelo = ap.Model()
    modelo.red = Red()
    modelo.random.seed(2)
    dt = 0.1
    # un carro que entra a la glorieta por el oeste...
    yo = Carro(modelo, arista=modelo.red.aristas["1_2->2_2"], carril=1, s=0.0, v=10.0)
    # ...y un carro que vino de OTRA calle y quedo chocado dentro de la glorieta, en mi camino
    otro = Carro(modelo, arista=modelo.red.aristas["2_3->2_2"], carril=1, s=0.0)
    otro.pos, otro.yaw = punto_en_curva(yo.plan["pts"], yo.plan["acum"], 12.0)
    otro.chocar()
    otro.t_chocado = 1000.0                         # que no se libere durante la prueba
    carros = [yo, otro]
    for paso in range(1, 121):
        yo.step(dt, carros=carros)
        if paso % 10 == 0:
            gap_viejo, _ = yo._ver_lider(carros)
            gap_nuevo = yo._ver_chocado(carros)
            donde = "glorieta" if yo.en_cruce() else f"calle, faltan {yo.arista['longitud'] - yo.s:4.1f} m"
            print(f"t={paso * dt:4.1f}s  v={yo.v:5.2f}  {donde:<22} lo ve _ver_lider: {gap_viejo}"
                  f"  | lo ve _ver_chocado: {None if gap_nuevo is None else round(gap_nuevo, 1)}")
    print("chocaron?", se_tocan(yo, otro))