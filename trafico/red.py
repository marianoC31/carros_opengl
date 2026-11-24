"""
    
red.py - La red vial de la ciudad como un graafo

Lee los datos de red_vial.json una sola vez y los acomoda para que los agentes
puedan preguntarle cosas rápido:

No usa OpenGL  
"""

import json
import os
import math

RUTA_RED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..","datos","red_vial.json")

def lerp(a,b,t):
    """punto entre a y b: t=0 -> a, t = 1 -> b, t=0.5 -> a la mitad"""
    return [a[k]+(b[k]-a[k])* t for k in range(3)]
class Red:
    def __init__(self, ruta= RUTA_RED):
        with open (ruta) as f:
            datos = json.load(f)
            
            
            #diccionarios id -> objeto, para encontrar cosas al instante por nombresinski
            
            self.nodos = {n["id"]: n for n in datos["nodos"]}
            self.aristas = {a["id"]: a for a in datos["aristas"]}
            self.glorieta = datos["glorieta"]
            
            #índices: para cada nodo las aristas que salen de el y las que 
            self.salientes = {nid: [] for nid in self.nodos}
            self.entrantes = {nid: [] for nid in self.nodos}
            
            for a in self.aristas.values():
                self.salientes[a["origen"]].append(a)
                self.entrantes[a["destino"]].append(a)
                
            # semaforos: indice id de arista -> semaforo que la controla
            # (las 4 calles que llegan a la glorieta No tienen semaforo)
                
            self.semaforos = datos["semaforos"]
            self.semaforo_de = {s["controla_arista"]: s for s in self.semaforos}    
                
    def opciones_en_cruce(self,arista):
        """calles que puedo tomar al final de la calle"""
        cruce = arista["destino"]
        opciones = [s for s in self.salientes[cruce] if s["destino"] != arista["origen"]]
        if not opciones:
            opciones = self.salientes[cruce]
        return opciones
    def semaforo_de_arista(self, arista):
        """en el semaforo al final de esta calle, o None si no tiene (glorieta)"""
        return self.semaforo_de.get(arista["id"])
    
    def es_glorieta(self, nodo_id):
        return self.nodos[nodo_id]["tipo"]=="glorieta"
    
    def punto_en_carril(self, arista, carril, s):
        """posicion (x,y,z) y orientacion (yaw, en grados) de un carro que lleva
        's' metros recorridos en el carril 'carril' (0 o 1) de arista"""
        c = arista["carriles"][carril]
        t = s / arista["longitud"]
        pos = lerp(c["inicio"], c["fin"], t)
        d = arista["direccion"]
        yaw = math.degrees(math.atan2(d[0], d[2]))
        return pos, yaw
#-----------------------------------
#Prueba rápida 
#-----------------------------------

if __name__ == "__main__":
    red = Red()
    print("nodos:", len(red.nodos))
    print("aristas:", len(red.aristas))
    for nodo in ("0_0", "1_0", "1_1", "2_2"):
        ids = [a["id"] for a in red.salientes[nodo]]
        print("de", nodo, "salen", len(ids), "calles:", ids)
    llegando = red.aristas["0_0->1_0"]
    print("llegando por", llegando["id"], "puedo tomar:", [a["id"] for a in red.opciones_en_cruce(llegando)])
    print("semaforos:", len(red.semaforos))
    for id_calle in ("0_0->1_0", "0_1->0_0","1_2->2_2"):
        sem = red.semaforo_de_arista(red.aristas[id_calle])
        if sem is None:
            print(id_calle, "-> sin semaforo (llego a glorieta)",
                  red.es_glorieta("2_2"))
        else:
            print(id_calle, "-> semaforo en el cruce", sem["interseccion"], "grupo", sem["grupo_fase"])
    calle = red.aristas["0_0->1_0"]
    for carril, s in ((1, 0), (1, 18.5), (1, 37), (0, 18.5)):
        pos, yaw = red.punto_en_carril(calle, carril, s)
        print("carril", carril, "a", s, "m ->", pos, "mirando a", yaw, "grados")