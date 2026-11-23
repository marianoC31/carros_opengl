# Plan de desarrollo

## Idea
Los carros aprenden con **no-regret learning** a partir de malas experiencias, como en la vida real:
choques, mala velocidad y eventualidades (calles cerradas). Hay tres niveles de decisión:

| Nivel | Cuándo decide | Qué elige | Algoritmo | Información |
|---|---|---|---|---|
| **Ruta** | Al iniciar cada viaje | Una de K rutas al destino | FixedShare (Hedge que no olvida) | Completa: conoce el tiempo de todas sus rutas |
| **Maniobras** | En situaciones concretas | Cómo manejar ahí | EXP3.S (un aprendiz por situación) | Bandit: solo sabe lo que le pasó a él |
| **Física** | Cada frame (30 Hz) | Acelerar o frenar | IDM, sin aprendizaje | — |

Situaciones de maniobra: semáforo en amarillo (frenar/pasar), distancia al de enfrente (corta/normal/larga),
velocidad (−10% / límite / +20%), entrada a la glorieta (hueco grande/chico) y cambio de carril (conservador/agresivo).

**Pérdida** (0 a 1) = a·tiempo perdido + b·choque + c·multa + d·frenado brusco

**Eventualidades (primero):** choques y calles cerradas.
**Después (ideas):** lluvia, radares, baches, personalidades distintas, semáforos que aprenden.

## Pasos
| # | Paso | Archivos | Estado |
|---|---|---|---|
| 0 | Algoritmos no-regret y un juguete de 2 rutas | `trafico/aprendizaje.py`, `experimentos/paso0_rutas.py` | ✅ |
| 1 | Separar la simulación del dibujo, con `dt` fijo | `trafico/red.py`, `trafico/agentes.py`, `trafico/mundo.py`, `visor.py` | ⬜ |
| 2 | Hacer posibles los choques: tiempo de reacción, ruido, colisiones | `trafico/agentes.py`, `trafico/colisiones.py` | ⬜ |
| 3 | Rutas: origen→destino, K rutas y aprendiz FixedShare | `trafico/red.py`, `trafico/conductor.py` | ⬜ |
| 4 | Maniobras: EXP3 por situación y función de pérdida | `trafico/conductor.py`, `trafico/perdidas.py` | ⬜ |
| 5 | Eventos: calles cerradas | `trafico/eventos.py` | ⬜ |
| 6 | Métricas y visualización: choques por día, regret, conos, colores | `experimentos/`, `visor.py` | ⬜ |

(Los nombres de archivo de los pasos 1 a 6 son tentativos; se ajustan al llegar a cada paso.)

## Resultados del paso 0 (porcentaje de conductores en la avenida)
| Momento | Hedge | FixedShare | EXP3 | EXP3.S |
|---|---|---|---|---|
| Día 99 (abierta, equilibrio 55.6%) | 66% | 66% | 64% | 63% |
| Día 110 (ya cerrada) | 7% | 7% | 32% | 29% |
| Día 199 (cerrada) | 0% | 1% | 6% | 2% |
| Día 220 (reabrió) | **0%** | 39% | 23% | 34% |
| Día 260 | 24% | 56% | 44% | 54% |

Conclusión: Hedge "se olvida" de la avenida y tarda ~60 días en volver cuando reabre, mientras que FixedShare
tarda ~20. Por eso las rutas usan FixedShare y las maniobras usan EXP3.S.
