#!/usr/bin/env bash
#
# Instalador de sysmon
#   sudo ./install.sh              instala /usr/local/bin/sysmon
#   sudo ./install.sh --uninstall  lo desinstala
#
# Notas de seguridad:
#   - Las dependencias se instalan desde el gestor de paquetes de la
#     distribución (paquetes firmados), nunca con pip como root.
#   - El script se instala con 'install' (root:root, 0755) en un archivo
#     temporal y se mueve de forma atómica.
#   - El shebang se fija a la ruta absoluta de python3 con -I (modo aislado),
#     para que PYTHONPATH o módulos en el directorio actual no puedan
#     inyectar código cuando se ejecuta con privilegios.

set -euo pipefail
umask 022
export LC_ALL=C

readonly INSTALL_DIR="/usr/local/bin"
readonly TARGET="${INSTALL_DIR}/sysmon"

if [[ -t 1 ]]; then
    GREEN=$'\033[0;32m'; BLUE=$'\033[0;34m'; RED=$'\033[0;31m'
    YELLOW=$'\033[1;33m'; BOLD=$'\033[1m'; NC=$'\033[0m'
else
    GREEN=""; BLUE=""; RED=""; YELLOW=""; BOLD=""; NC=""
fi

info() { printf '%s==>%s %s\n' "$BLUE" "$NC" "$*"; }
ok()   { printf '%s ✓%s  %s\n' "$GREEN" "$NC" "$*"; }
warn() { printf '%s !%s  %s\n' "$YELLOW" "$NC" "$*"; }
die()  { printf '%s ✗  %s%s\n' "$RED" "$*" "$NC" >&2; exit 1; }

usage() {
    cat <<EOF
Uso: sudo $0 [--uninstall | --help]

  (sin opciones)   instala sysmon en ${TARGET}
  --uninstall      elimina ${TARGET}
  --help           muestra esta ayuda
EOF
}

# Ruta absoluta del directorio del script (no depende del cwd)
SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname -- "$SCRIPT_PATH")"
SOURCE="${SCRIPT_DIR}/sysmon.py"

ACTION="install"
case "${1:-}" in
    "")              ;;
    --uninstall|-u)  ACTION="uninstall" ;;
    --help|-h)       usage; exit 0 ;;
    *)               usage >&2; exit 2 ;;
esac

printf '%s\n' "${BOLD}${BLUE}╭──────────────────────────────────────────╮"
printf '%s\n' "│        sysmon · instalador               │"
printf '%s\n' "╰──────────────────────────────────────────╯${NC}"

# --- Privilegios -------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || die "Se requieren permisos de root y sudo no está disponible."
    warn "Se necesitan permisos de administrador; reintentando con sudo…"
    exec sudo -- /usr/bin/env bash "$SCRIPT_PATH" "$@"
fi

# --- Desinstalación ----------------------------------------------------
if [[ $ACTION == "uninstall" ]]; then
    if [[ -e $TARGET || -L $TARGET ]]; then
        rm -f -- "$TARGET"
        ok "sysmon eliminado de ${TARGET}"
    else
        warn "sysmon no estaba instalado en ${TARGET}"
    fi
    exit 0
fi

# --- Comprobaciones ----------------------------------------------------
[[ -f $SOURCE && ! -L $SOURCE ]] || die "No se encontró ${SOURCE} (o es un enlace simbólico)."

info "Verificando Python 3…"
PYTHON="$(command -v python3 || true)"
[[ -n $PYTHON ]] || die "Python 3 no está instalado (sudo apt install python3)."
PYTHON="$(readlink -f -- "$PYTHON")"
"$PYTHON" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)' \
    || die "Se requiere Python 3.6 o superior."
ok "Python: $("$PYTHON" -I --version 2>&1) (${PYTHON})"

info "Verificando psutil…"
if ! "$PYTHON" -I -c 'import psutil' 2>/dev/null; then
    warn "psutil no está instalado; instalando desde los repositorios del sistema…"
    if   command -v apt-get >/dev/null; then apt-get install -y python3-psutil
    elif command -v dnf     >/dev/null; then dnf install -y python3-psutil
    elif command -v pacman  >/dev/null; then pacman -S --needed --noconfirm python-psutil
    elif command -v zypper  >/dev/null; then zypper --non-interactive install python3-psutil
    else
        die "No se reconoce el gestor de paquetes. Instala psutil manualmente y reintenta."
    fi
    "$PYTHON" -I -c 'import psutil' 2>/dev/null || die "No se pudo instalar psutil."
fi
ok "psutil disponible"

info "Validando sysmon.py…"
"$PYTHON" -I -c 'import ast, sys; ast.parse(open(sys.argv[1], encoding="utf-8").read())' "$SOURCE" \
    || die "sysmon.py contiene errores de sintaxis."
ok "Sintaxis correcta"

# --- Instalación -------------------------------------------------------
info "Instalando en ${TARGET}…"
install -d -m 0755 -- "$INSTALL_DIR"
TMP="$(mktemp -- "${INSTALL_DIR}/.sysmon.XXXXXX")"
trap 'rm -f -- "$TMP"' EXIT

{
    printf '#!%s -I\n' "$PYTHON"
    tail -n +2 -- "$SOURCE"
} > "$TMP"
chown root:root -- "$TMP"
chmod 0755 -- "$TMP"
mv -f -- "$TMP" "$TARGET"
trap - EXIT

"$TARGET" --version >/dev/null || die "La instalación no funciona correctamente."

printf '\n%s\n' "${GREEN}${BOLD}✓ ¡Instalación completada!${NC}"
printf '\n  %sUso:%s           sysmon            %s(q para salir)%s\n' "$BOLD" "$NC" "$YELLOW" "$NC"
printf '  %sOpciones:%s      sysmon --help\n' "$BOLD" "$NC"
printf '  %sDesinstalar:%s   sudo %s --uninstall\n\n' "$BOLD" "$NC" "$SCRIPT_PATH"
