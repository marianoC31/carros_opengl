"""
Colisiones.py - detecta cuando dos carron se tocan

Cada carro se aproxima con DOS circulos (como abeja):
dos carros se tocan si algun circulo de uno toca alguno de otro.

Sin OpenGL 
"""

import math

RADIO = 0.95 #medio carro 1.9m/2
SEPARACION = 1.1
DIST_REVISAR = 6.0

def circulos(c):
    """centro (x,z) de los dos ciruclos del carro 'c'"""
    yaw = math.radians(c.yaw)
    dx, dz = math.sin(yaw), math.cos(yaw)
    x, y, z = c.pos
    return [ (x + dx * SEPARACION, z + dz * SEPARACION),
            (x- dx * SEPARACION, z - dz * SEPARACION)]
    
def se_tocan(a,b):
    """True si los carros 'a' y 'b' se estan tocando"""
    if math.dist(a.pos, b.pos) > DIST_REVISAR:
        return False
    for p in circulos(a):
        for q in circulos(b):
            if math.dist(p,q) < 2*RADIO:
                return True
    return False

def detectar_contactos(carros):
    
    """todas las parejas de carros que se estan tocando"""
    lista = list(carros)
    contactos = set()
    
    for i in range(len(lista)):
        for j in range(i+1, len(lista)):
            a, b = lista[i], lista[j]
            if se_tocan(a,b):
                contactos.add((min(a.id,b.id), max(a.id, b.id)))
    return contactos


if __name__ == "__main__":
    import agentpy as ap
    from trafico.carro import Carro
    from trafico.mundo import Mundo
    from trafico.red import Red

    modelo = ap.Model()
    modelo.red = Red()
    calle = modelo.red.aristas["0_0->1_0"]

    def caso(nombre, a, b):
        print(f"{nombre:<48} centros a {math.dist(a.pos, b.pos):4.1f} m -> chocan: {se_tocan(a, b)}")

    caso("1) uno detras del otro, 2.5 m defensa a defensa",
         Carro(modelo, arista=calle, carril=1, s=10.0), Carro(modelo, arista=calle, carril=1, s=16.7))
    caso("2) uno detras del otro, encimados 1 m",
         Carro(modelo, arista=calle, carril=1, s=10.0), Carro(modelo, arista=calle, carril=1, s=13.2))
    caso("3) lado a lado, en carriles vecinos",
         Carro(modelo, arista=calle, carril=0, s=10.0), Carro(modelo, arista=calle, carril=1, s=10.0))
    a = Carro(modelo, arista=calle, carril=1, s=30.0)
    b = Carro(modelo, arista=calle, carril=1, s=30.0)
    b.pos = [a.pos[0] + 1.5, 0.0, a.pos[2]]     # lo movemos a mano 1.5 m adelante...
    b.yaw = 0.0                                 # ...y lo giramos de lado
    caso("4) uno de lado contra la puerta del otro (en T)", a, b)

    # en la ciudad: cuantos choques NUEVOS hay en 5 minutos (todavia sin consecuencias)
    mundo = Mundo({"n_carros": 80, "dt": 0.1, "seed": 1})
    mundo.sim_setup()
    antes = set()
    total = 0
    for paso in range(1, 3001):
        mundo.sim_step()
        ahora = detectar_contactos(mundo.carros)
        nuevos = ahora - antes                  # parejas que se tocan ahora pero NO se tocaban antes
        total += len(nuevos)
        antes = ahora
        if paso % 600 == 0:
            print(f"t={paso * 0.1:5.0f}s  tocandose ahora: {len(ahora):2d}  choques nuevos acumulados: {total}")