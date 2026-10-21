"""
create_silent.py - Construye el personaje SILENT de forma 100 % procedural.

SILENT es un observador/narrador: sudadera gris con capucha, rostro vacio
negro y dos ojos blancos verticales luminosos. Este script genera:

  * Geometria del personaje (objetos organizados en colecciones).
  * Rig basico (FK para tronco/brazos/cabeza, IK para piernas).
  * Animacion de 5 s a 24 fps: caminar, detenerse, mirar a camara y
    hacer un gesto de presentacion.
  * Escena de render barata (Cycles CPU, pocas muestras + denoise).
  * Silent.blend, imagen de vista previa, exportacion GLB y (opcional)
    video de la animacion.

Uso (Blender instalado):
    blender -b -P create_silent.py -- --preview --glb

Uso (modulo `bpy` de PyPI, sin Blender instalado):
    python create_silent.py --preview --glb

Opciones: ver `--help`.
"""

import argparse
import math
import os
import sys

import bpy  # noqa: I001  (bpy debe importarse antes que bmesh en el modulo pip)
import bmesh
from mathutils import Matrix, Quaternion, Vector

V = Vector
FPS = 24
FRAME_START = 1
FRAME_END = 120  # 5 s * 24 fps

AX_X = V((1, 0, 0))
AX_Y = V((0, 1, 0))
AX_Z = V((0, 0, 1))


