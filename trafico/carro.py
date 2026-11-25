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

from red import Red, longitudes_acumuladas, punto_en_curva


class Carro:
    LARGO = 4.2 #metros
    
    def __init__(self, red, arista, carril, s, v = 8.0):
        self.red = red
        self.arista = arista
        self.carril = carril
        self.s = s
        self.v = v
        self.cruce = None
        self.pos, self.yaw = red.punto_en_carril(arista, carril, s)
        
    def en_cruce(self):
        return self.cruce is not None
    
    #----paso del tiempo---
    
    def step(self, dt):
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
    carro = Carro(red, red.aristas["0_0->1_0"], carril=1, s=0.0, v=10.0)
    dt = 0.5
    antes = None
    for paso in range(1, 61):                       # 60 pasos de 0.5 s = 30 segundos
        carro.step(dt)
        if carro.en_cruce():
            donde = "cruzando hacia " + carro.cruce["sig"]["id"]
        else:
            donde = "en la calle " + carro.arista["id"]
        if donde != antes:                          # solo imprimir cuando cambia de lugar
            print(f"t={paso * dt:5.1f}s  {donde:<28} pos={[round(c, 1) for c in carro.pos]}")
            antes = donde          
        
        
    
