# Guion del video de avance (~2 minutos, dos integrantes)

### 0:00 – 0:15 · Introducción (A)
🎥 *Vista general de la ciudad, girando la cámara despacio.*

**A:** "Hola, somos ___ y ___. Les presentamos el avance de nuestro proyecto: una simulación multiagente del tráfico
de una ciudad, hecha en Python con OpenGL. Hoy les mostramos la base: la ciudad, su grafo y el comportamiento inicial
de los agentes."

### 0:15 – 0:40 · La ciudad (B)
🎥 *Acercamiento a un cruce: calles, banquetas, edificios.*

**B:** "La ciudad es una cuadrícula de cinco por cinco intersecciones, separadas sesenta metros. Cada calle tiene dos
carriles por sentido, banquetas, pasos de cebra y líneas de alto. En el centro hay una glorieta, y alrededor hay
edificios, casas y parques. Todo se genera con un script y se exporta a modelos OBJ que cargamos en OpenGL."

### 0:40 – 1:00 · El grafo (A)
🎥 *Vista desde arriba (o el archivo `datos/red_vial.json`).*

**A:** "Para que los agentes entiendan la ciudad, la representamos como un grafo dirigido. Tiene veinticinco nodos,
que son las intersecciones, y ochenta aristas, que son los tramos de calle en cada sentido. Cada arista guarda su
longitud, su velocidad máxima, sus dos carriles y el semáforo que la controla."

### 1:00 – 1:15 · Semáforos (B)
🎥 *Un cruce donde se vea el cambio de luces.*

**B:** "Nuestro primer agente es el semáforo. Alterna verde, amarillo y rojo entre los dos ejes de la calle. Cada
intersección tiene un pequeño desfase para formar una onda verde."

### 1:15 – 1:45 · Carros (A)
🎥 *Carros siguiéndose, frenando en rojo, cambiando de carril y entrando a la glorieta.*

**A:** "El segundo agente es el carro. Por ahora es reactivo. Sigue al auto de enfrente guardando una distancia
segura, con el Intelligent Driver Model. Frena en rojo y en amarillo, se cambia de carril si el de adelante va lento
y rodea la glorieta en sentido antihorario. En cada intersección elige su siguiente calle al azar: todavía no tiene
destino ni aprende."

### 1:45 – 2:00 · Siguiente paso (B)
🎥 *Vista general otra vez.*

**B:** "El siguiente paso es darles inteligencia con aprendizaje *no-regret*. Cada conductor elegirá su ruta y su
forma de manejar, y aprenderá de los malos resultados, como choques o calles cerradas. ¡Gracias!"

---

## Cómo grabar cada toma
Durante la ventana: **flechas** = girar la cámara, **W/S** = acercar o alejar, **ESPACIO** = pausa.

| Toma | Comando |
|---|---|
| Vista general | `python visor.py --carros 80` |
| Cruce con semáforo | `python visor.py --carros 80 --foco=-60,0,-60 --camara 30,30,60` |
| Glorieta | `python visor.py --carros 80 --foco 0,0,0 --camara 45,40,70` |

Consejos: graben cada toma por separado y júntenlas en la edición (la voz queda mejor grabada aparte). Si se pasan
de 2 minutos, recorten la parte del grafo.
