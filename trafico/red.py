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
            
#-----------------------------------
#Prueba rápida 
#-----------------------------------

if __name__ == "__main__":
    red = Red()
    print("nodos:", len(red.nodos))
    print("aristas:", len(red.aristas))
    a = red.aristas["0_0->1_0"]
    print("la calle", a["id"], "mide", a["longitud"], "m y su velocidad máxima es", a["vel_max"], "m/s")