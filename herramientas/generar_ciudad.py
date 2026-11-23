"""
Generador procedural de la ciudad para la simulacion multiagente.
Salida (eje Y hacia arriba, unidades = metros, triangulos, normales planas):
  -> en la carpeta modelos/:
  ciudad.obj / ciudad.mtl     -> escenario estatico (calles, banquetas, edificios, glorieta, arboles)
  carro.obj  / carro.mtl      -> agente vehiculo (centrado en el origen, mirando hacia +Z, sin llantas)
  llanta.obj / llanta.mtl     -> llanta individual centrada en el origen (para instanciar y rotar por eje)
  semaforo.obj / semaforo.mtl -> agente semaforo (luces en grupos separados: luz_roja, luz_amarilla, luz_verde)
  -> en la carpeta datos/:
  red_vial.json               -> grafo de la red: intersecciones, carriles, semaforos, glorieta
Uso:  python herramientas/generar_ciudad.py [semilla]
"""
import json, math, os, random, sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MODELOS = os.path.join(RAIZ, "modelos")
DATOS = os.path.join(RAIZ, "datos")

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 7
random.seed(SEED)

# ---------------- parametros de la ciudad ----------------
N = 5                 # intersecciones por eje (N x N)
S = 60.0              # distancia entre intersecciones
W = 14.0              # ancho de calle (2 carriles por sentido de 3.5 m)
LANE = 3.5
SW = 3.0              # ancho de banqueta
CURB = 0.15           # altura de banqueta
OFF = (N - 1) * S / 2 # para centrar la ciudad en el origen
CENTRO = (N // 2, N // 2)   # interseccion que sera glorieta
R_ISLA = 8.0          # radio de la isla central de la glorieta
R_GLOR = 20         # radio exterior de la glorieta


def ipos(i, j):
    """posicion (x, z) de la interseccion (i = columna, j = fila)"""
    return (i * S - OFF, j * S - OFF)


# ---------------- escritor OBJ ----------------
class Obj:
    def __init__(self, nombre):
        self.nombre = nombre
        self.v, self.vn = [], []
        self.vn_idx = {}
        self.grupos = []   # (nombre, material, [caras])

    def grupo(self, nombre, material):
        self.grupos.append((nombre, material, []))

    def _n(self, n):
        key = tuple(round(c, 4) for c in n)
        if key not in self.vn_idx:
            self.vn.append(key)
            self.vn_idx[key] = len(self.vn)
        return self.vn_idx[key]

    def tri(self, a, b, c):
        ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
        n = (uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx)
        L = math.sqrt(sum(x*x for x in n))
        if L < 1e-9:
            return
        n = (n[0]/L, n[1]/L, n[2]/L)
        ni = self._n(n)
        idx = []
        for p in (a, b, c):
            self.v.append(p)
            idx.append(len(self.v))
        self.grupos[-1][2].append((idx, ni))

    def poly(self, pts):
        """poligono convexo (o estrella desde pts[0]), orden CCW visto desde afuera"""
        for k in range(1, len(pts) - 1):
            self.tri(pts[0], pts[k], pts[k+1])

    def poly_out(self, pts, centro):
        """como poly() pero orienta la cara hacia afuera respecto a 'centro'"""
        a, b, c = pts[0], pts[1], pts[2]
        u = [b[k]-a[k] for k in range(3)]; v = [c[k]-a[k] for k in range(3)]
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        m = [sum(p[k] for p in pts)/len(pts) - centro[k] for k in range(3)]
        self.poly(pts if sum(n[k]*m[k] for k in range(3)) >= 0 else pts[::-1])

    def caja(self, x0, x1, y0, y1, z0, z1, fondo=False):
        p = lambda x, y, z: (x, y, z)
        self.poly([p(x0,y1,z0), p(x0,y1,z1), p(x1,y1,z1), p(x1,y1,z0)])  # arriba
        if fondo:
            self.poly([p(x0,y0,z0), p(x1,y0,z0), p(x1,y0,z1), p(x0,y0,z1)])
        self.poly([p(x0,y0,z1), p(x1,y0,z1), p(x1,y1,z1), p(x0,y1,z1)])  # +z
        self.poly([p(x1,y0,z0), p(x0,y0,z0), p(x0,y1,z0), p(x1,y1,z0)])  # -z
        self.poly([p(x1,y0,z1), p(x1,y0,z0), p(x1,y1,z0), p(x1,y1,z1)])  # +x
        self.poly([p(x0,y0,z0), p(x0,y0,z1), p(x0,y1,z1), p(x0,y1,z0)])  # -x

    def quad_suelo(self, x0, x1, z0, z1, y):
        self.poly([(x0,y,z0), (x0,y,z1), (x1,y,z1), (x1,y,z0)])

    def cilindro(self, cx, cz, r, y0, y1, seg=16, tapa=True):
        pts = [(cx + r*math.cos(2*math.pi*k/seg), cz + r*math.sin(2*math.pi*k/seg)) for k in range(seg)]
        for k in range(seg):
            a, b = pts[k], pts[(k+1) % seg]
            self.poly([(a[0],y0,a[1]), (a[0],y1,a[1]), (b[0],y1,b[1]), (b[0],y0,b[1])])
        if tapa:
            self.poly([(p[0], y1, p[1]) for p in reversed(pts)])

    def cono(self, cx, cz, r, y0, y1, seg=10):
        pts = [(cx + r*math.cos(2*math.pi*k/seg), cz + r*math.sin(2*math.pi*k/seg)) for k in range(seg)]
        for k in range(seg):
            a, b = pts[k], pts[(k+1) % seg]
            self.tri((a[0],y0,a[1]), (cx,y1,cz), (b[0],y0,b[1]))

    def extruir(self, pts2d, y0, y1):
        """prisma de un poligono 2D (x,z) en orden horario visto desde arriba (+Y)"""
        self.poly([(x, y1, z) for x, z in pts2d])
        n = len(pts2d)
        for k in range(n):
            a, b = pts2d[k], pts2d[(k+1) % n]
            self.poly([(a[0],y0,a[1]), (b[0],y0,b[1]), (b[0],y1,b[1]), (a[0],y1,a[1])])

    def guardar(self, mtl):
        with open(os.path.join(MODELOS, self.nombre + ".obj"), "w") as f:
            f.write(f"# {self.nombre}.obj  - generado por generar_ciudad.py (Y arriba, metros)\n")
            f.write(f"mtllib {self.nombre}.mtl\n")
            for x, y, z in self.v:
                f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
            for x, y, z in self.vn:
                f.write(f"vn {x:.4f} {y:.4f} {z:.4f}\n")
            for nombre, mat, caras in self.grupos:
                if not caras:
                    continue
                f.write(f"o {nombre}\nusemtl {mat}\n")
                for idx, ni in caras:
                    f.write("f " + " ".join(f"{i}//{ni}" for i in idx) + "\n")
        usados = {g[1] for g in self.grupos if g[2]}
        with open(os.path.join(MODELOS, self.nombre + ".mtl"), "w") as f:
            for m in sorted(usados):
                r, g, b = mtl[m]
                f.write(f"newmtl {m}\nKa {r*0.3:.3f} {g*0.3:.3f} {b*0.3:.3f}\nKd {r:.3f} {g:.3f} {b:.3f}\n"
                        f"Ks 0.050 0.050 0.050\nNs 10\nd 1.0\nillum 2\n\n")
        ntri = sum(len(g[2]) for g in self.grupos)
        print(f"{self.nombre}.obj: {len(self.v)} vertices, {ntri} triangulos")


MATERIALES = {
    "asfalto": (0.22, 0.22, 0.24), "pasto": (0.35, 0.55, 0.25), "banqueta": (0.70, 0.69, 0.66),
    "linea_blanca": (0.95, 0.95, 0.95), "linea_amarilla": (0.95, 0.78, 0.15),
    "edificio_1": (0.78, 0.74, 0.68), "edificio_2": (0.55, 0.62, 0.70), "edificio_3": (0.82, 0.60, 0.48),
    "edificio_4": (0.60, 0.60, 0.62), "edificio_5": (0.88, 0.85, 0.75), "vidrio": (0.30, 0.45, 0.60),
    "techo": (0.40, 0.38, 0.36), "teja": (0.62, 0.30, 0.22), "tronco": (0.40, 0.27, 0.15),
    "follaje": (0.20, 0.45, 0.18), "monumento": (0.80, 0.80, 0.82),
    "carroceria": (0.80, 0.12, 0.12), "cristal_carro": (0.15, 0.20, 0.28), "llanta": (0.06, 0.06, 0.06),
    "rin": (0.72, 0.74, 0.78),
    "faro": (1.0, 1.0, 0.85), "calavera": (0.7, 0.0, 0.0),
    "poste": (0.25, 0.25, 0.27), "caja_semaforo": (0.12, 0.12, 0.12),
    "luz_roja": (0.9, 0.05, 0.05), "luz_amarilla": (0.95, 0.75, 0.05), "luz_verde": (0.05, 0.85, 0.2),
}

# =====================================================================
# CIUDAD
# =====================================================================
city = Obj("ciudad")
EXT = OFF + S / 2 + 40   # extension del terreno

# --- terreno y asfalto ---
city.grupo("terreno", "pasto")
city.quad_suelo(-EXT, EXT, -EXT, EXT, -0.02)
city.grupo("asfalto", "asfalto")
A0, A1 = -OFF - W / 2, OFF + W / 2
city.quad_suelo(A0, A1, A0, A1, 0.0)

# --- manzanas (banquetas) ---
def manzana_poligono(x0, x1, z0, z1, corte, R=R_GLOR + 0.5):
    """rectangulo en sentido horario visto desde arriba; si corte=(cx,cz) se recorta un arco de la glorieta"""
    # horario visto desde +Y con ejes x->derecha, z->abajo: (x0,z0)->(x0,z1)->(x1,z1)->(x1,z0)
    esquinas = [(x0, z0), (x0, z1), (x1, z1), (x1, z0)]
    if not corte:
        return esquinas
    cx, cz = corte
    # esquina mas cercana al centro de la glorieta
    k = min(range(4), key=lambda i: (esquinas[i][0]-cx)**2 + (esquinas[i][1]-cz)**2)
    ex, ez = esquinas[k]
    prev, nxt = esquinas[k-1], esquinas[(k+1) % 4]
    def punto_en_lado(p):
        # interseccion del lado esquina->p con el circulo
        dx, dz = p[0]-ex, p[1]-ez
        L = math.hypot(dx, dz); dx /= L; dz /= L
        fx, fz = ex-cx, ez-cz
        b = fx*dx + fz*dz; c = fx*fx + fz*fz - R*R
        t = -b + math.sqrt(b*b - c)
        return (ex + dx*t, ez + dz*t)
    a = punto_en_lado(prev)
    b = punto_en_lado(nxt)
    ang_a = math.atan2(a[1]-cz, a[0]-cx)
    ang_b = math.atan2(b[1]-cz, b[0]-cx)
    d = (ang_b - ang_a + math.pi) % (2*math.pi) - math.pi
    arco = [(cx + R*math.cos(ang_a + d*t/10), cz + R*math.sin(ang_a + d*t/10)) for t in range(11)]
    pts = esquinas[k+1:] + esquinas[:k]   # las 3 esquinas restantes empezando por nxt
    # orden: ... prev -> arco(a..b) -> nxt ...
    res = []
    for i in range(4):
        idx = (k + 1 + i) % 4
        if idx == k:
            res += arco
        else:
            res.append(esquinas[idx])
    # empezar en la esquina opuesta (para triangulacion en abanico valida)
    op = (k + 2) % 4
    s = res.index(esquinas[op])
    return res[s:] + res[:s]

def lejos_glorieta(x0, x1, z0, z1, margen):
    cx, cz = ipos(*CENTRO)
    px = min(max(cx, x0), x1); pz = min(max(cz, z0), z1)
    return math.hypot(px-cx, pz-cz) > R_GLOR + margen

PALETA = ["edificio_1", "edificio_2", "edificio_3", "edificio_4", "edificio_5"]
arboles = []
for i in range(N - 1):
    for j in range(N - 1):
        (xa, za), (xb, zb) = ipos(i, j), ipos(i + 1, j + 1)
        x0, x1, z0, z1 = xa + W/2, xb - W/2, za + W/2, zb - W/2
        vecinas = {(i, j), (i+1, j), (i, j+1), (i+1, j+1)}
        corte = ipos(*CENTRO) if CENTRO in vecinas else None
        city.grupo(f"banqueta_{i}_{j}", "banqueta")
        city.extruir(manzana_poligono(x0, x1, z0, z1, corte), 0.0, CURB)

        ix0, ix1, iz0, iz1 = x0 + SW, x1 - SW, z0 + SW, z1 - SW
        dist_c = math.hypot((x0+x1)/2, (z0+z1)/2)
        es_parque = random.random() < 0.15
        if es_parque:
            # parque: pasto + arboles
            city.grupo(f"parque_{i}_{j}", "pasto")
            if corte:
                city.extruir(manzana_poligono(ix0, ix1, iz0, iz1, corte, R_GLOR + 0.5 + SW), CURB, CURB + 0.03)
            else:
                city.extruir([(ix0, iz0), (ix0, iz1), (ix1, iz1), (ix1, iz0)], CURB, CURB + 0.03)
            for _ in range(14):
                tx, tz = random.uniform(ix0+2, ix1-2), random.uniform(iz0+2, iz1-2)
                if lejos_glorieta(tx-1, tx+1, tz-1, tz+1, SW + 2):
                    arboles.append((tx, tz, CURB))
            continue
        # lotes con edificios
        div = random.choice([2, 2, 3])
        lw, lh = (ix1 - ix0) / div, (iz1 - iz0) / div
        centro = max(0.0, 1 - dist_c / (OFF * 1.2))
        for a in range(div):
            for b in range(div):
                lx0, lz0 = ix0 + a*lw, iz0 + b*lh
                if random.random() < 0.1 or not lejos_glorieta(lx0, lx0 + lw, lz0, lz0 + lh, SW + 1):
                    continue
                m = random.uniform(1.0, 2.5)
                bx0, bx1 = lx0 + m, lx0 + lw - random.uniform(1.0, 2.5)
                bz0, bz1 = lz0 + m, lz0 + lh - random.uniform(1.0, 2.5)
                mat = random.choice(PALETA)
                k = len(city.grupos)
                if random.random() < 0.25 + 0.6 * centro:
                    h = random.uniform(15, 30) + 70 * centro * random.random()   # torre
                    city.grupo(f"edificio_{i}_{j}_{a}{b}", mat)
                    city.caja(bx0, bx1, CURB, CURB + h, bz0, bz1)
                    # franjas de ventanas (ligeramente sobresalidas)
                    city.grupo(f"ventanas_{i}_{j}_{a}{b}", "vidrio")
                    piso = 3.5
                    y = CURB + 3.0
                    while y + 1.6 < CURB + h - 1:
                        e = 0.05
                        city.caja(bx0 - e, bx1 + e, y, y + 1.6, bz0 - e, bz1 + e)
                        y += piso
                    # remate en azotea
                    city.grupo(f"azotea_{i}_{j}_{a}{b}", "techo")
                    cx_, cz_ = (bx0+bx1)/2, (bz0+bz1)/2
                    city.caja(cx_-2, cx_+2, CURB+h, CURB+h+2.5, cz_-2, cz_+2)
                else:
                    h = random.uniform(4, 9)    # casa / comercio
                    city.grupo(f"casa_{i}_{j}_{a}{b}", mat)
                    city.caja(bx0, bx1, CURB, CURB + h, bz0, bz1)
                    if random.random() < 0.5:   # techo de dos aguas
                        city.grupo(f"techo_{i}_{j}_{a}{b}", "teja")
                        y0, y1 = CURB + h, CURB + h + 2.5
                        zm = (bz0 + bz1) / 2
                        city.poly([(bx0, y0, bz1), (bx1, y0, bz1), (bx1, y1, zm), (bx0, y1, zm)])
                        city.poly([(bx1, y0, bz0), (bx0, y0, bz0), (bx0, y1, zm), (bx1, y1, zm)])
                        city.tri((bx0, y0, bz0), (bx0, y0, bz1), (bx0, y1, zm))
                        city.tri((bx1, y0, bz1), (bx1, y0, bz0), (bx1, y1, zm))
                    city.grupo(f"ventanas_{i}_{j}_{a}{b}", "vidrio")
                    e = 0.05
                    city.caja(bx0 - e, bx1 + e, CURB + 1.2, CURB + 2.6, bz0 - e, bz1 + e)

# arboles sobre banquetas (alineacion de calle)
for i in range(N - 1):
    for j in range(N - 1):
        (xa, za), (xb, zb) = ipos(i, j), ipos(i + 1, j + 1)
        x0, x1, z0, z1 = xa + W/2, xb - W/2, za + W/2, zb - W/2
        for t in range(1, 5):
            for (tx, tz) in [(x0 + 1.5, z0 + t*(z1-z0)/5), (x1 - 1.5, z0 + t*(z1-z0)/5),
                             (x0 + t*(x1-x0)/5, z0 + 1.5), (x0 + t*(x1-x0)/5, z1 - 1.5)]:
                if random.random() < 0.5 and lejos_glorieta(tx-1, tx+1, tz-1, tz+1, 2):
                    arboles.append((tx, tz, CURB))

city.grupo("troncos", "tronco")
for tx, tz, y in arboles:
    city.cilindro(tx, tz, 0.2, y, y + 2.5, seg=6)
city.grupo("follaje", "follaje")
for tx, tz, y in arboles:
    h = random.uniform(3, 5)
    city.cono(tx, tz, random.uniform(1.3, 2.0), y + 1.8, y + 1.8 + h, seg=8)

# --- glorieta ---
gx, gz = ipos(*CENTRO)
city.grupo("glorieta_isla", "banqueta")
city.cilindro(gx, gz, R_ISLA, 0.0, CURB + 0.05, seg=40)
city.grupo("glorieta_pasto", "pasto")
city.cilindro(gx, gz, R_ISLA - 1.0, CURB + 0.05, CURB + 0.08, seg=40)
city.grupo("glorieta_monumento", "monumento")
city.cilindro(gx, gz, 2.0, CURB, CURB + 1.5, seg=12)
city.cilindro(gx, gz, 0.8, CURB + 1.5, CURB + 12, seg=12)
city.cono(gx, gz, 1.2, CURB + 12, CURB + 14, seg=12)

# --- marcas viales ---
YM = 0.012
def linea_up(x0, z0, x1, z1, ancho):
    # asegura que la normal apunte a +Y
    dx, dz = x1 - x0, z1 - z0
    L = math.hypot(dx, dz); nx, nz = -dz / L * ancho / 2, dx / L * ancho / 2
    p = [(x0+nx, YM, z0+nz), (x1+nx, YM, z1+nz), (x1-nx, YM, z1-nz), (x0-nx, YM, z0-nz)]
    # normal = (p1-p0)x(p2-p0) ; si y<0 invertir
    ux, uz = p[1][0]-p[0][0], p[1][2]-p[0][2]; vx, vz = p[2][0]-p[0][0], p[2][2]-p[0][2]
    if uz*vx - ux*vz < 0:
        p = p[::-1]
    city.poly(p)

def recorte(nodo):
    return R_GLOR + 1.0 if nodo == CENTRO else W / 2 + 4.5

segmentos = []  # (nodo_a, nodo_b) tramos de calle no dirigidos
for i in range(N):
    for j in range(N):
        if i + 1 < N: segmentos.append(((i, j), (i + 1, j)))
        if j + 1 < N: segmentos.append(((i, j), (i, j + 1)))

city.grupo("linea_central", "linea_amarilla")
for a, b in segmentos:
    (xa, za), (xb, zb) = ipos(*a), ipos(*b)
    d = math.hypot(xb-xa, zb-za); ux, uz = (xb-xa)/d, (zb-za)/d
    ta, tb = recorte(a), d - recorte(b)
    nx, nz = -uz, ux
    for s in (-0.12, 0.12):   # doble linea amarilla
        linea_up(xa+ux*ta+nx*s, za+uz*ta+nz*s, xa+ux*tb+nx*s, za+uz*tb+nz*s, 0.12)

city.grupo("lineas_carril", "linea_blanca")
for a, b in segmentos:
    (xa, za), (xb, zb) = ipos(*a), ipos(*b)
    d = math.hypot(xb-xa, zb-za); ux, uz = (xb-xa)/d, (zb-za)/d
    nx, nz = -uz, ux
    ta, tb = recorte(a), d - recorte(b)
    for s in (-LANE, LANE):   # division entre carriles (punteada)
        t = ta + 1
        while t + 3 < tb:
            linea_up(xa+ux*t+nx*s, za+uz*t+nz*s, xa+ux*(t+3)+nx*s, za+uz*(t+3)+nz*s, 0.15)
            t += 9
    # lineas de alto y pasos peatonales
    for (nodo, t0, sgn) in ((a, ta, 1), (b, tb, -1)):
        if nodo == CENTRO:
            continue
        # linea de alto (solo del lado de los carriles que llegan a 'nodo')
        px, pz = xa + ux*(t0 - sgn*0.3), za + uz*(t0 - sgn*0.3)
        lado = -sgn   # carriles que llegan estan a la derecha del sentido de llegada
        # sentido de llegada = -sgn*u ; derecha = (-dz, dx) de ese sentido
        hx, hz = (-sgn*ux), (-sgn*uz)
        rx, rz = -hz, hx
        linea_up(px, pz, px + rx*W/2, pz + rz*W/2, 0.5)
        # paso de cebra entre la linea de alto y la interseccion
        for k in range(7):
            o = -W/2 + 1 + k * 2.0
            cxp, czp = xa + ux*(t0 - sgn*2.6), za + uz*(t0 - sgn*2.6)
            linea_up(cxp + nx*o - ux*1.5, czp + nz*o - uz*1.5, cxp + nx*o + ux*1.5, czp + nz*o + uz*1.5, 0.9)

# linea punteada de la glorieta (entre los dos carriles de circulacion)
r_mid = (R_ISLA + R_GLOR) / 2
seg = 48
for k in range(0, seg, 2):
    a0, a1 = 2*math.pi*k/seg, 2*math.pi*(k+0.8)/seg
    linea_up(gx + r_mid*math.cos(a0), gz + r_mid*math.sin(a0), gx + r_mid*math.cos(a1), gz + r_mid*math.sin(a1), 0.15)

city.guardar(MATERIALES)

# =====================================================================
# CARRO (mirando a +Z, centrado en el origen, llantas tocando y=0)
# =====================================================================
car = Obj("carro")
car.grupo("carroceria", "carroceria")
car.caja(-0.9, 0.9, 0.35, 1.0, -2.1, 2.1, fondo=True)
# cabina trapezoidal
yb, yt = 1.0, 1.55
CC = (0.0, 1.2, -0.25)
car.grupo("cabina", "carroceria")
car.poly([(-0.75, yt, -1.1), (-0.75, yt, 0.6), (0.75, yt, 0.6), (0.75, yt, -1.1)])
car.grupo("cristales", "cristal_carro")
car.poly_out([(-0.85, yb, 1.1), (0.85, yb, 1.1), (0.75, yt, 0.6), (-0.75, yt, 0.6)], CC)      # parabrisas
car.poly_out([(0.85, yb, -1.6), (-0.85, yb, -1.6), (-0.75, yt, -1.1), (0.75, yt, -1.1)], CC)  # medallon
car.poly_out([(0.85, yb, 1.1), (0.85, yb, -1.6), (0.75, yt, -1.1), (0.75, yt, 0.6)], CC)      # lado +x
car.poly_out([(-0.85, yb, -1.6), (-0.85, yb, 1.1), (-0.75, yt, 0.6), (-0.75, yt, -1.1)], CC)  # lado -x
car.grupo("faros", "faro")
for fx in (-0.6, 0.6):
    car.caja(fx - 0.2, fx + 0.2, 0.7, 0.85, 2.1, 2.14)
car.grupo("calaveras", "calavera")
for fx in (-0.6, 0.6):
    car.caja(fx - 0.2, fx + 0.2, 0.7, 0.85, -2.14, -2.1)
car.guardar(MATERIALES)

# =====================================================================
# LLANTA INDIVIDUAL (centrada en el origen, eje de giro en X, radio 0.35)
# =====================================================================
wheel = Obj("llanta")
segs, r, r_rin = 12, 0.35, 0.19
x0, x1 = -0.12, 0.12
pts = [(r * math.cos(2 * math.pi * k / segs), r * math.sin(2 * math.pi * k / segs)) for k in range(segs)]
wheel.grupo("neumatico", "llanta")
for k in range(segs):
    (za_, ya), (zb_, yb_) = pts[k], pts[(k + 1) % segs]
    wheel.poly_out([(x0, ya, za_), (x0, yb_, zb_), (x1, yb_, zb_), (x1, ya, za_)], (0, 0, 0))
wheel.poly_out([(x1, y, z) for z, y in pts], (-1, 0, 0))
wheel.poly_out([(x0, y, z) for z, y in pts], (1, 0, 0))
pts_rin = [(r_rin * math.cos(2 * math.pi * k / segs), r_rin * math.sin(2 * math.pi * k / segs)) for k in range(segs)]
wheel.grupo("rin", "rin")
wheel.poly_out([(x1 + 0.004, y, z) for z, y in pts_rin], (-1, 0, 0))
wheel.poly_out([(x0 - 0.004, y, z) for z, y in pts_rin], (1, 0, 0))
wheel.grupo("aspa", "poste")
for sx, nx in ((x1 + 0.008, -1), (x0 - 0.008, 1)):
    wheel.poly_out([(sx, -0.03, -r_rin), (sx, 0.03, -r_rin), (sx, 0.03, r_rin), (sx, -0.03, r_rin)], (nx, 0, 0))
wheel.guardar(MATERIALES)

# =====================================================================
# SEMAFORO (base en el origen, poste en y, el brazo se extiende hacia +X,
# brazo hacia -X, las luces miran hacia +Z: rotarlo para que mire a los autos que llegan)
# =====================================================================
sem = Obj("semaforo")
sem.grupo("poste", "poste")
sem.cilindro(0, 0, 0.12, 0, 5.5, seg=10)
sem.caja(-4.5, 0, 5.3, 5.5, -0.08, 0.08)
sem.grupo("caja", "caja_semaforo")
sem.caja(-4.3, -3.7, 3.6, 5.3, -0.25, 0.25)
for nombre, y in (("luz_roja", 4.95), ("luz_amarilla", 4.45), ("luz_verde", 3.95)):
    sem.grupo(nombre, nombre)
    segs, r = 12, 0.2
    pts = [(-4.0 + r*math.cos(2*math.pi*k/segs), y + r*math.sin(2*math.pi*k/segs)) for k in range(segs)]
    sem.poly([(x, yy, 0.27) for x, yy in pts])
sem.guardar(MATERIALES)

# =====================================================================
# RED VIAL (grafo para la logica de los agentes)
# =====================================================================
nodos, aristas, semaforos = [], [], []
for i in range(N):
    for j in range(N):
        x, z = ipos(i, j)
        nodos.append({"id": f"{i}_{j}", "pos": [x, 0.0, z],
                      "tipo": "glorieta" if (i, j) == CENTRO else "semaforo"})

for a, b in segmentos:
    for (o, d) in ((a, b), (b, a)):
        (xo, zo), (xd, zd) = ipos(*o), ipos(*d)
        L = math.hypot(xd-xo, zd-zo); ux, uz = (xd-xo)/L, (zd-zo)/L
        rx, rz = -uz, ux           # derecha del conductor (Y arriba)
        t0, t1 = recorte(o), L - recorte(d)
        carriles = []
        for k, off in enumerate((LANE/2, LANE*1.5)):   # 0 = carril interior (izquierdo), 1 = exterior (derecho)
            carriles.append({"indice": k,
                             "inicio": [round(xo+ux*t0+rx*off, 3), 0.0, round(zo+uz*t0+rz*off, 3)],
                             "fin":    [round(xo+ux*t1+rx*off, 3), 0.0, round(zo+uz*t1+rz*off, 3)]})
        aristas.append({"id": f"{o[0]}_{o[1]}->{d[0]}_{d[1]}", "origen": f"{o[0]}_{o[1]}",
                        "destino": f"{d[0]}_{d[1]}", "direccion": [ux, 0.0, uz],
                        "longitud": round(t1 - t0, 3), "vel_max": 13.9, "carriles": carriles})
        if d != CENTRO:
            # semaforo en la esquina derecha antes de la interseccion destino, mirando a los autos que llegan
            px, pz = xd - ux*(W/2 + 1.5) + rx*(W/2 + 1.0), zd - uz*(W/2 + 1.5) + rz*(W/2 + 1.0)
            # el modelo mira a +Z (brazo a -X): girar yaw en Y para que mire a los autos que llegan (-dir);
            # asi el brazo queda sobre la calle
            yaw = math.degrees(math.atan2(-ux, -uz))
            eje = "x" if abs(ux) > 0.5 else "z"
            semaforos.append({"id": f"sem_{o[0]}_{o[1]}->{d[0]}_{d[1]}", "interseccion": f"{d[0]}_{d[1]}",
                              "controla_arista": f"{o[0]}_{o[1]}->{d[0]}_{d[1]}", "grupo_fase": eje,
                              "pos": [round(px, 3), CURB, round(pz, 3)], "yaw_grados": round(yaw, 2)})

red = {
    "descripcion": "Red vial de la ciudad. Y arriba, metros. Circulacion por la derecha. "
                   "Los carriles se recorren de 'inicio' a 'fin'; al llegar a 'fin' el agente entra a la "
                   "interseccion 'destino' y elige una arista saliente (decision de ruta).",
    "parametros": {"N": N, "distancia_intersecciones": S, "ancho_calle": W, "ancho_carril": LANE,
                   "altura_banqueta": CURB},
    "glorieta": {"nodo": f"{CENTRO[0]}_{CENTRO[1]}", "centro": [gx, 0.0, gz], "radio_isla": R_ISLA,
                 "radio_exterior": R_GLOR, "radios_carriles": [R_ISLA + 1.9, R_ISLA + 5.4],
                 "sentido": "antihorario visto desde arriba (+Y): angulo theta=atan2(z,x) DISMINUYE"},
    "nodos": nodos, "aristas": aristas, "semaforos": semaforos,
}
with open(os.path.join(DATOS, "red_vial.json"), "w") as f:
    json.dump(red, f, indent=1)
print(f"red_vial.json: {len(nodos)} nodos, {len(aristas)} aristas, {len(semaforos)} semaforos")