# --------------------------------------------------------------------------
# Argumentos
# --------------------------------------------------------------------------
def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    elif os.path.basename(argv[0]).lower().startswith("blender"):
        argv = []
    else:
        argv = argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description="Construye el personaje SILENT")
    p.add_argument("--outdir", default=os.path.join(here, "output"),
                   help="carpeta de salida (por defecto ./output)")
    p.add_argument("--preview", action="store_true",
                   help="renderiza la imagen de vista previa")
    p.add_argument("--preview-frame", type=int, default=104,
                   help="frame usado para la vista previa")
    p.add_argument("--samples", type=int, default=32,
                   help="muestras de Cycles para la vista previa")
    p.add_argument("--glb", action="store_true",
                   help="exporta el personaje animado a GLB")
    p.add_argument("--video", action="store_true",
                   help="renderiza la animacion completa (MP4, baja resolucion)")
    p.add_argument("--video-samples", type=int, default=8)
    p.add_argument("--video-scale", type=int, default=50,
                   help="porcentaje de 1280x720 para el video")
    return p.parse_args(argv)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoothstep(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ramp(f, a, b):
    return smoothstep((f - a) / (b - a))


def lerp(a, b, t):
    return a + (b - a) * t


def dist_point_segment(p, a, b):
    ab = b - a
    t = clamp((p - a).dot(ab) / max(ab.length_squared, 1e-9))
    return (p - (a + ab * t)).length


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def new_collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


# --------------------------------------------------------------------------
# Materiales (Principled BSDF: compatibles con Cycles, EEVEE y glTF)
# --------------------------------------------------------------------------
def make_material(name, color, rough=0.6, spec=0.5, sheen=0.0,
                  emission=None, strength=0.0, bump=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = spec
    if sheen and "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    if bump > 0:
        # Textura de tela muy barata: ruido fino -> bump (solo afecta al render)
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 420.0
        noise.inputs["Detail"].default_value = 2.0
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = bump
        nt.links.new(noise.outputs["Fac"], bmp.inputs["Height"])
        nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    m.diffuse_color = (*color, 1.0)  # color en viewport solido
    return m


def build_materials():
    return {
        "hoodie": make_material("M_Hoodie", (0.25, 0.26, 0.28), 0.85, 0.3,
                                sheen=0.4, bump=0.15),
        "rib": make_material("M_HoodieRib", (0.22, 0.225, 0.24), 0.9, 0.25,
                             sheen=0.3, bump=0.3),
        "string": make_material("M_Drawstring", (0.78, 0.78, 0.76), 0.7, 0.3),
        "metal": make_material("M_Aglet", (0.75, 0.76, 0.78), 0.3, 0.8),
        "pants": make_material("M_Pants", (0.035, 0.037, 0.045), 0.8, 0.3,
                               sheen=0.3, bump=0.12),
        "gloves": make_material("M_Gloves", (0.012, 0.012, 0.014), 0.45, 0.5),
        "shoe": make_material("M_ShoeUpper", (0.06, 0.062, 0.07), 0.6, 0.4),
        "sole": make_material("M_ShoeSole", (0.85, 0.85, 0.83), 0.55, 0.4),
        "void": make_material("M_FaceVoid", (0.0, 0.0, 0.0), 1.0, 0.0),
        "eyes": make_material("M_Eyes", (1.0, 1.0, 1.0), 0.4, 0.0,
                              emission=(0.92, 0.96, 1.0), strength=8.0),
        "floor": make_material("M_Floor", (0.018, 0.02, 0.025), 0.55, 0.4),
    }


# --------------------------------------------------------------------------
# Rig: definicion de huesos (espacio del armature = mundo en reposo)
# El personaje mira hacia -Y. Lado .L = +X (izquierda del personaje).
# --------------------------------------------------------------------------
def arm_points(s):
    shoulder = V((0.185 * s, 0.0, 1.435))
    elbow = V((0.283 * s, 0.01, 1.145))
    wrist = V((0.372 * s, -0.005, 0.90))
    tip = V((0.425 * s, -0.012, 0.715))
    return shoulder, elbow, wrist, tip


def leg_points(s):
    hip = V((0.095 * s, 0.0, 0.93))
    knee = V((0.10 * s, -0.02, 0.51))
    ankle = V((0.10 * s, 0.0, 0.09))
    ball = V((0.10 * s, -0.14, 0.025))
    return hip, knee, ankle, ball


def bone_defs():
    """(nombre, cabeza, cola, padre, deform, coleccion)"""
    d = [
        ("root", V((0, 0, 0)), V((0, -0.45, 0)), None, False, "Controls"),
        ("hips", V((0, 0, 0.95)), V((0, 0, 1.07)), "root", True, "Body"),
        ("spine", V((0, 0, 1.07)), V((0, 0, 1.25)), "hips", True, "Body"),
        ("chest", V((0, 0, 1.25)), V((0, 0, 1.46)), "spine", True, "Body"),
        ("neck", V((0, 0, 1.49)), V((0, -0.005, 1.575)), "chest", True, "Body"),
        ("head", V((0, -0.005, 1.575)), V((0, -0.005, 1.80)), "neck", True, "Body"),
    ]
    for side, s in (("L", 1), ("R", -1)):
        sh, el, wr, tip = arm_points(s)
        d += [
            (f"shoulder.{side}", V((0.025 * s, 0, 1.45)), V((0.165 * s, 0, 1.445)),
             "chest", True, "Body"),
            (f"upper_arm.{side}", sh, el, f"shoulder.{side}", True, "Body"),
            (f"forearm.{side}", el, wr, f"upper_arm.{side}", True, "Body"),
            (f"hand.{side}", wr, tip, f"forearm.{side}", True, "Body"),
        ]
        hip, knee, ankle, ball = leg_points(s)
        d += [
            (f"thigh.{side}", hip, knee, "hips", True, "Legs"),
            (f"shin.{side}", knee, ankle, f"thigh.{side}", True, "Legs"),
            (f"foot.{side}", ankle, ball, f"shin.{side}", True, "Legs"),
            (f"foot_ik.{side}", ankle, ball, "root", False, "Controls"),
            (f"knee_pole.{side}", V((0.10 * s, -0.6, 0.51)), V((0.10 * s, -0.7, 0.51)),
             "hips", False, "Controls"),
        ]
    return d


def build_rig(coll):
    data = bpy.data.armatures.new("SILENT_Rig")
    data.display_type = "OCTAHEDRAL"
    ob = bpy.data.objects.new("SILENT_Rig", data)
    ob.show_in_front = True
    coll.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)

    bcolls = {n: data.collections.new(n) for n in ("Body", "Legs", "Controls")}
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent, deform, bc in bone_defs():
        eb = data.edit_bones.new(name)
        eb.head, eb.tail = head, tail
        eb.align_roll(V((0, -1, 0)) if abs((tail - head).normalized().z) > 0.7 else AX_Z)
        eb.use_deform = deform
        if parent:
            eb.parent = data.edit_bones[parent]
            eb.use_connect = (data.edit_bones[parent].tail - head).length < 1e-5
        bcolls[bc].assign(eb)
    bpy.ops.object.mode_set(mode="OBJECT")

    for pb in ob.pose.bones:
        pb.rotation_mode = "QUATERNION"
    for side in ("L", "R"):
        ik = ob.pose.bones[f"shin.{side}"].constraints.new("IK")
        ik.name = "IK"
        ik.target, ik.subtarget = ob, f"foot_ik.{side}"
        ik.pole_target, ik.pole_subtarget = ob, f"knee_pole.{side}"
        ik.chain_count = 2
        cr = ob.pose.bones[f"foot.{side}"].constraints.new("COPY_ROTATION")
        cr.target, cr.subtarget = ob, f"foot_ik.{side}"
        ob.pose.bones[f"foot_ik.{side}"].color.palette = "THEME01"
        ob.pose.bones[f"knee_pole.{side}"].color.palette = "THEME09"
        calibrate_pole(ob, side)
    return ob


def calibrate_pole(arm, side):
    """Elige el pole_angle que hace que la rodilla apunte hacia delante."""
    ik_pb = arm.pose.bones[f"foot_ik.{side}"]
    ik_pb.location = local_loc(ik_pb, V((0, 0.05, 0.30)))  # fuerza flexion
    con = arm.pose.bones[f"shin.{side}"].constraints["IK"]
    best = None
    for deg in (-90, 90, 0, 180):
        con.pole_angle = math.radians(deg)
        bpy.context.view_layer.update()
        knee = arm.pose.bones[f"shin.{side}"].head
        hip_x = arm.pose.bones[f"thigh.{side}"].head.x
        score = knee.y + abs(knee.x - hip_x)
        if best is None or score < best[0]:
            best = (score, deg)
    con.pole_angle = math.radians(best[1])
    ik_pb.location = (0, 0, 0)
    bpy.context.view_layer.update()


def rest_segments():
    return {n: (h, t) for n, h, t, *_ in bone_defs()}


# --------------------------------------------------------------------------
# Geometria: constructor de prendas con pesos automaticos por proximidad
# --------------------------------------------------------------------------
class Garment:
    """Acumula piezas en un bmesh y asigna pesos de huesos a cada pieza."""

    def __init__(self, name, segs):
        self.name = name
        self.bm = bmesh.new()
        self.dl = self.bm.verts.layers.deform.verify()
        self.groups, self.mats, self.segs = [], [], segs

    def _gi(self, bone):
        if bone not in self.groups:
            self.groups.append(bone)
        return self.groups.index(bone)

    def _mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def part(self, verts, bones, mat, sharp=6.0):
        """Asigna material y pesos (inversa de distancia a cada hueso)."""
        verts = [v for v in verts if v.is_valid]
        mi = self._mi(mat)
        faces = {f for v in verts for f in v.link_faces}
        for f in faces:
            f.material_index = mi
            f.smooth = True
        segs = [(self._gi(b), *self.segs[b]) for b in bones]
        for v in verts:
            ws = [(gi, 1.0 / (dist_point_segment(v.co, h, t) + 0.01) ** sharp)
                  for gi, h, t in segs]
            tot = sum(w for _, w in ws)
            ws = [(gi, w / tot) for gi, w in ws if w / tot > 0.02]
            tot = sum(w for _, w in ws)
            for gi, w in ws:
                v[self.dl][gi] = w / tot

    def finish(self, coll, arm, subsurf=2):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        coll.objects.link(ob)
        for g in self.groups:
            ob.vertex_groups.new(name=g)
        ob.parent = arm
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        if subsurf:
            ss = ob.modifiers.new("Subdivision", "SUBSURF")
            ss.levels, ss.render_levels = 1, subsurf
        return ob


def add_tube(bm, centers, radii, segs=16, caps=(True, True), closed=False,
             ref=AX_X):
    """Tubo de seccion eliptica a lo largo de una polilinea."""
    centers = [V(c) for c in centers]
    n = len(centers)
    rings, verts = [], []
    for i, c in enumerate(centers):
        if closed:
            t = centers[(i + 1) % n] - centers[i - 1]
        elif i == 0:
            t = centers[1] - centers[0]
        elif i == n - 1:
            t = centers[-1] - centers[-2]
        else:
            t = centers[i + 1] - centers[i - 1]
        t.normalize()
        u = ref - t * ref.dot(t)
        if u.length < 1e-4:
            u = AX_Y - t * t.y
        u.normalize()
        w = t.cross(u)
        r = radii[i]
        rx, ry = (r, r) if isinstance(r, (int, float)) else r
        ring = [bm.verts.new(c + u * (rx * math.cos(a)) + w * (ry * math.sin(a)))
                for a in (2 * math.pi * k / segs for k in range(segs))]
        rings.append(ring)
        verts += ring
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(segs):
            k1 = (k + 1) % segs
            bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
    if not closed:
        if caps[0]:
            bm.faces.new(rings[0])
        if caps[1]:
            bm.faces.new(rings[-1])
    return verts


def add_ellipsoid(bm, center, radii, u=24, v=14, matrix=None):
    verts = bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v,
                                      radius=1.0)["verts"]
    m = Matrix.Translation(V(center)) @ (matrix or Matrix.Identity(4)) @ \
        Matrix.Diagonal((*radii, 1.0))
    bmesh.ops.transform(bm, matrix=m, verts=verts)
    return verts


