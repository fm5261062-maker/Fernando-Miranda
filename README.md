# SILENT: personaje 3D procedural (Python + Blender)

SILENT es un narrador silencioso para YouTube: observa y presenta historias sin
participar en ellas. Viste una sudadera gris con la capucha puesta. Su rostro
es un vacío negro, sin nariz ni boca, con dos ojos blancos verticales y
luminosos. Lleva pantalones oscuros, guantes y zapatillas.

Todo se genera desde código con `create_silent.py`, así que el proyecto es
reproducible: sin modelos externos, sin texturas de imagen y sin addons.

![Vista previa](output/silent_preview.png)

## Archivos

| Archivo | Contenido |
|---|---|
| `create_silent.py` | Script que construye el personaje, el rig, la animación, la escena y las exportaciones |
| `output/Silent.blend` | Escena de Blender organizada en colecciones |
| `output/silent_preview.png` | Vista previa 1280×720 (frame 104, gesto de presentación) |
| `output/Silent.glb` | Personaje con skin + rig + animación (sin escenario) |
| `output/silent_animation.mp4` | Animación completa, 640×360, 5 s, 24 fps (render rápido de prueba) |
| `requirements.txt` | Versión de `bpy` usada si no tienes Blender instalado |

### Organización del `.blend`

```
SILENT
├── SILENT_Rig        → SILENT_Rig (armature)
└── SILENT_Geometry   → SILENT_Hoodie, SILENT_Pants, SILENT_Gloves,
                        SILENT_Shoes, SILENT_FaceVoid, SILENT_Eyes
Set
├── Set_Cyclorama
└── Camera_Lights     → Camera, Camera_Target, Light_Key/Rim/Fill/Back
```

Cada malla tiene su modificador *Armature* (pesos suaves calculados por
proximidad a los huesos) y un *Subdivision Surface* (1 en viewport, 2 en
render). Los materiales son Principled BSDF sencillos (`M_Hoodie`, `M_Pants`,
`M_Eyes` con emisión, etc.), compatibles con Cycles, EEVEE y glTF.

### Rig

- **Body** (FK): `hips`, `spine`, `chest`, `neck`, `head`, `shoulder.L/R`,
  `upper_arm.L/R`, `forearm.L/R`, `hand.L/R`.
- **Legs**: `thigh`, `shin`, `foot` (.L/.R), movidos por IK.
- **Controls**: `root`, `foot_ik.L/R` (controlan los pies) y `knee_pole.L/R`
  (dirección de las rodillas).

Para animar en Blender, selecciona `SILENT_Rig`, entra en *Pose Mode* y rota
los huesos del grupo Body o mueve los `foot_ik`.

### Animación (frames 1–120, 24 fps)

| Frames | Acción |
|---|---|
| 1–61 | Entra caminando desde la izquierda (balanceo de brazos, rebote de cadera) |
| 54–68 | Se detiene y gira la cabeza hacia la cámara |
| 63–81 | Gira el cuerpo con dos pasos cortos hasta quedar de frente |
| 84–106 | Gesto de presentación: brazo derecho abierto, palma arriba, cabeza ligeramente inclinada |
| 106–120 | Mantiene la pose mientras respira |

La acción se llama `SILENT_Walk_Stop_Look_Present`. Tiene un keyframe por
frame porque se genera de forma procedural. Puedes editarla en el
Dope Sheet / Graph Editor o crear acciones nuevas sobre el mismo rig.

## Cómo ejecutarlo

### Opción A: con Blender instalado (4.2 o superior; probado con 5.2)

```bash
# Solo construir y guardar output/Silent.blend
blender -b -P create_silent.py

# Todo: .blend + vista previa + GLB
blender -b -P create_silent.py -- --preview --glb

# Además, el video de la animación (unos 5–6 min en CPU)
blender -b -P create_silent.py -- --preview --glb --video
```

Los argumentos del script van **después de `--`**.

### Opción B: sin Blender, con el módulo `bpy` de PyPI

`bpy` es Blender empaquetado como módulo de Python. Necesita la misma versión
de Python que su Blender: Python 3.13 para `bpy` 5.2.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python create_silent.py --preview --glb --video
```

### Opciones

| Opción | Efecto |
|---|---|
| `--outdir DIR` | Carpeta de salida (por defecto `./output`) |
| `--preview` | Renderiza `silent_preview.png` |
| `--preview-frame N` | Frame de la vista previa (por defecto 104) |
| `--samples N` | Muestras de Cycles para la vista previa (por defecto 32) |
| `--glb` | Exporta `Silent.glb` (personaje + rig + animación) |
| `--video` | Renderiza `silent_animation.mp4` |
| `--video-samples N` | Muestras por frame del video (por defecto 8) |
| `--video-scale P` | Porcentaje de 1280×720 para el video (por defecto 50) |

### Render de bajo coste

El render usa Cycles en CPU con muestreo adaptativo, rebotes limitados y
denoise. Con esta configuración, la vista previa tarda unos 15 s y cada frame
del video unos 2,7 s en una CPU de 4 núcleos. Si tienes Blender con GPU,
puedes abrir el `.blend` y cambiar a EEVEE para renders casi instantáneos.

## Ideas para seguir mejorándolo

- Formas de mano / dedos con huesos propios para gestos más expresivos.
- Pliegues de tela esculpidos o un mapa normal para la sudadera.
- Más acciones (idle, señalar, saludo) en el mismo rig.
- Variantes de color de los ojos para distintos tipos de historia.
