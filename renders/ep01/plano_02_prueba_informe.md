# Prueba del plano 2: Silent camina de espaldas hacia el acantilado

**Para revisión. No continúo con los planos 1 y 3–6 hasta tu aprobación.**

| | |
|---|---|
| Vídeo | `renders/ep01/plano_02_prueba_caminata.mp4` (1920×1080, 24 fps, 10,0 s) |
| Escena | `scenes/ep01_atlantida/plano_02_prueba.json` |
| Personaje | `assets/character/silent/back/` (rig de espaldas, **capas provisionales**) |
| Escenario | `assets/backgrounds/cliff_night/` (**capas provisionales**) |
| Audio | sin voz; pistas aparte: `footsteps.wav` (pasos en roca), `ambience.wav` (viento, mar, cascada); mezcla de referencia a -24,2 LUFS, pico real -5,7 dBFS |
| Render | 310 s en CPU de 4 núcleos (vista previa 960×540: 41 s) |

## Qué está animado
- **Caminata de espaldas:**
  - Ciclo de 1,12 s, 0,78 m/s.
  - El pie de apoyo queda fijo en el suelo y la pierna se resuelve con IK en profundidad
    (se aleja de la cámara).
  - La cadera sube y baja (≈3,5 cm) y se balancea lateralmente.
  - La pelvis y los hombros se inclinan en contrafase.
  - Los brazos se balancean 20° y el codo se flexiona al adelantarse.
- **Ropa y viento:** la mochila rebota con retraso sobre un muelle amortiguado; el faldón de
  la chaqueta y la capucha se mueven con el viento. Las ráfagas siguen la **misma curva**
  que el sonido del viento.
- **Cámara:** sigue a Silent a la altura del hombro con un dolly que se acerca (5,0 → 4,5 m),
  un ligero paneo lateral y temblor de mano. El paralaje se calcula con la distancia real
  de cada capa: el borde del acantilado (17 m) se acerca, el mar y la isla (700–900 m) casi
  no se mueven y las rocas laterales pasan junto a la cámara.
- **Escenario:** las nubes se desplazan, el oleaje del mar está animado por filas, el agua de
  las cascadas cae, la niebla avanza, la rama de primer término se mueve con el viento, y
  hay brillos de luna en el agua, rocío en las cascadas y polvo arrastrado por el viento.

## Medidas (`renders/ep01/qc_plano_02_prueba.json`)
- IK de pierna recortado: 3 de 480 muestras (0,6 %).
- Recorrido de la mano: 37,7 px en horizontal y 116,3 px en vertical. Esta cifra incluye el
  cambio de escala mientras se aleja y la cámara se acerca.
- Recorrido vertical del tobillo: 106 px.

## Lo que tienes que saber antes de aprobar
1. **El arte es provisional.** Dibujé a Silent de espaldas siguiendo tus planos 2, 4, 5 y 6
   (chaqueta con capucha y cremallera, faldón largo, mochila táctica negra), pero no es una
   ilustración final. La hoja de referencia del personaje **no llegó** con el mensaje.
   Lo que se revisa aquí es **el movimiento, la cámara y el paralaje**, no el acabado.
2. **Límites de la caminata con recortes:** sin dibujos en escorzo, las piernas "se acortan"
   en lugar de doblar la rodilla, y la suela no se ve al levantar el pie. Con las capas
   ilustradas y 2–3 dibujos de pierna en escorzo, el mismo rig gana mucho.
3. **Encuadre:** acerqué la cámara para que la marcha se lea bien. Como consecuencia, la luna
   queda cortada en el borde superior. Puedo bajarla en la capa del cielo o abrir el plano,
   según prefieras.
4. **Escenario provisional** sencillo comparado con la referencia: la isla es una silueta con
   textura, no hay paredes de roca pintadas y el mar está hecho a pinceladas.

## Qué necesito para el render definitivo de este plano
Las capas ilustradas de Silent de espaldas, las capas pintadas del acantilado, y los dibujos
en escorzo de pierna y pie. La lista completa por plano está en `docs/ep01_escena1_plan.md`.
