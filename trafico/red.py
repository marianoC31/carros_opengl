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

def bezier(a, ctrl, b, n = 12):
    """Curva de Bezier cuadrática: sale de 'a', llega a 'b' y la 'jala' el punto
    'ctrl'.
        Regresa n+1 puntos sobre la curva
    """
    pts = []
    for k in range(n+1):
        u = k / n
        pts.append([(1-u) ** 2 * a[i] + 2 * (1-u) * u * ctrl[i] + u **2 *b[i] for i in range(3)])
        
    return pts

def longitudes_acumuladas(pts):
    """Para cada punto de la curva: cuantos metros hay desde el primer punto, siguiendo la curva"""
    acum = [0.0]
    for k in range(1, len(pts)):
        acum.append(acum[-1] + math.dist(pts[k-1], pts[k]))
    return acum

def punto_en_curva(pts,acum,s):
    """posicion (x,y,z) y yaw de un carro que lleva 's' metros recorridos
    sobre la curva 'pts'"""
    
    s = max(0.0, min(s, acum[-1]))
    for k in range(1, len(pts)):
        if s <= acum[k]:
            
            tramo = max(acum[k] - acum[k-1], 1e-9)
            t = (s - acum[k-1]) / tramo
            
            pos = lerp(pts[k-1], pts[k], t)
            d = [pts[k][i] - pts[k-1][i] for i in range(3)]
            
            yaw = math.degrees(math.atan2(d[0], d[2]))
            return pos, yaw
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
    
    def curva_en_cruce(self, arista, carril, sig, carril_sig):
        """puntos que recorre un carro DENTRO del cruce: desde la linea de alto de 'arista'
            (en su 'carril') hasta el incio de la calle 'sig' (en 'carril_sig')
        """
        a = arista["carriles"][carril]["fin"]
        b = sig["carriles"][carril_sig]["inicio"]
        
        if self.es_glorieta(arista["destino"]):
            return self.curva_glorieta(a,b)
        
        d1, d2 = arista["direccion"], sig["direccion"]
        cruz = d1[0] * d2[2] - d1[2] * d2[0]
        
        if abs(cruz) < 1e-6:
                #sigo derecho no hay esquina
            ctrl = lerp(a,b,0.5)
        else:
            #doy vuelta: el control es la esquina donde se cruzan las lines del carril
            t = ((b[0]-a[0]) * d2[2] - (b[2] - a[2]) * d2[0]) / cruz
            ctrl = [a[0] + d1[0] * t, 0.0, a[2] + d1[2] * t]
            
        return bezier(a, ctrl, b)
    
    def curva_glorieta(self, a, b):
        """arco alrededor de la isla, en sentido antihorario, desde la entrada 'a'
        hasta la salida 'b'"""
        cx,_, cz = self.glorieta["centro"]
        r = self.glorieta["radios_carriles"][1] # radio del carril exterior
        ang_a = math.atan2(a[2] - cz, a[0] - cx) #angulo de la entrada
        ang_b = math.atan2(b[2] - cz, b[0] - cx) # angulo de la salida
        #cuando hay que girar el ángulo disminuye.
        #ang_a - ang_b %2pi lo deja entre 0 y una vuelta completa 
        giro = (ang_a - ang_b) % (2 * math.pi)
        if giro < 0.3:
            #salida junto a la entrada hay que dar la vuelta entera
            
            giro += 2 * math.pi
        n = max(4, int(giro*8))
        pts = [a]
        for k in range(n + 1):
            ang = ang_a - giro* k/ n
            pts.append([cx + r * math.cos(ang), 0.0, cz + r * math.sin(ang)])
        pts.append(b)
        return pts
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
    for id_sig, nombre in (("1_0->2_0", "derecho"), ("1_0->1_1", "vuelta")):
        pts = red.curva_en_cruce(calle, 1, red.aristas[id_sig], 1)
        mitad = [round(v, 2) for v in pts[6]]
        print(nombre, "->", len(pts), "puntos | inicio", pts[0], "| mitad", mitad, "| fin", pts[-1])
    entrada = red.aristas["1_2->2_2"]
    for id_sig, nombre in (("2_2->2_3", "derecha"), ("2_2->3_2", "derecho"), ("2_2->2_1", "izquierda")):
        pts = red.curva_en_cruce(entrada, 1, red.aristas[id_sig], 1)
        acum = longitudes_acumuladas(pts)
        print("glorieta", nombre, "->", len(pts), "puntos, mide", round(acum[-1], 1), "m")
        
        