def add_box(bm, center, size, matrix=None):
    verts = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    m = Matrix.Translation(V(center)) @ (matrix or Matrix.Identity(4)) @ \
        Matrix.Diagonal((*size, 1.0))
    bmesh.ops.transform(bm, matrix=m, verts=verts)
    return verts


def frame_along(head, tail, mirror=False):
    """Matriz que lleva el eje -Z canonico a la direccion head->tail."""
    z = -(V(tail) - V(head)).normalized()
    x = (AX_X - z * z.x).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = V(head)
    if mirror:
        m = m @ Matrix.Diagonal((-1, 1, 1, 1))
    return m


# --------------------------------------------------------------------------
# Piezas del personaje
# --------------------------------------------------------------------------
HOOD_C = V((0.0, 0.012, 1.672))       # centro de la capucha
HOOD_R = V((0.128, 0.150, 0.160))     # radios de la capucha
OPEN_C = V((0.0, 0.0, 1.662))         # centro de la abertura del rostro
OPEN_R = (0.083, 0.112)               # radios (x, z) de la abertura
FACE_C = V((0.0, -0.035, 1.662))
FACE_R = V((0.094, 0.098, 0.118))


def hood_surface_y(x, z):
    k = 1 - (x / HOOD_R.x) ** 2 - ((z - HOOD_C.z) / HOOD_R.z) ** 2
    return HOOD_C.y - HOOD_R.y * math.sqrt(max(k, 0.0))


