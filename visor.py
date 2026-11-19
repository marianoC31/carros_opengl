"""
Visor + simulacion multiagente basica (Python + PyOpenGL + pygame).
  pip install pygame PyOpenGL
  python visor.py                      # ventana interactiva
  python visor.py --carros 80          # cantidad de autos
Controles: flechas = orbitar camara, W/S = acercar/alejar, A/D = subir/bajar, ESPACIO = pausa, ESC = salir

Agentes:
  * Semaforo  -> ciclo de fases por interseccion (eje X / eje Z), con desfase entre intersecciones
  * Carro     -> sigue su carril, guarda distancia con el de enfrente, frena en rojo/amarillo,
                 cambia de carril si el de enfrente va lento, decide ruta al llegar a cada interseccion,
                 y circula la glorieta en sentido antihorario.
"""
import argparse, json, math, random, sys
import pygame
from pygame.locals import DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_SPACE
from OpenGL.GL import *


# =====================================================================
# Cargador OBJ -> display lists de OpenGL
# =====================================================================
class ObjModel:
    def __init__(self, ruta):
        self.mats = {}
        self.grupos = {}          # material -> lista de (normal, (v0, v1, v2))
        base = ruta.rsplit("/", 1)[0] + "/" if "/" in ruta else ""
        V, N = [], []
        mat = None
        for linea in open(ruta):
            p = linea.split()
            if not p:
                continue
            if p[0] == "mtllib":
                self._leer_mtl(base + p[1])
            elif p[0] == "v":
                V.append(tuple(map(float, p[1:4])))
            elif p[0] == "vn":
                N.append(tuple(map(float, p[1:4])))
            elif p[0] == "usemtl":
                mat = p[1]
                self.grupos.setdefault(mat, [])
            elif p[0] == "f":
                vs, ns = [], []
                for t in p[1:]:
                    partes = t.split("/")
                    vs.append(V[int(partes[0]) - 1])
                    ns.append(N[int(partes[2]) - 1] if len(partes) > 2 and partes[2] else None)
                for k in range(1, len(vs) - 1):     # triangula poligonos
                    self.grupos[mat].append((ns[0], (vs[0], vs[k], vs[k + 1])))

    def _leer_mtl(self, ruta):
        actual = None
        for linea in open(ruta):
            p = linea.split()
            if not p:
                continue
            if p[0] == "newmtl":
                actual = p[1]
                self.mats[actual] = (0.8, 0.8, 0.8)
            elif p[0] == "Kd":
                self.mats[actual] = tuple(map(float, p[1:4]))

    def compilar(self, materiales=None, con_color=True):
        """display list con los materiales indicados (None = todos).
        con_color=False -> no fija el color, se usa el glColor actual (para pintar cada auto distinto)."""
        lista = glGenLists(1)
        glNewList(lista, GL_COMPILE)
        glBegin(GL_TRIANGLES)
        for mat, tris in self.grupos.items():
            if materiales is not None and mat not in materiales:
                continue
            if con_color:
                glColor3f(*self.mats.get(mat, (0.8, 0.8, 0.8)))
            for n, (a, b, c) in tris:
                if n:
                    glNormal3f(*n)
                glVertex3f(*a); glVertex3f(*b); glVertex3f(*c)
        glEnd()
        glEndList()
        return lista


# =====================================================================
# Agentes
# =====================================================================
VERDE, AMARILLO, ROJO = "verde", "amarillo", "rojo"
T_VERDE, T_AMARILLO, T_TODO_ROJO = 12.0, 3.0, 1.5
CICLO = 2 * (T_VERDE + T_AMARILLO + T_TODO_ROJO)


class AgenteSemaforo:
    """Controla una interseccion: fase 'x' (calles en eje X) y fase 'z'."""
    def __init__(self, nodo_id, desfase):
        self.id = nodo_id
        self.t = desfase

    def step(self, dt):
        self.t = (self.t + dt) % CICLO

    def estado(self, eje):
        t = self.t if eje == "x" else (self.t + CICLO / 2) % CICLO
        if t < T_VERDE:
            return VERDE
        if t < T_VERDE + T_AMARILLO:
            return AMARILLO
        return ROJO


def lerp(a, b, t):
    return [a[k] + (b[k] - a[k]) * t for k in range(3)]


