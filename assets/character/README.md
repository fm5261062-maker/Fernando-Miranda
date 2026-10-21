# Especificación de capas del personaje

El rig está en `silent/<vista>/rig.json`. El motor no "anima imágenes sueltas": cada
capa es un **hueso entre dos articulaciones**. El solver calcula dónde está cada articulación
en cada frame y deforma la imagen para que su hueso de reposo coincida con el hueso
resuelto. Para sustituir el arte provisional por el definitivo:

1. Dibuja a Silent en la **pose de reposo frontal** (de pie, brazos caídos y algo separados)
   sobre un lienzo de 1500 px de altura total (o 3000 px para primeros planos).
2. Separa cada parte en su propia capa con transparencia. Deja solapes generosos en las
   articulaciones (rodilla, codo, hombro, cadera) para que no se abran huecos al girar.
3. Exporta cada capa recortada y anota en `rig.json` su `image_origin`: la esquina superior
   izquierda de la imagen recortada, en unidades de arte.
4. Si cambian las proporciones, ajusta `joints`. Unidades: 1000 = altura total;
   origen en el suelo entre los pies; Y hacia abajo; `.L` = izquierda del personaje =
   derecha de la pantalla.
5. Cambia `"placeholder": true` a `false` en las capas definitivas.

## Articulaciones (vista frontal, unidades de arte)

| Articulación | Posición | | Articulación | Posición |
|---|---|---|---|---|
| head_top | (0, -1020) | | pelvis | (0, -505) |
| neck | (0, -835) | | crotch | (0, -412) |
| shoulder.L | (107, -798) | | hip.L | (55, -494) |
| elbow.L | (118, -629) | | knee.L | (52, -281) |
| wrist.L | (126, -477) | | ankle.L | (51, -45) |
| hand_tip.L | (130, -376) | | toe.L | (51, 0) |

El lado `.R` es el espejo en X.

## Capas y orden de dibujo
`foot.R, foot.L, shin.R, shin.L, thigh.R, thigh.L, pelvis, torso, drawstrings,
upper_arm.R, upper_arm.L, forearm.R, forearm.L, hand.R, hand.L, hood_back, face, eyes, hood_rim`

- `eyes` es **emisiva**: no recibe la luz ambiente y genera su propio halo.
- `face`, `eyes` y `hood_rim` se desplazan por separado para simular el giro de cabeza
  (canal `head_turn`).
- Las variantes (`variants` en el JSON) sustituyen una capa durante una acción. Ejemplo:
  `hand.R → hand_point.R.png` mientras dura `point`.

## Acciones disponibles (`scripts/silent2d/actions.py`)
| Acción | Estado |
|---|---|
| `walk_front` | Probada en render (versiones 01 y 02) |
| `idle`, `head_turn`, `observe` | Funcionan (fotogramas de prueba); movimientos sutiles |
| `point` | Funciona, pero sin `hand_point` ni capa de hombro se ven defectos |
| `walk_side` | Código listo; necesita el arte de perfil (`silent/side/`) |