def build_hoodie(segs, mats):
    g = Garment("SILENT_Hoodie", segs)
    bm = g.bm
    # Torso: tubo eliptico desde el dobladillo hasta el cuello
    prof = [  # z, rx, ry, y-offset
        (0.875, 0.170, 0.122, 0.000),
        (0.95, 0.168, 0.118, -0.002),
        (1.05, 0.163, 0.113, -0.004),
        (1.17, 0.172, 0.120, -0.008),
        (1.29, 0.186, 0.126, -0.010),
        (1.38, 0.186, 0.118, -0.006),
        (1.445, 0.160, 0.103, 0.000),
        (1.50, 0.110, 0.088, 0.008),
        (1.54, 0.075, 0.072, 0.010),
    ]
    vs = add_tube(bm, [(0, y, z) for z, _, _, y in prof],
                  [(rx, ry) for _, rx, ry, _ in prof], segs=24)
    g.part(vs, ["hips", "spine", "chest", "neck"], mats["hoodie"])
    # Dobladillo acanalado
    vs = add_tube(bm, [(0, 0, 0.845), (0, 0, 0.885)],
                  [(0.176, 0.127), (0.176, 0.127)], segs=24)
    g.part(vs, ["hips", "spine"], mats["rib"])
    # Bolsillo canguro
    vs = add_ellipsoid(bm, (0, -0.058, 1.012), (0.118, 0.072, 0.064), u=24, v=12)
    g.part(vs, ["hips", "spine"], mats["hoodie"])

    # Mangas + deltoides + puno
    for side, s in (("L", 1), ("R", -1)):
        sh, el, wr, _ = arm_points(s)
        top = V((0.105 * s, 0.0, 1.425))
        pts = [top, sh.lerp(top, 0.45), sh + V((0, 0, -0.008)),
               sh.lerp(el, 0.35), sh.lerp(el, 0.75), el,
               el.lerp(wr, 0.4), el.lerp(wr, 0.8), wr.lerp(el, 0.06)]
        rad = [0.05, 0.058, 0.060, 0.058, 0.054, 0.052, 0.049, 0.045, 0.043]
        vs = add_tube(bm, pts, rad, segs=16)
        g.part(vs, ["chest", f"shoulder.{side}", f"upper_arm.{side}",
                    f"forearm.{side}"], mats["hoodie"])
        c0, c1 = wr.lerp(el, 0.10), wr.lerp(el, -0.005)
        vs = add_tube(bm, [c0, c1], [0.040, 0.037], segs=16)
        g.part(vs, [f"forearm.{side}", f"hand.{side}"], mats["rib"])

    # Capucha: elipsoide con abertura frontal
    vs = add_ellipsoid(bm, HOOD_C, HOOD_R, u=32, v=20)
    for v in vs:  # pico suave arriba/atras y caida hacia los hombros
        d = v.co - HOOD_C
        if d.z > 0.08 and d.y > 0.0:
            v.co += V((0, 0.025, 0.012)) * (d.z / HOOD_R.z) * (d.y / HOOD_R.y)
        if d.z < -0.06:
            k = (-0.06 - d.z) / 0.1
            v.co.x *= 1 + 0.35 * k
            v.co.y += 0.03 * k
    cut = []
    for v in vs:
        if v.co.y < OPEN_C.y - 0.02 and \
                (v.co.x / OPEN_R[0]) ** 2 + ((v.co.z - OPEN_C.z) / OPEN_R[1]) ** 2 < 1:
            cut.append(v)
    bmesh.ops.delete(bm, geom=cut, context="VERTS")
    vs = [v for v in vs if v.is_valid]
    # Grosor de la tela: copia interior ligeramente reducida
    inner = bmesh.ops.duplicate(bm, geom=list({f for v in vs for f in v.link_faces}))
    ivs = [e for e in inner["geom"] if isinstance(e, bmesh.types.BMVert)]
    for v in ivs:
        v.co = HOOD_C + (v.co - HOOD_C) * 0.93
    bmesh.ops.reverse_faces(bm, faces=[e for e in inner["geom"]
                                      if isinstance(e, bmesh.types.BMFace)])
    g.part(vs + ivs, ["head", "neck"], mats["hoodie"], sharp=4)
    # Borde de la abertura (dobladillo de la capucha)
    rim = []
    for k in range(40):
        a = 2 * math.pi * k / 40
        x = OPEN_R[0] * 1.02 * math.cos(a)
        z = OPEN_C.z + OPEN_R[1] * 1.02 * math.sin(a)
        rim.append((x, hood_surface_y(x * 0.97, z) + 0.004, z))
    vs = add_tube(bm, rim, [0.013] * 40, segs=10, closed=True)
    g.part(vs, ["head"], mats["hoodie"])
    # Cuello/cowl que une capucha y torso por detras
    vs = add_tube(bm, [(0, 0.012, 1.47), (0, 0.022, 1.53), (0, 0.03, 1.585)],
                  [(0.15, 0.115), (0.122, 0.11), (0.112, 0.112)], segs=24)
    g.part(vs, ["chest", "neck", "head"], mats["hoodie"])
    # Cordones con puntas metalicas
    for s in (1, -1):
        top = V((0.036 * s, hood_surface_y(0.036, 1.56) - 0.006, 1.565))
        pts = [top, top + V((0.004 * s, -0.012, -0.06)),
               top + V((0.008 * s, -0.018, -0.13)),
               top + V((0.011 * s, -0.020, -0.19))]
        vs = add_tube(bm, pts, [0.0045] * 4, segs=8)
        g.part(vs, ["neck", "chest"], mats["string"])
        end = pts[-1]
        vs = add_tube(bm, [end, end + V((0.001 * s, -0.001, -0.028))],
                      [0.0055, 0.005], segs=8)
        g.part(vs, ["chest"], mats["metal"])
    return g


