# Recursos que faltan (Las Crónicas de Silent)

Mientras falten estos recursos, el render muestra el sello **"PRUEBA TÉCNICA - ARTE
PROVISIONAL"**. Todo lo que hay ahora en `assets/` lo genera
`scripts/make_placeholder_assets.py` y está marcado con `"placeholder": true`.
**No es arte final.**

## 0. Referencia (bloqueante)
- [ ] **Hoja de diseño de Silent.** No llegó con el encargo. Las capas provisionales siguen solo la
  descripción escrita (capucha gris claro, rostro negro sin rasgos, dos ojos blancos verticales,
  guantes negros, pantalón oscuro). La forma de las zapatillas y la proporción de la capucha
  son suposiciones y hay que confirmarlas con la hoja.

## 1. Personaje: vista frontal (`assets/character/silent/front/`)
Hacen falta PNG con transparencia a 1500 px de altura total o más (1000 unidades de arte =
1,78 m). Cada parte se dibuja **en la pose de reposo**, en su sitio, respetando las
articulaciones de `rig.json`. La especificación completa está en `assets/character/README.md`.

| Archivo | Contenido | Estado |
|---|---|---|
| `hood_back.png` | Silueta exterior de la capucha | provisional |
| `face.png` | Vacío negro del rostro | provisional |
| `eyes.png` | Los dos ojos verticales (capa emisiva) | provisional |
| `hood_rim.png` | Borde de la abertura de la capucha (anillo) | provisional |
| `torso.png` | Sudadera: torso, bolsillo canguro, dobladillo | provisional |
| `drawstrings.png` | Cordones (capa independiente para que oscilen) | provisional |
| `pelvis.png` | Parte alta del pantalón | provisional |
| `upper_arm.L/R.png`, `forearm.L/R.png` | Mangas | provisional |
| `hand.L/R.png` | Guantes relajados | provisional |
| `thigh.L/R.png`, `shin.L/R.png` | Pantalón | provisional |
| `foot.L/R.png` | Zapatillas vistas de frente | provisional |
| `hand_point.L/R.png` | Guante señalando (variante de la acción `point`) | **FALTA** |

### Dibujos adicionales necesarios para una marcha frontal creíble
Un rig de recortes no puede inventar escorzos. Para que la marcha frontal deje de parecer
"tubos que se acortan" hacen falta:
- [ ] `thigh_fwd.L/R.png` y `shin_fwd.L/R.png`: pierna de paso con la rodilla hacia cámara
  (escorzo), para cambiar de dibujo en la fase de balanceo.
- [ ] `foot_lift.L/R.png`: suela vista al levantar el pie.
- [ ] `upper_arm_fwd.L/R.png` y `forearm_fwd.L/R.png`: brazo adelantado en escorzo.
- [ ] `shoulder.L/R.png`: deltoides/hombro como capa propia. Sin ella, la acción `point`
  abre un hueco en el hombro al levantar el brazo (verificado en la prueba de acciones).
- [ ] Pase de luz y pase de sombra de cada capa (o máscaras de sombra), para integrar al
  personaje en contraluz sin aplanarlo.

## 2. Personaje: vista lateral (`assets/character/silent/side/`)
- [ ] Juego completo de capas de perfil con su `rig.json` (`"view": "side"`). El código de
  `walk_side` existe, pero **no se ha validado visualmente porque no hay arte de perfil**.

## 3. Fondo: océano (`assets/backgrounds/ocean_dusk/`)
Capas pintadas de 2560×1440 con el horizonte en la fila `horizon_px` = 560. Cada elemento
del suelo debe ir en la fila `560 + 2015 × 1,5 / distancia` (ver `set.json`).

| Archivo | Distancia | Estado |
|---|---|---|
| `00_sky.png` | infinito | provisional |
| `01_clouds.png` (repetible en X) | 3000 m | provisional |
| `02_sea_far.png` | 400 m | provisional |
| `03_swells.png` (repetible en X) | 70 m | provisional |
| `04_surf.png` ola rompiente (repetible en X) | 34 m | provisional |
| `05_whitewater.png` espuma | 24 m | provisional |
| `06_shore_wash.png` lámina de orilla | 18 m | provisional |
| `07_sand.png` arena húmeda | suelo | provisional |
| `07b_sun_glare.png` reflejo del sol | infinito (enmascarado por la arena) | provisional |
| `08_foreground.png` rocas/hierba | 2,2 m | provisional (no aparece en los encuadres actuales) |

- [ ] Ideal: 2–3 dibujos de la ola rompiente (formación, rotura, espuma) para alternarlos.
  Ahora mismo la ola solo se desplaza y se desvanece.

## 4. Audio (`audio/`)
- [ ] **Narración**: no hay guion ni locución para esta prueba. Se espera
  `audio/narration/*.wav` (48 kHz) y el texto en el JSON de escena.
- [ ] **Música**: `audio/music/cronicas_tema_oceano.wav`. Ahora suena un colchón sintetizado
  provisional para comprobar niveles.
- [ ] **Foley de pasos en arena** (`audio/sfx/steps_sand_*.wav`, de 8 a 12 variaciones). Ahora
  son sintetizados.
- [ ] **Ambiente de mar** con olas reales (`audio/sfx/ocean_ambience.wav`). Ahora es
  sintetizado, pero sincronizado con el ciclo de olas visible.
