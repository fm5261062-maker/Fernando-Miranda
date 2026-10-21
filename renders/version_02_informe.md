# Informe: version_02 (prueba técnica de 10 s, Silent camina de frente ante el océano)

**Estado:** prueba técnica con arte **provisional**. No es un resultado cinematográfico
final. El personaje y el océano son capas generadas por código a partir de la descripción
escrita, porque la hoja de diseño de referencia no llegó con el encargo.

| | version_01 | version_02 |
|---|---|---|
| Archivo | `renders/version_01.mp4` | `renders/version_02.mp4` |
| Escena | `scenes/test_ocean_walk.json` | `scenes/test_ocean_walk_v02.json` |
| Formato | 1920×1080, 24 fps, 10,0 s, H.264 + AAC 48 kHz | igual |
| Tiempo de render (4 núcleos CPU) | 238 s | 242 s |

Nota de reproducibilidad: `version_01.mp4` se generó antes de los cambios de luz, fondo
y audio. Si hoy se re-renderiza `scenes/test_ocean_walk.json`, se conservan el montaje y la
marcha de la v01, pero se usan el fondo, la luz y el limitador nuevos.

Contexto: antes de este trabajo no existía ningún render de *Las Crónicas de Silent* en el
repositorio. version_01 es la primera prueba, generada en esta misma sesión, y es la que se
ha revisado.

## Revisión de version_01: los cinco problemas visuales más importantes (por impacto)

1. **Fundido encadenado entre dos tamaños de plano del mismo sujeto y en el mismo eje.**
   Durante los 0,5 s del fundido (12 fotogramas) aparece un Silent gigante y translúcido
   superpuesto al pequeño: una doble exposición que rompe la continuidad del personaje.
   Además, sh02 duraba 4,5 s y **no cumplía la regla de 5–12 s por plano**.
2. **Marcha poco legible.** Los brazos casi no se mueven: en el plano medio la mano recorre
   16 px en horizontal y 18 px en vertical a 1080p. El pie apenas se levanta, y en el 7,5 %
   de las muestras el IK de la pierna no alcanzaba el objetivo (38 de 504), lo que produce
   un pequeño salto en el apoyo del talón.
3. **Integración de luz.** En un contraluz de atardecer, Silent se ve demasiado claro y frío,
   con un borde de luz débil y sin sombra de contacto: parece pegado encima del fondo.
4. **Fondo con patrón repetido y reflejo mal colocado.** La ola rompiente repite el mismo
   tramo (autocorrelación 0,943), los regueros verticales parecen una valla, el oleaje apenas
   avanza y el reflejo del sol en la arena no queda debajo del sol: se desplaza con el dolly.
5. **Pico de audio por encima del objetivo.** Pico real de -0,7 dBFS en el MP4 final, con
   un objetivo de -1,5 dBFS (riesgo de distorsión al recomprimir en YouTube).

Lo que se comprobó y **estaba bien** en version_01:
- **Sin deslizamiento del pie apoyado:** 0,00 cm/frame.
- **Pasos sincronizados con la imagen:** 18 pasos, todos a ≤ 0,9 ms del contacto.
- **Sonoridad en objetivo:** -14,1 LUFS.

## Cambios realizados en version_02

| # | Problema | Cambio (código o montaje) | Archivo |
|---|---|---|---|
| 1 | Doble exposición y regla de duración | Fundido sustituido por un **corte en el apoyo del pie izquierdo** (t = 5,0 s): dos planos de 5,0 s. La continuidad de fase y posición en el corte se calcula al sub-fotograma. Se añadió un aviso automático cuando un plano incumple la regla de 5–12 s | `scenes/test_ocean_walk_v02.json`, `render.py` |
| 2 | Marcha | Balanceo de brazos 14° → 24°, codo +18° al adelantar, la mano cruza hacia la línea media, el pie se levanta 0,10 → 0,13 m y la cadera baja más en el contacto (0,034 → 0,048 m) para que la pierna llegue | `actions.py`, JSON v02 |
| 3 | Luz | Ambiente más bajo (0,60/0,63/0,74), borde de luz más intenso (1,1), sombra de contacto bajo los pies | `stage.py`, `set.json` |
| 4 | Fondo | Ola rompiente sin repetición visible (armónicos irregulares), menos regueros, oleaje con más recorrido (24/34/40 px), reflejo del sol en una capa a distancia infinita **enmascarada por la arena** | `make_placeholder_assets.py`, `stage.py`, `camera.py` |
| 5 | Audio | Limitador sobremuestreado ×4 **después** de la normalización a -14 LUFS, con 1 dB de margen para el AAC | `audio.py` |