def polilinea_longitudes(pts):
    acum = [0.0]
    for k in range(1, len(pts)):
        acum.append(acum[-1] + math.dist(pts[k - 1], pts[k]))
    return acum


def punto_en_polilinea(pts, acum, s):
    s = max(0.0, min(s, acum[-1]))
    for k in range(1, len(acum)):
        if s <= acum[k]:
            t = (s - acum[k - 1]) / max(1e-9, acum[k] - acum[k - 1])
            p = lerp(pts[k - 1], pts[k], t)
            d = [pts[k][i] - pts[k - 1][i] for i in range(3)]
            return p, math.degrees(math.atan2(d[0], d[2]))
    d = [pts[-1][i] - pts[-2][i] for i in range(3)]
    return list(pts[-1]), math.degrees(math.atan2(d[0], d[2]))


class AgenteCarro:
    LARGO = 4.2
    RADIO_LLANTA = 0.35
    LLANTAS_POS = ((-0.95, 0.35, 1.3), (0.95, 0.35, 1.3), (-0.95, 0.35, -1.3), (0.95, 0.35, -1.3))
    DIST_MIN = 2.5          # separacion minima (m)
    T_SEG = 1.2             # tiempo de seguridad (s)
    A_MAX, B_COMODO = 2.5, 4.0

    def __init__(self, sim, arista, carril, s, color):
        self.sim = sim
        self.arista, self.carril, self.s = arista, carril, s
        self.v = random.uniform(5, 10)
        self.vmax = arista["vel_max"] * random.uniform(0.8, 1.1)
        self.color = color
        self.en_cruce = None      # (pts, acum, arista_sig, carril_sig) mientras cruza la interseccion
        self.cambio = 1.0         # 0..1 progreso visual del cambio de carril
        self.carril_prev = carril
        self.pos, self.yaw = [0, 0, 0], 0.0
        self.ang_llanta, self.steer = 0.0, 0.0

    # ---------- percepcion ----------
    def lider(self):
        """distancia y velocidad del auto de enfrente en el mismo carril (o en su cruce)"""
        mejor, vel = 1e9, None
        for o in self.sim.carros:
            if o is self:
                continue
            if self.en_cruce:
                if o.en_cruce and o.en_cruce[2] is self.en_cruce[2] and o.en_cruce[3] == self.en_cruce[3] and o.s > self.s:
                    d = o.s - self.s
                elif o.arista is self.en_cruce[2] and o.carril == self.en_cruce[3] and not o.en_cruce:
                    d = (self.en_cruce[1][-1] - self.s) + o.s
                else:
                    continue
            else:
                if o.arista is self.arista and o.carril == self.carril and not o.en_cruce and o.s > self.s:
                    d = o.s - self.s
                else:
                    continue
            if d < mejor:
                mejor, vel = d, o.v
        return mejor - self.LARGO, vel

    def hueco_en(self, carril):
        adelante, atras = 1e9, 1e9
        for o in self.sim.carros:
            if o is self or o.en_cruce or o.arista is not self.arista or o.carril != carril:
                continue
            d = o.s - self.s
            if d >= 0:
                adelante = min(adelante, d)
            else:
                atras = min(atras, -d)
        return adelante, atras

    # ---------- decision ----------
    def acel_idm(self, gap, v_lider):
        """Intelligent Driver Model (simplificado)"""
        libre = 1 - (self.v / self.vmax) ** 4
        if v_lider is None:
            return self.A_MAX * libre
        dv = self.v - v_lider
        s_star = self.DIST_MIN + max(0, self.v * self.T_SEG + self.v * dv / (2 * math.sqrt(self.A_MAX * self.B_COMODO)))
        return self.A_MAX * (libre - (s_star / max(gap, 0.1)) ** 2)

    def elegir_siguiente(self):
        """decision de ruta: al azar entre las aristas salientes (sin vuelta en U)"""
        destino = self.arista["destino"]
        opciones = [a for a in self.sim.salientes[destino] if a["destino"] != self.arista["origen"]]
        return random.choice(opciones or self.sim.salientes[destino])

    def construir_cruce(self, sig, carril_sig):
        a = self.arista["carriles"][self.carril]["fin"]
        b = sig["carriles"][carril_sig]["inicio"]
        nodo = self.sim.nodos[self.arista["destino"]]
        if nodo["tipo"] == "glorieta":
            g = self.sim.red["glorieta"]
            cx, _, cz = g["centro"]
            r = g["radios_carriles"][1]
            t0 = math.atan2(a[2] - cz, a[0] - cx)
            t1 = math.atan2(b[2] - cz, b[0] - cx)
            dt = (t0 - t1) % (2 * math.pi)        # sentido antihorario visto desde arriba = theta decrece
            if dt < 0.3:
                dt += 2 * math.pi
            pts = [a]
            n = max(4, int(dt * 8))
            for k in range(n + 1):
                th = t0 - dt * k / n
                pts.append([cx + r * math.cos(th), 0.0, cz + r * math.sin(th)])
            pts.append(b)
        else:
            # curva de Bezier cuadratica; el punto de control es el cruce de las dos rectas de carril
            d1, d2 = self.arista["direccion"], sig["direccion"]
            cruz = d1[0] * d2[2] - d1[2] * d2[0]
            if abs(cruz) < 1e-6:     # recto
                ctrl = lerp(a, b, 0.5)
            else:
                t = ((b[0] - a[0]) * d2[2] - (b[2] - a[2]) * d2[0]) / cruz
                ctrl = [a[0] + d1[0] * t, 0.0, a[2] + d1[2] * t]
            pts = []
            for k in range(13):
                u = k / 12
                pts.append([(1 - u) ** 2 * a[i] + 2 * (1 - u) * u * ctrl[i] + u * u * b[i] for i in range(3)])
        return pts, polilinea_longitudes(pts), sig, carril_sig

    def step(self, dt):
        gap, v_lider = self.lider()
        acc = self.acel_idm(gap, v_lider)

        if not self.en_cruce:
            L = self.arista["longitud"]
            restante = L - self.s
            # semaforo: tratar la linea de alto como un auto detenido
            sem = self.sim.semaforo_de(self.arista)
            if sem:
                estado = sem.estado(self.sim.eje_de[self.arista["id"]])
                frenado = self.v * self.v / (2 * self.B_COMODO)
                if estado == ROJO or (estado == AMARILLO and restante > frenado + 1):
                    acc = min(acc, self.acel_idm(restante - 0.5, 0.0))
            elif self.sim.nodos[self.arista["destino"]]["tipo"] == "glorieta":
                acc = min(acc, self.A_MAX * (1 - (self.v / 7.0) ** 2))   # reducir para entrar a la glorieta

            # cambio de carril si el de enfrente va lento
            if self.cambio >= 1.0 and v_lider is not None and gap < 20 and v_lider < self.v - 0.5 and 10 < self.s < L - 20:
                otro = 1 - self.carril
                adelante, atras = self.hueco_en(otro)
                if adelante > gap + 10 and atras > 12:
                    self.carril_prev, self.carril, self.cambio = self.carril, otro, 0.0

        self.v = max(0.0, self.v + acc * dt)
        self.s += self.v * dt
        self.cambio = min(1.0, self.cambio + dt / 2.0)

        if not self.en_cruce and self.s >= self.arista["longitud"]:
            sobra = self.s - self.arista["longitud"]
            sig = self.elegir_siguiente()
            self.en_cruce = self.construir_cruce(sig, self.carril)
            self.s = sobra
            self.cambio = 1.0
        if self.en_cruce and self.s >= self.en_cruce[1][-1]:
            sobra = self.s - self.en_cruce[1][-1]
            _, _, sig, carril = self.en_cruce
            self.arista, self.carril, self.carril_prev, self.s = sig, carril, carril, sobra
            self.en_cruce = None

        yaw_prev = self.yaw
        self._actualizar_pose()
        self.ang_llanta = (self.ang_llanta + math.degrees(self.v * dt / self.RADIO_LLANTA)) % 360.0
        dyaw = (self.yaw - yaw_prev + 180.0) % 360.0 - 180.0
        objetivo = max(-30.0, min(30.0, (dyaw / dt) * 0.6)) if dt > 0 and self.v > 0.2 else 0.0
        self.steer += (objetivo - self.steer) * min(1.0, 10.0 * dt)

    def _actualizar_pose(self):
        if self.en_cruce:
            self.pos, self.yaw = punto_en_polilinea(self.en_cruce[0], self.en_cruce[1], self.s)
            return
        L = self.arista["longitud"]
        u = self.s / L
        c_new = self.arista["carriles"][self.carril]
        c_old = self.arista["carriles"][self.carril_prev]
        p_new = lerp(c_new["inicio"], c_new["fin"], u)
        p_old = lerp(c_old["inicio"], c_old["fin"], u)
        k = 0.5 - 0.5 * math.cos(math.pi * self.cambio)
        self.pos = lerp(p_old, p_new, k)
        d = self.arista["direccion"]
        self.yaw = math.degrees(math.atan2(d[0], d[2]))
        if k < 1:   # inclinar un poco el auto mientras cambia de carril
            lado = 1 if self.carril > self.carril_prev else -1
            self.yaw -= lado * 8 * math.sin(math.pi * k)