def build_face(segs, mats):
    g = Garment("SILENT_FaceVoid", segs)
    vs = add_ellipsoid(g.bm, FACE_C, FACE_R, u=24, v=16)
    g.part(vs, ["head"], mats["void"])
    return g


def build_eyes(segs, mats):
    g = Garment("SILENT_Eyes", segs)
    for s in (1, -1):
        x, z = 0.034 * s, 1.672
        k = 1 - (x / FACE_R.x) ** 2 - ((z - FACE_C.z) / FACE_R.z) ** 2
        y = FACE_C.y - FACE_R.y * math.sqrt(k) - 0.004
        yaw = Matrix.Rotation(math.atan2(x, FACE_R.y) * 0.8, 4, "Z")
        vs = add_ellipsoid(g.bm, (x, y, z), (0.0135, 0.008, 0.040),
                           u=16, v=12, matrix=yaw)
        g.part(vs, ["head"], mats["eyes"])
    return g


def build_pants(segs, mats):
    g = Garment("SILENT_Pants", segs)
    vs = add_tube(g.bm, [(0, 0.005, 1.02), (0, 0.0, 0.93), (0, 0.0, 0.84)],
                  [(0.156, 0.108), (0.17, 0.112), (0.15, 0.10)], segs=20)
    g.part(vs, ["hips", "thigh.L", "thigh.R"], mats["pants"])
    for side, s in (("L", 1), ("R", -1)):
        hip, knee, ankle, _ = leg_points(s)
        hip = hip + V((-0.005 * s, 0, 0.02))
        pts = [hip, hip.lerp(knee, 0.35), hip.lerp(knee, 0.7), knee,
               knee.lerp(ankle, 0.3), knee.lerp(ankle, 0.65),
               knee.lerp(ankle, 0.88), knee.lerp(ankle, 0.95)]
        rad = [0.094, 0.088, 0.076, 0.065, 0.064, 0.056, 0.052, 0.053]
        vs = add_tube(g.bm, pts, rad, segs=16)
        g.part(vs, ["hips", f"thigh.{side}", f"shin.{side}"], mats["pants"])
    return g


def build_gloves(segs, mats):
    g = Garment("SILENT_Gloves", segs)
    for side, s in (("L", 1), ("R", -1)):
        _, el, wr, tip = arm_points(s)
        bm = g.bm
        new = []
        # mano canonica (izquierda): munieca en el origen, dedos hacia -Z,
        # palma hacia -X (hacia el cuerpo), pulgar hacia delante (-Y)
        new += add_box(bm, (0.0, 0.0, -0.052), (0.038, 0.094, 0.108))
        fingers = [(-0.031, 0.074), (-0.0105, 0.084), (0.0105, 0.080), (0.030, 0.066)]
        for y, ln in fingers:
            p0 = V((0.002, y, -0.088))
            pts = [p0, p0 + V((-0.004, 0, -ln * 0.5)), p0 + V((-0.014, 0, -ln))]
            new += add_tube(bm, pts, [0.0115, 0.0108, 0.0098], segs=8)
        t0 = V((-0.006, -0.036, -0.03))
        new += add_tube(bm, [t0, t0 + V((-0.014, -0.022, -0.035)),
                             t0 + V((-0.022, -0.03, -0.068))],
                        [0.0135, 0.012, 0.011], segs=8)
        new += add_tube(bm, [(0, 0, 0.035), (0, 0, -0.01)],
                        [(0.026, 0.036), (0.022, 0.04)], segs=12)  # punio
        bmesh.ops.transform(bm, matrix=frame_along(wr, tip, mirror=(s < 0)),
                            verts=new)
        g.part(new, [f"forearm.{side}", f"hand.{side}"], mats["gloves"], sharp=8)
    return g