**Guion:** no se ha modificado. No había narración y sigue sin haberla. El contenido es
el mismo (Silent camina de frente hacia cámara frente al mar). Lo único que cambió en el
montaje es el tipo de transición y la duración de los planos (6,0 + 4,5 s con fundido →
5,0 + 5,0 s con corte).

## Comparación medida (`scripts/qc_metrics.py`)

| Métrica | version_01 | version_02 |
|---|---|---|
| Planos dentro de la regla de 5–12 s | 1 de 2 | 2 de 2 |
| Fotogramas con doble exposición | 12 | 0 |
| Muestras con el IK de pierna recortado | 38/504 (7,5 %) | 3/480 (0,6 %) |
| Recorrido de la mano, plano general (x / y, px a 1080p) | 4,1 / 10,7 | 15,9 / 30,4 |
| Recorrido de la mano, plano medio (x / y, px a 1080p) | 16,1 / 18,0 | 31,4 / 63,5 |
| Recorrido vertical del tobillo, plano medio (px) | 93,8 | 104,9 |
| Autocorrelación de la capa de ola (1 = patrón repetido) | 0,943 | 0,686 |
| Sonoridad integrada | -14,1 LUFS | -14,3 LUFS |
| Pico real | -0,7 dBFS | -2,1 dBFS |

Estas cifras miden lo que dicen y nada más. Que la marcha "se vea más natural" o que la luz
"integre mejor" es mi valoración al revisar los fotogramas, no una medida. En version_02
los brazos alternan de forma visible y el corte ya no superpone dos Silent. La integración
de luz mejora poco: la sombra de contacto se aprecia poco en el plano general.

## Problemas pendientes (no resueltos)

1. **El arte es provisional y no puede coincidir con la hoja de diseño, porque no la tengo.**
   Es el problema de mayor impacto y no se resuelve con código.
2. **La marcha frontal sigue limitada por el arte.** Sin dibujos en escorzo, las piernas
   "se acortan" en lugar de doblar la rodilla hacia cámara, la rodilla no se lee y la
   capucha no tiene movimiento secundario propio. Quedan 3 muestras de IK recortadas.
3. **El fondo tiene costuras horizontales** entre la espuma, la lámina de orilla y la arena;
   la arena es plana y la capa de primer término (rocas) queda fuera de los dos encuadres.
4. **La luz del personaje es una aproximación.** Faltan pases de sombra pintados; el
   contraluz sigue aplanando volúmenes.
5. **Audio provisional:** pasos, mar y música están sintetizados. No hay narración. Los
   niveles y la sincronía se han verificado, pero el timbre no es de producción.
6. **Archivos pesados:** el grano de película eleva la tasa de bits del máster (unos 60 Mbps,
   72 MB por 10 s). Para revisión conviene una copia a CRF 23 con `-tune grain` (≈ 23 MB).
7. **Acciones sin validar en render:** `point` muestra defectos (hueco en el hombro, manga
   estirada, falta el guante señalando). `walk_side` necesita arte de perfil. `idle`,
   `head_turn` y `observe` solo se han revisado en fotogramas sueltos.

## Recursos gráficos adicionales necesarios
La lista detallada está en `assets/MISSING_ASSETS.md`. Lo prioritario:
1. Hoja de diseño de Silent (frente, perfil, espalda, 3/4).
2. Capas frontales definitivas según `assets/character/README.md`.
3. Dibujos en escorzo para la marcha frontal (pierna de paso, brazo adelantado, pie
   levantado) y capa de hombro.
4. Guante señalando (`hand_point.L/R`).
5. Juego completo de perfil para `walk_side`.
6. Fondos pintados del océano por capas, con 2–3 dibujos de la ola rompiente.
7. Locución, música y foley real de pasos en arena y de mar.
