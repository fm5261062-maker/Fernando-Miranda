# Episodio 1, Escena 1: "El océano de los secretos". Plan técnico

Formato: 1920×1080, 24 fps, 60 s, sin narración (la voz se añadirá después).
Referencias recibidas: seis planos, guardados en `assets/reference/escena1/` a
537×285 px. **La hoja de referencia del personaje no llegó con el mensaje**; el diseño se
ha tomado de los planos 2, 4, 5 y 6.

## 1. Lo que dicen las referencias sobre Silent

| Rasgo | Referencia | Consecuencia |
|---|---|---|
| Chaqueta gris clara casi blanca, con capucha y **cremallera**, larga hasta medio muslo | planos 2, 4, 5, 6 | Las capas frontales que hice antes (sudadera con bolsillo canguro) **no sirven**: hay que rehacerlas |
| **Mochila táctica negra** con tirantes, hebillas y cintas MOLLE | planos 2, 4, 5, 6 | Capa propia con movimiento secundario (rebote al caminar) |
| Rostro negro sin rasgos; ojos blancos alargados, algo inclinados y luminosos | planos 4, 6 | Capa emisiva con halo |
| Guantes negros, pantalón oscuro | planos 4, 5 | — |
| Estilo: ilustración pintada tipo anime, contraluz y bordes de luz marcados | todos | Luz de borde por capa y etalonaje por escenario |

Las imágenes se usan **solo como referencia**: a 537×285 no valen como capas (habría que
ampliarlas 3,6×) y además son planos completos, no piezas separadas para animar.

## 2. Cómo se construye cada plano

Motor: `scripts/silent2d` (Python + FFmpeg).
- **Personaje:** recortado por capas, con brazos y piernas resueltos en 3D y proyectados con
  perspectiva, más movimiento secundario (mochila, faldón, capucha) movido por el viento.
- **Escenarios:** capas a distancias reales; el paralaje sale de la geometría de la cámara.
- **Cámara:** virtual, con travelling, dolly, zoom y temblor de mano.
- **Montaje:** cada plano se exporta por separado y luego se monta.

| Plano | Tiempo | Construcción | Estado |
|---|---|---|---|
| 1 Océano nocturno | 0:00–0:10 | Travelling (dolly) hacia el horizonte. Capas: cielo + luna, nubes (desplazamiento), mar lejano/medio/cercano con oleaje animado por filas, crestas que rompen, niebla baja, rocas de primer término con espuma; reflejo de luna enmascarado por el agua | pendiente |
| 2 Silent hacia el acantilado | 0:10–0:20 | Rig de espaldas + caminata (`walk_front`, vista `back`); la cámara lo sigue con dolly. Capas: cielo, nubes, montañas, mar 45 m abajo, isla con cascadas (flujo), niebla, suelo de roca hasta el borde, rocas laterales, rama de primer término con viento | **prueba hecha, a revisión** |
| 3 Atlántida sumergida | 0:20–0:30 | Descenso de cámara (`height` y `horizon` animados), capas de ciudad a varias profundidades, rayos de luz (capas aditivas con desplazamiento), partículas en suspensión, peces, cáusticas | pendiente |
| 4 Primer plano de Silent | 0:30–0:40 | Rig de **3/4 a frontal** en primer plano: giro de cabeza (`head_turn`), parpadeo/brillo de ojos, brazo hacia cámara con escorzo (requiere dibujos específicos) | pendiente (bloqueado por arte) |
| 5 Transición a Grecia | 0:40–0:50 | Fundido de escenario por capas (noche → atardecer dorado), cambio progresivo de luz y etalonaje, Silent de espaldas observando (rig de espaldas + `idle`/`observe`) | pendiente |
| 6 Platón escribe | 0:50–1:00 | Segundo personaje (Platón) por capas: brazo y mano que escriben, cabeza que asiente. Silent de perfil/3/4 observando. Luz ambiental con polvo en suspensión | pendiente (bloqueado por arte) |

Audio: sin voz sintética. Cada pista se exporta por separado (`footsteps.wav`, `ambience.wav`
y, cuando exista, música), y se puede desactivar o ajustar desde el JSON de escena. Las
mezclas de referencia van a -24 LUFS para dejar sitio a tu narración. El ducking de
música y ambiente bajo la voz ya está implementado y se activa en cuanto añadas los
archivos de narración.

## 3. Recursos necesarios por plano

Se considera que una capa es "definitiva" cuando es una ilustración separada, con
transparencia, en la pose y escala indicadas, y con `"placeholder": false` en su JSON.

### Personaje Silent (común a todos los planos)
- [ ] **Hoja de diseño** (frente, espalda, perfil, 3/4) a buena resolución.
- [ ] Rig **de espaldas**: capucha, torso de chaqueta, faldón, mochila (con tirantes),
  brazos (brazo, antebrazo, guante), pantalón (muslo, pierna), botas. Ahora es provisional
  (`assets/character/silent/back`).
- [ ] Rig **frontal / 3/4**: capucha exterior, hueco del rostro, ojos (emisivos), borde de la
  capucha, chaqueta con cremallera, tirantes de la mochila por delante, brazos y guantes.
- [ ] Rig **de perfil** (plano 6), con la mochila de perfil.
- [ ] Poses dibujadas para el **plano 4**: mano extendida hacia cámara en escorzo (guante con
  la palma y los dedos hacia el espectador), antebrazo en escorzo y cabeza en 3/4 y de frente.
- [ ] Dibujos en escorzo para la marcha (pierna de paso, pie levantado, brazo adelantado),
  vistos de frente y de espaldas.

### Escenarios (capas pintadas 2560×1440 o mayores, con horizonte y distancias del `set.json`)
- [ ] **Plano 1, océano nocturno:** cielo con luna, 2 o 3 capas de nubes, mar lejano, oleaje
  medio, olas cercanas que rompen (2–3 dibujos), niebla, rocas de primer término a izquierda
  y derecha, espuma.
- [ ] **Plano 2, acantilado:** cielo y luna, nubes, montañas, mar, isla con cascadas (silueta
  y cascadas aparte), niebla, suelo de roca hasta el borde, rocas, rama seca. Ahora es
  provisional (`assets/backgrounds/cliff_night`).
- [ ] **Plano 3, Atlántida:** superficie del agua vista desde abajo, 3 o 4 capas de ciudad
  (lejana, media, cercana, ruinas en primer término), rayos de luz, cáusticas, peces
  (sprites), partículas.
- [ ] **Plano 4, primer plano:** cielo nocturno con luna desenfocado (puede salir del plano 1).
- [ ] **Plano 5, Grecia:** cielo dorado, montañas, mar, ciudad, acrópolis/Partenón, cipreses
  y rocas de primer término. Además, la versión nocturna o de transición de las capas
  compartidas.
- [ ] **Plano 6, estancia de Platón:** columnas y arco, estatua, mesa, pergamino, tintero y
  luz de atardecer.

### Personaje Platón (plano 6)
- [ ] Rig de 3/4: cabeza (barba), torso con túnica, brazo y antebrazo, mano con cálamo (2–3
  poses de escritura), mano que sujeta el pergamino.

### Audio
- [ ] Tu narración (WAV de 48 kHz), cuando la grabes.
- [ ] Música de la escena (opcional; ahora no hay ninguna).
- [ ] Foley real: pasos sobre roca, viento, mar, cascada, agua bajo la superficie, pluma
  sobre pergamino.