def build_shoes(segs, mats):
    g = Garment("SILENT_Shoes", segs)
    prof = [  # y, rx, rz, zc
        (0.078, 0.030, 0.035, 0.055),
        (0.055, 0.044, 0.058, 0.068),
        (0.0, 0.048, 0.070, 0.072),
        (-0.06, 0.051, 0.052, 0.055),
        (-0.13, 0.052, 0.040, 0.044),
        (-0.18, 0.046, 0.032, 0.036),
        (-0.205, 0.026, 0.020, 0.032),
    ]
    for side, s in (("L", 1), ("R", -1)):
        x = 0.10 * s
        vs = add_tube(g.bm, [(x, y, zc) for y, _, _, zc in prof],
                      [(rx, rz) for _, rx, rz, _ in prof], segs=16)
        g.part(vs, [f"foot.{side}"], mats["shoe"])
        vs = add_tube(g.bm, [(x, y + 0.004 * (1 if y > 0 else -1), 0.014)
                             for y, *_ in prof],
                      [(rx + 0.006, 0.015) for _, rx, *_ in prof], segs=16)
        g.part(vs, [f"foot.{side}"], mats["sole"])
        vs = add_tube(g.bm, [(x, 0.01, 0.115), (x, 0.012, 0.135)],
                      [(0.048, 0.052), (0.046, 0.05)], segs=16)  # tobillera
        g.part(vs, [f"foot.{side}"], mats["shoe"])
    return g


# --------------------------------------------------------------------------
# Escena: plato, luces y camara (barata y cinematografica)
# --------------------------------------------------------------------------
CAM_POS = V((0.35, -5.6, 1.32))
CAM_TARGET = V((-0.5, 0.0, 1.0))


def build_set(coll, mats):
    # Ciclorama: suelo que se curva hacia una pared al fondo
    bm = bmesh.new()
    prof = [(-9.0, 0.0), (2.5, 0.0)]
    for k in range(1, 9):
        a = (math.pi / 2) * k / 8
        prof.append((2.5 + 1.5 * math.sin(a), 1.5 - 1.5 * math.cos(a)))
    prof.append((4.0, 6.0))
    rows = [[bm.verts.new((x, y, z)) for y, z in prof] for x in (-9.0, 9.0)]
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new("Set_Cyclorama")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats["floor"])
    ob = bpy.data.objects.new("Set_Cyclorama", me)
    coll.objects.link(ob)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.012, 0.014, 0.02, 1)
    bg.inputs["Strength"].default_value = 1.0
    bpy.context.scene.world = world


def build_lights_camera(coll):
    target = bpy.data.objects.new("Camera_Target", None)
    target.location = CAM_TARGET
    coll.objects.link(target)

    def area(name, loc, energy, color, size):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.color, ld.size = energy, color, size
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        coll.objects.link(lo)
        tr = lo.constraints.new("TRACK_TO")
        tr.target = target
        return lo

    area("Light_Key", (-2.6, -3.2, 3.6), 190, (1.0, 0.93, 0.85), 2.0)
    area("Light_Rim", (2.4, 2.6, 2.8), 420, (0.55, 0.72, 1.0), 1.5)
    area("Light_Fill", (3.2, -2.8, 1.4), 35, (0.8, 0.85, 1.0), 3.0)
    area("Light_Back", (-1.0, 3.6, 3.5), 110, (0.6, 0.6, 0.75), 4.0)

    cd = bpy.data.cameras.new("Camera")
    cd.lens = 40
    cd.dof.use_dof = False
    cam = bpy.data.objects.new("Camera", cd)
    cam.location = CAM_POS
    coll.objects.link(cam)
    tr = cam.constraints.new("TRACK_TO")
    tr.target = target
    bpy.context.scene.camera = cam
    return cam


# --------------------------------------------------------------------------
# Animacion procedural (se hornea un key por frame)
# --------------------------------------------------------------------------
def local_loc(pb, delta_world):
    return pb.bone.matrix_local.to_3x3().inverted() @ V(delta_world)


def local_rot(pb, q_world):
    """Rotacion expresada en ejes de reposo del armature -> espacio del hueso."""
    rq = pb.bone.matrix_local.to_quaternion()
    return rq.inverted() @ q_world @ rq


def Q(axis, deg):
    return Quaternion(axis, math.radians(deg))


class FootTrack:
    """Huella de un pie: posicion inicial + lista de pasos (swing)."""

    def __init__(self, pos, yaw, steps, lift=0.09):
        self.pos, self.yaw, self.steps, self.lift = V(pos), yaw, steps, lift

    def at(self, f):
        pos, yaw = self.pos.copy(), self.yaw
        for f0, f1, p1, y1, *opt in self.steps:
            lift = opt[0] if opt else self.lift
            if f < f0:
                break
            if f <= f1:
                u = (f - f0) / (f1 - f0)
                e = 0.35 * u + 0.65 * smoothstep(u)
                p = pos.lerp(V(p1), e)
                pitch = 22 * math.sin(math.pi * u) * (1 - 2 * u) * (lift / 0.09)
                return V((p.x, p.y, lift * math.sin(math.pi * u))), \
                    lerp(yaw, y1, e), pitch, u
            pos, yaw = V(p1), y1
        return V((pos.x, pos.y, 0.0)), yaw, 0.0, None


