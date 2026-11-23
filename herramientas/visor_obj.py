"""
Visor rapido de un solo carrito.
  pip install pygame PyOpenGL
  python herramientas/visor_obj.py                      # usa modelos/carro.obj
  python herramientas/visor_obj.py modelos/llanta.obj   # cualquier otro OBJ
Controles: arrastrar con el mouse = girar, rueda = zoom, C = cambiar color,
           ESPACIO = activar/desactivar giro automatico, ESC = salir
"""
import math, os, sys
import pygame
from pygame.locals import *
from OpenGL.GL import *

MODELOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modelos")
RUTA = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.path.join(MODELOS, "carro.obj")
COLORES = [(0.8, 0.1, 0.1), (0.1, 0.3, 0.8), (0.95, 0.75, 0.1), (0.2, 0.6, 0.3), (0.9, 0.9, 0.9), (0.15, 0.15, 0.15)]


def cargar_obj(ruta):
    """regresa {material: [(normal, v0, v1, v2), ...]} y {material: color}"""
    carpeta = os.path.dirname(ruta)
    V, N, grupos, colores, mat = [], [], {}, {}, None
    for linea in open(ruta):
        p = linea.split()
        if not p:
            continue
        if p[0] == "mtllib":
            actual = None
            for l in open(os.path.join(carpeta, p[1])):
                q = l.split()
                if q and q[0] == "newmtl":
                    actual = q[1]
                elif q and q[0] == "Kd":
                    colores[actual] = tuple(map(float, q[1:4]))
        elif p[0] == "v":
            V.append(tuple(map(float, p[1:4])))
        elif p[0] == "vn":
            N.append(tuple(map(float, p[1:4])))
        elif p[0] == "usemtl":
            mat = p[1]
            grupos.setdefault(mat, [])
        elif p[0] == "f":
            idx = [t.split("/") for t in p[1:]]
            vs = [V[int(t[0]) - 1] for t in idx]
            n = N[int(idx[0][2]) - 1] if len(idx[0]) > 2 and idx[0][2] else None
            for k in range(1, len(vs) - 1):
                grupos.setdefault(mat, []).append((n, vs[0], vs[k], vs[k + 1]))
    return grupos, colores


def dibujar_piso():
    glDisable(GL_LIGHTING)
    glColor3f(0.35, 0.35, 0.38)
    glBegin(GL_QUADS)
    glVertex3f(-6, 0, -6); glVertex3f(-6, 0, 6); glVertex3f(6, 0, 6); glVertex3f(6, 0, -6)
    glEnd()
    glColor3f(0.5, 0.5, 0.55)
    glBegin(GL_LINES)
    for i in range(-6, 7):
        glVertex3f(i, 0.001, -6); glVertex3f(i, 0.001, 6)
        glVertex3f(-6, 0.001, i); glVertex3f(6, 0.001, i)
    glEnd()
    glEnable(GL_LIGHTING)


def main():
    ancho, alto = 900, 650
    pygame.init()
    pygame.display.set_mode((ancho, alto), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Carrito - " + RUTA)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING); glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL); glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_NORMALIZE)
    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.35, 0.35, 0.38, 1))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.85, 0.85, 0.8, 1))
    glClearColor(0.62, 0.78, 0.92, 1)

    grupos, colores = cargar_obj(RUTA)
    rot, elev, dist = 35.0, 20.0, 9.0
    auto, color_i, arrastrando = True, 0, False
    reloj = pygame.time.Clock()
    captura = "--captura" in sys.argv

    while True:
        dt = reloj.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                pygame.quit(); return
            if e.type == KEYDOWN and e.key == K_SPACE:
                auto = not auto
            if e.type == KEYDOWN and e.key == K_c:
                color_i = (color_i + 1) % len(COLORES)
            if e.type == MOUSEBUTTONDOWN and e.button == 1:
                arrastrando = True
            if e.type == MOUSEBUTTONUP and e.button == 1:
                arrastrando = False
            if e.type == MOUSEMOTION and arrastrando:
                rot -= e.rel[0] * 0.5
                elev = max(-5, min(85, elev + e.rel[1] * 0.4))
            if e.type == MOUSEWHEEL:
                dist = max(3, min(30, dist - e.y * 0.6))
        if auto and not arrastrando:
            rot += 25 * dt

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        h = 0.1 * math.tan(math.radians(45) / 2)
        glFrustum(-h * ancho / alto, h * ancho / alto, -h, h, 0.1, 200)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        # camara orbital (sin GLU): alejarse, inclinar, girar
        glTranslatef(0, -0.6, -dist)
        glRotatef(elev, 1, 0, 0)
        glRotatef(-rot, 0, 1, 0)
        glLightfv(GL_LIGHT0, GL_POSITION, (0.4, 1.0, 0.6, 0.0))

        dibujar_piso()
        glBegin(GL_TRIANGLES)
        for mat, tris in grupos.items():
            glColor3f(*(COLORES[color_i] if mat == "carroceria" else colores.get(mat, (0.8, 0.8, 0.8))))
            for n, a, b, c in tris:
                if n:
                    glNormal3f(*n)
                glVertex3f(*a); glVertex3f(*b); glVertex3f(*c)
        glEnd()
        pygame.display.flip()

        if captura:
            datos = glReadPixels(0, 0, ancho, alto, GL_RGB, GL_UNSIGNED_BYTE)
            img = pygame.image.fromstring(datos, (ancho, alto), "RGB")
            pygame.image.save(pygame.transform.flip(img, False, True), "captura_carro.png")
            pygame.quit(); return


if __name__ == "__main__":
    main()