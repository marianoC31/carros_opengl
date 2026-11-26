"""
visor.py - Dibuja con open GL el mundo de la simulación.

La lógica de agente vive en trafico / agentpy y este archivo solo dibuja lo que hay en el mundo.
    python visor.py
    python visor.py --carros 80
    python visor.py --semilla 1
    Controles: flechas = orbitar camara, W/S = acercar/alejar, ESPACIO = pausa, ESC = salir
"""
import argparse, math, os
import pygame
from pygame.locals import DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_SPACE
from OpenGL.GL import *

from trafico.mundo import Mundo
from trafico.semaforo import AMARILLO, ROJO, VERDE

# carpetas del proyecto (calculadas desde este archivo, asi funciona desde cualquier directorio)
RAIZ = os.path.dirname(os.path.abspath(__file__))
MODELOS = os.path.join(RAIZ, "modelos")

DT = 1/30


# =====================================================================
# Cargador OBJ -> display lists de OpenGL
# =====================================================================
class ObjModel:
    def __init__(self, ruta):
        self.mats = {}
        self.grupos = {}          # material -> lista de (normal, (v0, v1, v2))
        base = os.path.dirname(ruta)
        V, N = [], []
        mat = None
        for linea in open(ruta):
            p = linea.split()
            if not p:
                continue
            if p[0] == "mtllib":
                self._leer_mtl(os.path.join(base, p[1]))
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

COLORES = [(0.8,0.1,0.1),(0.1,0.3,0.8),(0.9,0.9,0.9),(0.15,0.15,0.15),
           (0.95,0.75,0.1),(0.2,0.6,0.3),(0.6,0.6,0.65), (0.5,0.1,0.5)]
RADIO_LLANTA = 0.35
LLANTAS_POS = ((-0.95,0.35,1.3),(0.95,0.35,1.3),(-0.95,0.35,-1.3),(0.95,0.35,-1.3))

def animar_llantas(estado, c, dt):
    """cuanto han rodado las llantas del carro 'c' y hacia donde apuntan las 
        delanteras(grados).
        'estado' guarda, por id de carro: (rdado, direccion, yaw del cuadro anerior)
    """
    rodado, direccion, yaw_antes = estado.get(c.id,(0.0,0.0,c.yaw))
    rodado = (rodado + math.degrees(c.v*dt / RADIO_LLANTA)) % 360 #angulo = distancia / radio
    dyaw = (c.yaw - yaw_antes + 180) % 360 - 180 #cuanto giro el carro
    objetivo = max(-30.0, min(30.0, dyaw / dt * 0.6)) if c.v > 0.2 else 0.0
    direccion += (objetivo - direccion) * min(1.0, 10 * dt) #mover suavemente
    estado[c.id] = (rodado, direccion, c.yaw)
    return rodado, direccion


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
    ap.add_argument("--semilla", type=int, default = None, help = "misma semilla -> misma simulacion")
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

    ciudad = ObjModel(os.path.join(MODELOS, "ciudad.obj"))
    carro = ObjModel(os.path.join(MODELOS, "carro.obj"))
    llanta = ObjModel(os.path.join(MODELOS, "llanta.obj"))
    semaforo = ObjModel(os.path.join(MODELOS, "semaforo.obj"))
    L_ciudad = ciudad.compilar()
    L_carro_cuerpo = carro.compilar({"carroceria"}, con_color=False)
    L_carro_resto = carro.compilar(set(carro.grupos) - {"carroceria"})
    L_llanta = llanta.compilar()
    L_sem_base = semaforo.compilar({"poste", "caja_semaforo"})
    L_luz = {m: semaforo.compilar({m}, con_color=False) for m in ("luz_roja", "luz_amarilla", "luz_verde")}

    mundo = Mundo({"n_carros": args.carros, "dt":DT, "seed": args.semilla})
    mundo.sim_setup()
    llantas = {}
    

    rot, elev, dist = map(float, args.camara.split(","))
    foco = tuple(map(float, args.foco.split(",")))
    reloj = pygame.time.Clock()
    pausa = False
    t_sim = 0.0
    

    while True:
        dt = DT
        if not args.captura:
            reloj.tick(30)
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
            mundo.sim_step()
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

        for s in mundo.red.semaforos:
            agente = mundo.semaforo_de_nodo[s["interseccion"]]
            estado = agente.estado(s["grupo_fase"])
            glPushMatrix()
            glTranslatef(*s["pos"]); glRotatef(s["yaw_grados"], 0, 1, 0)
            glCallList(L_sem_base)
            for mat, nombre in (("luz_roja", ROJO), ("luz_amarilla", AMARILLO), ("luz_verde", VERDE)):
                base = semaforo.mats[mat]
                glColor3f(*(base if estado == nombre else [c * 0.15 for c in base]))
                glCallList(L_luz[mat])
            glPopMatrix()

        for c in mundo.carros:
            rodando, direccion = animar_llantas(llantas, c, dt)
            glPushMatrix()
            glTranslatef(*c.pos); glRotatef(c.yaw, 0, 1, 0)
            glColor3f(*COLORES[c.id % len(COLORES)])
            glCallList(L_carro_cuerpo)
            glCallList(L_carro_resto)
            for wx, wy, wz in LLANTAS_POS:
                glPushMatrix()
                glTranslatef(wx, wy, wz)
                if wz > 0:
                    glRotatef(direccion, 0, 1, 0)
                glRotatef(rodando, 1, 0, 0)
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
