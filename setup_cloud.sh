#!/usr/bin/env bash
# setup_cloud.sh - Instala Blender sin interfaz en Ubuntu/Debian y genera SILENT.
#
# Uso:
#   sudo ./setup_cloud.sh                 # instala Blender (apt) y genera .blend + preview + GLB
#   sudo ./setup_cloud.sh --video         # ademas renderiza el MP4
#   sudo ./setup_cloud.sh --official      # usa la build oficial de blender.org (con denoiser)
#
# Probado en Ubuntu 24.04 (Blender 4.0.2 de apt). Gratuito: no requiere cuentas
# ni credenciales.
set -euo pipefail

BLENDER_VERSION="4.2.3"   # para --official
OUTDIR="${OUTDIR:-output}"
EXTRA=()
OFFICIAL=0
for a in "$@"; do
  case "$a" in
    --official) OFFICIAL=1 ;;
    *) EXTRA+=("$a") ;;
  esac
done

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

cd "$(dirname "$0")"

if [ "$OFFICIAL" -eq 1 ]; then
  # Build oficial: Blender LTS con OpenImageDenoise, glTF y FFmpeg incluidos.
  $SUDO apt-get update
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl xz-utils ca-certificates libxi6 libxxf86vm1 libxfixes3 libxrender1 \
    libxkbcommon0 libsm6 libgl1 libegl1
  dir="blender-${BLENDER_VERSION}-linux-x64"
  if [ ! -x "$HOME/$dir/blender" ]; then
    curl -fL "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/${dir}.tar.xz" \
      | tar -xJ -C "$HOME"
  fi
  BLENDER="$HOME/$dir/blender"
else
  # Paquete de Ubuntu: Blender 4.0.2 (sin OpenImageDenoise; el script lo compensa).
  if ! command -v blender >/dev/null || ! dpkg -s python3-numpy >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      blender python3-numpy
  fi
  BLENDER="blender"
fi

"$BLENDER" --version | head -1
"$BLENDER" -b -P create_silent.py -- --outdir "$OUTDIR" --preview --glb "${EXTRA[@]}"
ls -la "$OUTDIR"
