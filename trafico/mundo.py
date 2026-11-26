"""
Script del mundo con ap.model, instancia de carros.

"""

import agentpy as ap

from trafico.carro import Carro

from trafico.red import Red

from trafico.semaforo import Semaforo

class Mundo(ap.Model):
    def setup(self):
        """Se llama una vez al empezar: crear mapa"""
        self.red = Red()
        self.dt = self.p.get("dt", 0.1)
        
        
        self.semaforos = ap.AgentList(self, [
            Semaforo(self, nodo_id =n, desfase = self._desfase(n))
            for n in self.red.nodos if not self.red.es_glorieta(n)
        ])
        
        self.semaforo_de_nodo = {sem.nodo: sem for sem in self.semaforos}
        
        self.carros = ap.AgentList(self,
                                   self._colocar_carros(self.p.get("n_carros", 70)))
    def _desfase(self, nodo_id):
        """desfase de semaforos por intersecciones }"""
        i, j = map(int, nodo_id.split("_"))
        return (i+j) * 4.0
    def _colocar_carros(self, n):
        """reparte n carros al azar por la ciudad""" 
        aristas = list(self.red.aristas.values())
        ocupados = set()
        carros = []
        intentos = 0
        while len(carros) < n and intentos < 10000:
            intentos+=1
            a = self.random.choice(aristas)
            carril = self.random.randint(0,1)
            lugar = self.random.randint(0, int(a["longitud"] // 9) -1)
            if (a["id"], carril, lugar) in ocupados:
                continue
            ocupados.add((a["id"], carril, lugar))
            carros.append(Carro(self, arista=a,carril=carril, s=lugar * 9 + 2,
                                  v = self.random.uniform(5,10)))
        return carros
    def step(self):
        """paso de tiempo"""
        self.semaforos.step(self.dt)
        self.carros.step(self.dt, self.semaforo_de_nodo, self.carros)
    def update(self):
        """despues de cada paso anotar datos"""
        n = len(self.carros)
        self.record("segundos", self.t * self.dt)
        self.record("vel_promedio_km/h", sum(c.v for c in self.carros) / n * 3.6)
        self.record("parados", sum(1 for c in self.carros if c.v < 0.5))
        
        self.record("cruzando", sum(1 for c in self.carros if c.en_cruce()))
        
    def end(self):
        """al terminar: resultados finales"""
        self.report("carros", len(self.carros))
        self.report("semaforos", len(self.semaforos))

if __name__ == "__main__":
    parametros = {"n_carros": 80, "dt": 0.1, "steps": 600, "seed": 1}   # 600 pasos x 0.1 s = 60 s
    mundo = Mundo(parametros)
    resultados = mundo.run(display=False)
    datos = resultados.variables.Mundo          # tabla con todo lo que se anoto en update()
    print(datos.iloc[::100].round(1))           # una fila cada 100 pasos (cada 10 s)
    print()
    print(resultados.reporters)
    print("tiempo real:", resultados.info["run_time"])
                    