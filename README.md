# Ciudad para simulación multiagente (OBJ + OpenGL)

## Archivos
| Archivo | Qué es |
|---|---|
| `ciudad.obj` + `ciudad.mtl` | Escenario estático: grid de 5×5 intersecciones, calles de 2 carriles por sentido, banquetas, pasos de cebra, líneas de alto, glorieta central con monumento, edificios, casas, parques y árboles |
| `carro.obj` + `carro.mtl` | Agente vehículo. Centrado en el origen, mira hacia **+Z**, llantas en y=0. Material `carroceria` separado para pintar cada auto de distinto color |
| `semaforo.obj` + `semaforo.mtl` | Agente semáforo. Base en el origen, luces mirando a **+Z**, brazo hacia −X. Las luces son grupos separados: `luz_roja`, `luz_amarilla`, `luz_verde` |
| `red_vial.json` | Grafo de la red vial para la lógica de los agentes |
| `visor.py` | Cargador OBJ + simulación multiagente de ejemplo con PyOpenGL |
| `generar_ciudad.py` | Genera todo lo anterior. `python generar_ciudad.py 12` → otra ciudad con semilla 12 |

Convenciones: **Y hacia arriba**, unidades en **metros**, solo triángulos, normales por cara (`f v//vn`). Circulación por la derecha.

## Correr el ejemplo
```
pip install pygame PyOpenGL
python visor.py --carros 80
```
Flechas = orbitar, W/S = zoom, ESPACIO = pausa.

## Cómo poner cada agente en OpenGL
```python
glPushMatrix()
glTranslatef(x, y, z)          # posición del agente
glRotatef(yaw, 0, 1, 0)        # yaw = degrees(atan2(dir_x, dir_z))
glCallList(lista_carro)
glPopMatrix()
```
La ciudad se dibuja una sola vez por frame con su display list (o VBO). Los carros y semáforos son el mismo modelo instanciado muchas veces con distinta matriz.

## red_vial.json
- `nodos`: intersecciones (`id` "i_j", `pos`, `tipo` = `semaforo` | `glorieta`)
- `aristas`: tramos **dirigidos** entre intersecciones. Cada una tiene `direccion`, `longitud`, `vel_max` (m/s) y 2 `carriles` (0 = izquierdo/interior, 1 = derecho/exterior) con puntos `inicio` → `fin`. El `fin` coincide con la línea de alto.
- `semaforos`: posición y `yaw_grados` listos para `glTranslatef`/`glRotatef`, la arista que controlan y su `grupo_fase` (`x` o `z`): los del mismo grupo en una intersección se ponen en verde juntos.
- `glorieta`: centro, radios de los carriles y sentido de giro.

## Lógica incluida en visor.py (para extender)
- **Semáforo**: ciclo verde 12 s / amarillo 3 s / todo rojo 1.5 s, alternando eje X y eje Z, con desfase entre intersecciones (onda verde).
- **Carro**: Intelligent Driver Model (sigue al de enfrente con distancia de seguridad), se detiene en rojo/amarillo, cambio de carril si el de enfrente va lento y hay hueco, decisión de ruta aleatoria en cada intersección, curvas Bézier dentro del cruce, circulación antihoraria en la glorieta.
- Simplificación: los autos dentro de una intersección no revisan conflictos con los que cruzan en otra dirección (el semáforo lo evita; en la glorieta no se cede el paso). Siguientes pasos: ceda el paso en la glorieta, baches (frenado), rutas por Dijkstra/A* sobre el grafo, y conectar con Mesa enviando posiciones por JSON.
