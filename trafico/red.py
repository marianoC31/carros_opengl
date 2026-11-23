"""
    
red.py - La red vial de la ciudad como un graafo

Lee los datos de red_vial.json una sola vez y los acomoda para que los agentes
puedan preguntarle cosas rápido:

No usa OpenGL  
"""

import json
import os

RUTA_RED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..","datos","red_vial.json")

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
                
                
    def opciones_en_cruce(self,arista):
        """calles que puedo tomar al final de la calle"""
        cruce = arista["destino"]
        opciones = [s for s in self.salientes[cruce] if s["destino"] != arista["origen"]]
        if not opciones:
            opciones = self.salientes[cruce]
        return opciones
    
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