# =====================================================================
# Simulacion
# =====================================================================
class Simulacion:
    COLORES = [(0.8, 0.1, 0.1), (0.1, 0.3, 0.8), (0.9, 0.9, 0.9), (0.15, 0.15, 0.15),
               (0.95, 0.75, 0.1), (0.2, 0.6, 0.3), (0.6, 0.6, 0.65), (0.5, 0.1, 0.5)]

    def __init__(self, red, n_carros):
        self.red = red
        self.nodos = {n["id"]: n for n in red["nodos"]}
        self.salientes = {}
        for a in red["aristas"]:
            self.salientes.setdefault(a["origen"], []).append(a)
        self.eje_de = {}
        self.sem_de_arista = {}
        self.semaforos = {}
        for n in red["nodos"]:
            if n["tipo"] == "semaforo":
                i, j = map(int, n["id"].split("_"))
                self.semaforos[n["id"]] = AgenteSemaforo(n["id"], desfase=(i + j) * 4.0)   # "onda verde"
        for s in red["semaforos"]:
            self.eje_de[s["controla_arista"]] = s["grupo_fase"]
            self.sem_de_arista[s["controla_arista"]] = self.semaforos[s["interseccion"]]
        # colocar autos sin que se encimen
        self.carros = []
        ocupados = set()
        intentos = 0
        while len(self.carros) < n_carros and intentos < 10000:
            intentos += 1
            a = random.choice(red["aristas"])
            carril = random.randint(0, 1)
            s = random.uniform(2, a["longitud"] - 8)
            celda = (a["id"], carril, int(s // 9))
            if celda in ocupados:
                continue
            ocupados.add(celda)
            self.carros.append(AgenteCarro(self, a, carril, (s // 9) * 9 + 2, random.choice(self.COLORES)))

    def semaforo_de(self, arista):
        return self.sem_de_arista.get(arista["id"])

    def step(self, dt):
        for s in self.semaforos.values():
            s.step(dt)
        random.shuffle(self.carros)
        for c in self.carros:
            c.step(dt)


# =====================================================================
# Render
# (perspectiva y camara sin GLU, para no depender de libGLU)
def perspectiva(fovy, aspecto, cerca, lejos):
    h = cerca * math.tan(math.radians(fovy) / 2)
    glFrustum(-h * aspecto, h * aspecto, -h, h, cerca, lejos)


def mirar_a(ojo, centro, arriba):
    f = [centro[i] - ojo[i] for i in range(3)]
    n = math.sqrt(sum(x * x for x in f)); f = [x / n for x in f]
    s = [f[1] * arriba[2] - f[2] * arriba[1], f[2] * arriba[0] - f[0] * arriba[2], f[0] * arriba[1] - f[1] * arriba[0]]
    n = math.sqrt(sum(x * x for x in s)); s = [x / n for x in s]
    u = [s[1] * f[2] - s[2] * f[1], s[2] * f[0] - s[0] * f[2], s[0] * f[1] - s[1] * f[0]]
    m = [s[0], u[0], -f[0], 0, s[1], u[1], -f[1], 0, s[2], u[2], -f[2], 0, 0, 0, 0, 1]
    glMultMatrixf(m)
    glTranslatef(-ojo[0], -ojo[1], -ojo[2])


# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carros", type=int, default=70)
    ap.add_argument("--ancho", type=int, default=1280)
    ap.add_argument("--alto", type=int, default=720)
    ap.add_argument("--captura", help="guardar una imagen y salir (para pruebas)")
    ap.add_argument("--segundos", type=float, default=20.0, help="tiempo simulado antes de la captura")
    ap.add_argument("--camara", default="45,35,260", help="angulo_y,angulo_elevacion,distancia")
    ap.add_argument("--foco", default="0,0,0", help="punto al que mira la camara x,y,z")
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_mode((args.ancho, args.alto), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Simulacion multiagente - ciudad")

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING); glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL); glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_NORMALIZE)
    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.35, 0.35, 0.38, 1))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.8, 0.8, 0.75, 1))
    glClearColor(0.62, 0.78, 0.92, 1)
    glShadeModel(GL_FLAT)

    ciudad = ObjModel("ciudad.obj")
    carro = ObjModel("carro.obj")
    llanta = ObjModel("llanta.obj")
    semaforo = ObjModel("semaforo.obj")
    L_ciudad = ciudad.compilar()
    L_carro_cuerpo = carro.compilar({"carroceria"}, con_color=False)
    L_carro_resto = carro.compilar(set(carro.grupos) - {"carroceria"})
    L_llanta = llanta.compilar()
    L_sem_base = semaforo.compilar({"poste", "caja_semaforo"})
    L_luz = {m: semaforo.compilar({m}, con_color=False) for m in ("luz_roja", "luz_amarilla", "luz_verde")}

    red = json.load(open("red_vial.json"))
    sim = Simulacion(red, args.carros)

    rot, elev, dist = map(float, args.camara.split(","))
    foco = tuple(map(float, args.foco.split(",")))
    reloj = pygame.time.Clock()
    pausa = False
    t_sim = 0.0
    dt_fijo = 1 / 30

    while True:
        if args.captura:
            dt = dt_fijo
        else:
            dt = min(reloj.tick(60) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                    pygame.quit(); return
                if e.type == KEYDOWN and e.key == K_SPACE:
                    pausa = not pausa
            k = pygame.key.get_pressed()
            rot += (k[pygame.K_RIGHT] - k[pygame.K_LEFT]) * 60 * dt
            elev = max(5, min(89, elev + (k[pygame.K_UP] - k[pygame.K_DOWN]) * 40 * dt))
            dist = max(20, min(600, dist + (k[pygame.K_s] - k[pygame.K_w]) * 150 * dt))

        if not pausa:
            sim.step(dt)
            t_sim += dt

        if args.captura and t_sim < args.segundos:
            continue

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        perspectiva(50, args.ancho / args.alto, 0.5, 2000)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        ex = dist * math.cos(math.radians(elev)) * math.sin(math.radians(rot))
        ez = dist * math.cos(math.radians(elev)) * math.cos(math.radians(rot))
        ey = dist * math.sin(math.radians(elev))
        mirar_a((ex + foco[0], ey, ez + foco[2]), foco, (0, 1, 0))
        glLightfv(GL_LIGHT0, GL_POSITION, (0.4, 1.0, 0.3, 0.0))

        glCallList(L_ciudad)

        for s in red["semaforos"]:
            agente = sim.semaforos[s["interseccion"]]
            estado = agente.estado(s["grupo_fase"])
            glPushMatrix()
            glTranslatef(*s["pos"]); glRotatef(s["yaw_grados"], 0, 1, 0)
            glCallList(L_sem_base)
            for mat, nombre in (("luz_roja", ROJO), ("luz_amarilla", AMARILLO), ("luz_verde", VERDE)):
                base = semaforo.mats[mat]
                glColor3f(*(base if estado == nombre else [c * 0.15 for c in base]))
                glCallList(L_luz[mat])
            glPopMatrix()

        for c in sim.carros:
            glPushMatrix()
            glTranslatef(*c.pos); glRotatef(c.yaw, 0, 1, 0)
            glColor3f(*c.color)
            glCallList(L_carro_cuerpo)
            glCallList(L_carro_resto)
            for wx, wy, wz in c.LLANTAS_POS:
                glPushMatrix()
                glTranslatef(wx, wy, wz)
                if wz > 0:
                    glRotatef(c.steer, 0, 1, 0)
                glRotatef(c.ang_llanta, 1, 0, 0)
                glCallList(L_llanta)
                glPopMatrix()
            glPopMatrix()

        pygame.display.flip()

        if args.captura:
            datos = glReadPixels(0, 0, args.ancho, args.alto, GL_RGB, GL_UNSIGNED_BYTE)
            img = pygame.image.fromstring(datos, (args.ancho, args.alto), "RGB")
            pygame.image.save(pygame.transform.flip(img, False, True), args.captura)
            pygame.quit(); return


if __name__ == "__main__":
    main()