def build_tracks():
    w = 0.09  # media separacion lateral durante la marcha
    left = FootTrack((-2.1, w), 90, [
        (15, 27, (-1.2, w), 90),
        (39, 51, (0.0, w), 90),
        (71, 80, (0.10, 0.0), 0, 0.05),
    ])
    right = FootTrack((-2.1, -w), 90, [
        (4, 15, (-1.8, -w), 90),
        (27, 39, (-0.6, -w), 90),
        (51, 61, (0.0, -w), 90, 0.06),
        (64, 73, (-0.10, 0.0), 0, 0.05),
    ])
    return left, right


def body_yaw(f):
    return lerp(90.0, 0.0, ramp(f, 63, 81))


def animate(arm):
    scn = bpy.context.scene
    pbs = arm.pose.bones
    left, right = build_tracks()
    seg = rest_segments()
    leg_len = (seg["thigh.L"][1] - seg["thigh.L"][0]).length + \
        (seg["shin.L"][1] - seg["shin.L"][0]).length
    look = CAM_POS - V((0, 0, 1.67))
    cam_yaw = math.degrees(math.atan2(look.x, -look.y))
    cam_pitch = math.degrees(math.atan2(-look.z, look.xy.length))

    for f in range(FRAME_START, FRAME_END + 1):
        fl = {}
        for side, tr in (("L", left), ("R", right)):
            fl[side] = tr.at(f)
        yaw = body_yaw(f)
        fwd = Quaternion(AX_Z, math.radians(yaw)) @ V((0, -1, 0))
        center = (fl["L"][0].xy + fl["R"][0].xy) / 2
        # oscilacion de la marcha: diferencia de avance entre pies
        dfoot = (fl["L"][0] - fl["R"][0]).xy.dot(fwd.xy)  # >0: pie L delante
        swing = clamp(dfoot / 0.6, -1, 1)
        walk_w = 1.0 - ramp(f, 56, 64)

        # altura de cadera: reposo + rebote, limitada por el alcance de piernas
        bob = 0.0
        for side in ("L", "R"):
            u = fl[side][3]
            if u is not None:
                bob = max(bob, 0.014 * math.sin(math.pi * u))
        dz = -0.022 + bob * walk_w + 0.003 * math.sin(f * 0.18) * (1 - walk_w)
        hip_yaw = yaw - 5.0 * swing * walk_w
        rz = Quaternion(AX_Z, math.radians(hip_yaw))
        for side, s in (("L", 1), ("R", -1)):
            joint_off = rz @ V((0.095 * s, 0.0, -0.02))
            ankle = fl[side][0] + V((0, 0, 0.09))
            hz = V((center.x, center.y)) + joint_off.xy
            horiz = (ankle.xy - hz).length
            reach = math.sqrt(max((0.985 * leg_len) ** 2 - horiz ** 2, 0.0))
            dz = min(dz, ankle.z + reach - joint_off.z - 0.95)

        pbs["hips"].location = local_loc(pbs["hips"], V((center.x, center.y, dz)))
        pbs["hips"].rotation_quaternion = local_rot(pbs["hips"], rz)

        for side in ("L", "R"):
            pos, fyaw, pitch, _ = fl[side]
            pb = pbs[f"foot_ik.{side}"]
            pb.location = local_loc(pb, pos - V((0.10 if side == "L" else -0.10, 0, 0)))
            pb.rotation_quaternion = local_rot(pb, Q(AX_Z, fyaw) @ Q(AX_X, pitch))

        # Tronco
        gest = ramp(f, 84, 97)
        settle = math.sin(math.pi * ramp(f, 95, 106)) * 0.15
        breath = math.sin(f * 0.16) * (1 - walk_w)
        pbs["spine"].rotation_quaternion = local_rot(
            pbs["spine"], Q(AX_Z, 2.5 * swing * walk_w) @
            Q(AX_X, 4.0 * walk_w - 1.5 * gest))
        pbs["chest"].rotation_quaternion = local_rot(
            pbs["chest"], Q(AX_Z, 4.0 * swing * walk_w - 4.0 * gest) @
            Q(AX_X, -0.8 * breath - 1.0 * gest))

        # Cabeza: mira al frente al caminar y luego a camara
        look_w = ramp(f, 54, 68)
        chest_yaw = hip_yaw + 6.5 * swing * walk_w - 4.0 * gest
        head_yaw = clamp(lerp(0.0, cam_yaw - chest_yaw, look_w), -75, 75)
        head_pitch = lerp(-3.0 * walk_w, cam_pitch, look_w) + 2.0 * breath * 0.3
        tilt = 7.0 * gest - 2.0 * settle
        pbs["neck"].rotation_quaternion = local_rot(
            pbs["neck"], Q(AX_Z, head_yaw * 0.35) @ Q(AX_X, head_pitch * 0.3))
        pbs["head"].rotation_quaternion = local_rot(
            pbs["head"], Q(AX_Z, head_yaw * 0.65) @ Q(AX_X, head_pitch * 0.7) @
            Q(AX_Y, tilt))

        # Brazos: balanceo opuesto a las piernas + gesto con el brazo derecho
        for side, s in (("L", 1), ("R", -1)):
            arm_sw = (-swing if side == "L" else swing) * walk_w  # >0: adelante
            add = 13.0 * s
            fwd_deg = -20.0 * arm_sw - 3.0
            elbow = -12.0 - 14.0 * max(arm_sw, 0) - 4.0 * (1 - walk_w)
            twist = 0.0
            wrist = 0.0
            if side == "R":
                g = gest - settle * 0.5
                add = lerp(add, 48.0, g)
                fwd_deg = lerp(fwd_deg, -40.0, g)
                elbow = lerp(elbow, -42.0, g)
                twist = lerp(0.0, 115.0, g)
                wrist = lerp(0.0, -18.0, g)
            else:
                elbow -= 6.0 * gest
            pbs[f"upper_arm.{side}"].rotation_quaternion = local_rot(
                pbs[f"upper_arm.{side}"], Q(AX_Y, add) @ Q(AX_X, fwd_deg))
            pbs[f"forearm.{side}"].rotation_quaternion = local_rot(
                pbs[f"forearm.{side}"], Q(AX_X, elbow)) @ \
                Quaternion(AX_Y, math.radians(twist * -s))
            pbs[f"hand.{side}"].rotation_quaternion = local_rot(
                pbs[f"hand.{side}"], Q(AX_Y, wrist * s))

        for pb in pbs:
            if pb.name in ("hips",) or pb.name.startswith("foot_ik"):
                pb.keyframe_insert("location", frame=f, group=pb.name)
            if pb.name not in ("root",) and not pb.name.startswith(
                    ("knee_pole", "thigh", "shin", "foot.")):
                pb.keyframe_insert("rotation_quaternion", frame=f, group=pb.name)

    act = arm.animation_data.action
    act.name = "SILENT_Walk_Stop_Look_Present"
    act.use_fake_user = True
    scn.frame_set(FRAME_START)


