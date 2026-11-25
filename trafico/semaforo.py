"""
semaforo.py - el agente semaforo.

Cada interseccion con semaforos tiene UN agente que controla sus dos grupos
de luces:
    grupo "x" -> calles este-oeste
    grupo "y" -> calles norte-sur
    
Nunca estan los dos en verde al mismo tiempo.

SIN OPENGL
"""
import agentpy as ap
VERDE, AMARILLO, ROJO = "verde", "amarillo", "rojo"

#duracion de cada fase

T_VERDE = 12.0
T_AMARILLO = 3.0
T_TODO_ROJO = 1.5
CICLO = 2 * (T_VERDE + T_AMARILLO + T_TODO_ROJO) #33s

class Semaforo(ap.Agent):
    def setup(self, nodo_id, desfase = 0.0):
        self.id = nodo_id
        self.t = desfase % CICLO
        
    def step(self, dt):
        """pasaron dt segundos: avanzar el reloj (y dar la vuelta al llegar a 33)"""
        self.t = (self.t + dt) % CICLO

    def estado(self, grupo):
        """color de la luz para el grupo 'x' o 'z'"""
        if grupo == "x":
            t = self.t
        else:
            t = (self.t+CICLO / 2) % CICLO #grupo z medio ciclo adelantado
        if t < T_VERDE:
            return VERDE
        if t < T_VERDE + T_AMARILLO:
            return AMARILLO
        return ROJO 

if __name__ == "__main__":
    modelo = ap.Model()                     # todo agente vive dentro de un modelo
    sem = Semaforo(modelo, nodo_id="1_1")
    print("semaforo del cruce", sem.nodo, "| id de agentpy:", sem.id)
    print("ciclo completo:", CICLO, "s")
    print(" t(s)   grupo x    grupo z")
    for k in range(23):
        print(f"{sem.t:5.1f}   {sem.estado('x'):<9}  {sem.estado('z')}")
        sem.step(1.5)    