# --------------------------------------------------------------------------
# Render y exportacion
# --------------------------------------------------------------------------
def setup_render(samples):
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = samples
    scn.cycles.use_adaptive_sampling = True
    scn.cycles.adaptive_threshold = 0.05
    scn.cycles.max_bounces = 4
    scn.cycles.diffuse_bounces = 2
    scn.cycles.glossy_bounces = 2
    scn.cycles.transmission_bounces = 0
    scn.cycles.volume_bounces = 0
    scn.cycles.use_denoising = True
    scn.render.resolution_x, scn.render.resolution_y = 1280, 720
    scn.render.resolution_percentage = 100
    scn.render.fps = FPS
    scn.frame_start, scn.frame_end = FRAME_START, FRAME_END
    try:
        scn.view_settings.view_transform = "AgX"
        scn.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scn.render.film_transparent = False


def render_still(path, frame, samples):
    scn = bpy.context.scene
    scn.cycles.samples = samples
    scn.frame_set(frame)
    scn.render.image_settings.file_format = "PNG"
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)


def render_video(path, samples, scale):
    scn = bpy.context.scene
    scn.cycles.samples = samples
    scn.render.resolution_percentage = scale
    try:
        scn.render.image_settings.media_type = "VIDEO"  # Blender 5.x
    except (AttributeError, TypeError):
        pass
    scn.render.image_settings.file_format = "FFMPEG"
    scn.render.ffmpeg.format = "MPEG4"
    scn.render.ffmpeg.codec = "H264"
    scn.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scn.render.filepath = path
    bpy.ops.render.render(animation=True)
    scn.render.resolution_percentage = 100


def export_glb(path, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True,
        export_apply=True, export_animations=True, export_skins=True,
        export_yup=True)


# --------------------------------------------------------------------------
def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    reset_scene()
    scn = bpy.context.scene
    scn.name = "SILENT"
    scn.unit_settings.system = "METRIC"

    c_char = new_collection("SILENT")
    c_rig = new_collection("SILENT_Rig", c_char)
    c_geo = new_collection("SILENT_Geometry", c_char)
    c_set = new_collection("Set")
    c_cam = new_collection("Camera_Lights", c_set)

    mats = build_materials()
    arm = build_rig(c_rig)
    segs = rest_segments()
    geo = [b.finish(c_geo, arm) for b in (
        build_hoodie(segs, mats), build_pants(segs, mats),
        build_gloves(segs, mats), build_shoes(segs, mats),
        build_face(segs, mats), build_eyes(segs, mats))]

    build_set(c_set, mats)
    build_lights_camera(c_cam)
    setup_render(args.samples)
    animate(arm)
    scn.frame_set(args.preview_frame)

    blend = os.path.join(args.outdir, "Silent.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    print(f"[SILENT] guardado: {blend}")

    if args.glb:
        glb = os.path.join(args.outdir, "Silent.glb")
        export_glb(glb, [arm] + geo)
        print(f"[SILENT] exportado: {glb}")
    if args.preview:
        png = os.path.join(args.outdir, "silent_preview.png")
        render_still(png, args.preview_frame, args.samples)
        print(f"[SILENT] vista previa: {png}")
    if args.video:
        mp4 = os.path.join(args.outdir, "silent_animation.mp4")
        render_video(mp4, args.video_samples, args.video_scale)
        print(f"[SILENT] video: {mp4}")


if __name__ == "__main__":
    main()
