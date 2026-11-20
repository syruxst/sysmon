#!/usr/bin/env python3
"""
SYSMon - Monitor simple del sistema para Linux.

Muestra CPU, memoria, swap, discos, red, IPs y procesos principales en una
interfaz de terminal sin parpadeo.

Teclas:  q  salir   ·   s  ordenar procesos por CPU/MEM
"""

import argparse
import ipaddress
import os
import platform
import re
import select
import shutil
import signal
import socket
import sys
import threading
import time
import unicodedata
import urllib.request
from collections import deque
from datetime import datetime

try:
    import psutil
except ImportError:
    sys.stderr.write(
        "Error: falta el módulo psutil.\n"
        "Instálalo con: sudo apt install python3-psutil\n"
    )
    sys.exit(1)

try:
    import termios
    import tty
except ImportError:  # Plataformas sin termios (p.ej. Windows)
    termios = tty = None

VERSION = "2.0.0"
PUBLIC_IP_URL = "https://api.ipify.org"
PUBLIC_IP_TTL = 300          # segundos entre consultas de IP pública
MAX_WIDTH = 110              # ancho máximo de la interfaz
MIN_WIDTH = 60               # ancho mínimo utilizable
LABEL_W = 12                 # ancho de la columna de etiquetas
MAX_DISKS = 4

# ============================================================
# TEXTO SEGURO Y MEDICIÓN DE ANCHO
# ============================================================

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def sanitize(value):
    """Elimina caracteres de control/formato de texto no confiable.

    Nombres de procesos, usuarios o interfaces los controla cualquier usuario
    local: si se imprimieran tal cual, podrían inyectar secuencias de escape
    en la terminal de quien ejecuta sysmon.
    """
    return "".join(
        "?" if unicodedata.category(ch)[0] == "C" else ch for ch in str(value)
    )


def char_width(ch):
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def text_width(s):
    return sum(char_width(c) for c in ANSI_RE.sub("", s))


def fit(s, width):
    """Recorta texto plano a `width` columnas, con '…' si no cabe."""
    if width <= 0:
        return ""
    if text_width(s) <= width:
        return s
    out, w = [], 0
    for ch in s:
        cw = char_width(ch)
        if w + cw > width - 1:
            break
        out.append(ch)
        w += cw
    return "".join(out) + "…"


def pad(s, width):
    """Rellena con espacios (texto con o sin ANSI) hasta `width` columnas."""
    return s + " " * max(0, width - text_width(s))


def clip(s, width):
    """Recorta un texto con códigos ANSI a `width` columnas visibles."""
    out, w, i = [], 0, 0
    while i < len(s):
        m = ANSI_RE.match(s, i)
        if m:
            out.append(m.group())
            i = m.end()
            continue
        cw = char_width(s[i])
        if w + cw > width:
            break
        out.append(s[i])
        w += cw
        i += 1
    return "".join(out), w


def human(n, per_second=False):
    suffix = "/s" if per_second else ""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}{suffix}" if unit == "B" else f"{n:.1f} {unit}{suffix}"
        n /= 1024
    return f"{n:.1f} PiB{suffix}"


def human_uptime(seconds):
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    return f"{hours:02d}h {minutes:02d}m"


# ============================================================
# TEMA / COLORES
# ============================================================

class Theme:
    def __init__(self, enabled):
        def c(code):
            return f"\033[{code}m" if enabled else ""

        self.reset = c("0")
        self.bold = c("1")
        self.border = c("38;5;239")
        self.title = c("1;38;5;117")
        self.label = c("1;38;5;75")
        self.muted = c("38;5;245")
        self.text = c("38;5;252")
        self.track = c("38;5;237")
        self.head = c("1;38;5;250")
        self.ok = c("38;5;114")
        self.warn = c("38;5;221")
        self.crit = c("38;5;203")
        self.up = c("38;5;180")
        self.down = c("38;5;110")
        # Un color distinto por disco (azul, violeta, turquesa, rosa)
        self.disks = [c("38;5;75"), c("38;5;141"), c("38;5;80"), c("38;5;218")]

    def disk_color(self, index, pct):
        """Color propio del disco; amarillo/rojo si se está llenando."""
        if pct >= 70:
            return self.level(pct, 70, 85)
        return self.disks[index % len(self.disks)]

    def level(self, pct, warn=50, crit=80):
        if pct >= crit:
            return self.crit
        if pct >= warn:
            return self.warn
        return self.ok


BLOCKS = " ▏▎▍▌▋▊▉"
SPARK = "▁▂▃▄▅▆▇█"


def bar(pct, width, th, color=None):
    pct = max(0.0, min(100.0, pct))
    exact = pct / 100 * width
    full = int(exact)
    part = int((exact - full) * 8)
    s = "█" * full
    used = full
    if full < width and part:
        s += BLOCKS[part]
        used += 1
    return f"{color or th.level(pct)}{s}{th.track}{'░' * (width - used)}{th.reset}"


def sparkline(values, width, th):
    vals = list(values)[-width:]
    out = []
    for v in vals:
        idx = min(len(SPARK) - 1, int(max(0.0, v) / 100 * len(SPARK)))
        out.append(f"{th.level(v)}{SPARK[idx]}")
    return " " * (width - len(vals)) + "".join(out) + th.reset


# ============================================================
# RECOLECCIÓN DE DATOS
# ============================================================

def cpu_temperature():
    try:
        temps = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None
    for key in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"):
        if temps.get(key):
            return temps[key][0].current
    return None


def local_ips():
    """IPv4 de interfaces activas, sin tráfico de red."""
    result = []
    try:
        stats = psutil.net_if_stats()
        for iface, addrs in psutil.net_if_addrs().items():
            if iface == "lo" or not (stats.get(iface) and stats[iface].isup):
                continue
            for a in addrs:
                if a.family == socket.AF_INET:
                    result.append((sanitize(iface), a.address))
    except OSError:
        pass
    return result


class PublicIP:
    """IP pública consultada en segundo plano, solo si el usuario lo pide."""

    def __init__(self, enabled):
        self._lock = threading.Lock()
        self._value = "consultando…" if enabled else None
        if enabled:
            threading.Thread(target=self._loop, daemon=True).start()

    @staticmethod
    def _fetch():
        req = urllib.request.Request(
            PUBLIC_IP_URL, headers={"User-Agent": f"sysmon/{VERSION}"}
        )
        # Certificado TLS verificado por el contexto por defecto de urllib.
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw = resp.read(64).decode("ascii").strip()
        # Solo se acepta una IP válida: nunca se muestra texto arbitrario.
        return str(ipaddress.ip_address(raw))

    def _loop(self):
        while True:
            try:
                value = self._fetch()
            except Exception:  # hilo en segundo plano: nunca debe romper la UI
                value = "N/A"
            with self._lock:
                self._value = value
            time.sleep(PUBLIC_IP_TTL)

    def get(self):
        with self._lock:
            return self._value


class Collector:
    def __init__(self, history=120):
        self.cpu_hist = deque(maxlen=history)
        psutil.cpu_percent(None)
        psutil.cpu_percent(None, percpu=True)
        for p in psutil.process_iter():
            try:
                p.cpu_percent(None)
            except psutil.Error:
                pass
        self._net = psutil.net_io_counters()
        self._t = time.monotonic()

    def sample(self):
        s = {}
        s["cpu"] = psutil.cpu_percent(None)
        s["cores"] = psutil.cpu_percent(None, percpu=True)
        self.cpu_hist.append(s["cpu"])
        s["cpu_hist"] = self.cpu_hist
        freq = None
        try:
            f = psutil.cpu_freq()
            freq = f.current if f else None
        except (OSError, NotImplementedError):
            pass
        s["freq"] = freq
        s["phys"] = psutil.cpu_count(logical=False) or 0
        s["logical"] = psutil.cpu_count() or 0
        s["temp"] = cpu_temperature()
        try:
            s["load"] = os.getloadavg()
        except (AttributeError, OSError):
            s["load"] = None

        s["mem"] = psutil.virtual_memory()
        s["swap"] = psutil.swap_memory()

        disks, seen = [], set()
        for part in psutil.disk_partitions(all=False):
            if part.device in seen or part.fstype in ("squashfs", "iso9660"):
                continue
            if part.mountpoint.startswith(("/snap", "/var/snap")):
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue
            seen.add(part.device)
            disks.append((sanitize(part.mountpoint), usage))
            if len(disks) >= MAX_DISKS:
                break
        s["disks"] = disks

        now = time.monotonic()
        net = psutil.net_io_counters()
        dt = max(now - self._t, 1e-6)
        s["net"] = net
        s["tx_rate"] = max(0, net.bytes_sent - self._net.bytes_sent) / dt
        s["rx_rate"] = max(0, net.bytes_recv - self._net.bytes_recv) / dt
        self._net, self._t = net, now

        s["ips"] = local_ips()
        s["uptime"] = time.time() - psutil.boot_time()

        procs = []
        for p in psutil.process_iter(
            ["pid", "name", "username", "cpu_percent", "memory_percent"]
        ):
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": sanitize(info["name"] or "?"),
                "user": sanitize(info["username"] or "?"),
                "cpu": info["cpu_percent"] or 0.0,
                "mem": info["memory_percent"] or 0.0,
            })
        s["procs"] = procs
        return s


# ============================================================
# RENDERIZADO
# ============================================================

class Frame:
    def __init__(self, width, th):
        self.w = width
        self.inner = width - 4
        self.th = th
        self.lines = []

    def _rule(self, left, right, title="", rtext=""):
        th = self.th
        lt = f"{left}─ {th.title}{title}{th.border} " if title else f"{left}─"
        rt = f" {th.muted}{rtext}{th.border} ─{right}" if rtext else f"─{right}"
        fill = self.w - text_width(lt) - text_width(rt)
        self.lines.append(f"{th.border}{lt}{'─' * max(0, fill)}{rt}{th.reset}")

    def top(self, title, rtext=""):
        self._rule("╭", "╮", title, rtext)

    def section(self, title, rtext=""):
        self._rule("├", "┤", title, rtext)

    def bottom(self, rtext=""):
        self._rule("╰", "╯", "", rtext)

    def row(self, content=""):
        th = self.th
        body, w = clip(content, self.inner)
        self.lines.append(
            f"{th.border}│{th.reset} {body}{th.reset}{' ' * (self.inner - w)} "
            f"{th.border}│{th.reset}"
        )


def render(s, th, cols, rows, sort_key, interval, public_ip):
    width = max(MIN_WIDTH, min(cols, MAX_WIDTH))
    f = Frame(width, th)
    inner = f.inner
    bw = max(10, min(40, inner - LABEL_W - 9 - 30))
    detail_w = inner - LABEL_W - bw - 9

    def label(text, color=None):
        return f"{color or th.label}{th.bold}{pad(fit(text, LABEL_W - 1), LABEL_W)}{th.reset}"

    def meter(name, pct, detail, color=None):
        return (f"{label(name, color)}{bar(pct, bw, th, color)} "
                f"{color or th.level(pct)}{pct:5.1f}%"
                f"{th.reset}  {th.muted}{fit(detail, detail_w)}{th.reset}")

    host = sanitize(socket.gethostname())
    clock = datetime.now().strftime("%H:%M:%S")
    f.top(f"SYSMon {VERSION}", f"{host} · Linux {platform.release()} · {clock}")

    # --- CPU -------------------------------------------------------------
    info = [f"{s['phys']}C/{s['logical']}T"]
    if s["freq"]:
        info.insert(0, f"{s['freq'] / 1000:.2f} GHz")
    f.row(meter("CPU", s["cpu"], " · ".join(info)))

    extra = ""
    if s["temp"] is not None:
        extra += f"{th.level(s['temp'], 60, 80)}{s['temp']:.0f}°C{th.reset}  "
    if s["load"]:
        extra += f"{th.muted}carga {' '.join(f'{x:.2f}' for x in s['load'])}{th.reset}"
    f.row(f"{label('historial')}{sparkline(s['cpu_hist'], bw, th)}        {extra}")

    cores = "".join(
        f"{th.level(c)}{SPARK[min(7, int(c / 100 * 8))]}" for c in s["cores"]
    )
    f.row(f"{label('núcleos')}{cores}{th.reset}")

    # --- Memoria ---------------------------------------------------------
    f.section("Memoria")
    m = s["mem"]
    f.row(meter("RAM", m.percent,
                f"{human(m.used)} / {human(m.total)} · libre {human(m.available)}"))
    sw = s["swap"]
    if sw.total:
        f.row(meter("SWAP", sw.percent, f"{human(sw.used)} / {human(sw.total)}"))

    # --- Discos ----------------------------------------------------------
    if s["disks"]:
        f.section("Discos")
        for i, (mount, u) in enumerate(s["disks"]):
            f.row(meter(mount, u.percent, f"{human(u.used)} / {human(u.total)}",
                        th.disk_color(i, u.percent)))

    # --- Red -------------------------------------------------------------
    f.section("Red")
    net = s["net"]
    f.row(f"{label('tráfico')}{th.up}↑ {pad(human(s['tx_rate'], True), 13)}"
          f"{th.down}↓ {pad(human(s['rx_rate'], True), 13)}{th.reset}"
          f"{th.muted}total ↑ {human(net.bytes_sent)}  ↓ {human(net.bytes_recv)}{th.reset}")
    ips = "  ".join(f"{th.muted}{i}{th.reset} {th.text}{a}{th.reset}" for i, a in s["ips"])
    f.row(f"{label('ip local')}{ips or th.muted + 'sin conexión' + th.reset}")
    pub = public_ip.get()
    if pub is None:
        f.row(f"{label('ip pública')}{th.muted}desactivada (usa --public-ip){th.reset}")
    else:
        f.row(f"{label('ip pública')}{th.text}{pub}{th.reset}")

    # --- Sistema ---------------------------------------------------------
    f.section("Sistema")
    f.row(f"{label('uptime')}{th.text}{human_uptime(s['uptime'])}{th.reset}"
          f"    {th.muted}procesos{th.reset} {th.text}{len(s['procs'])}{th.reset}")

    # --- Procesos --------------------------------------------------------
    key = "cpu" if sort_key == "cpu" else "mem"
    f.section("Procesos", f"orden: {key.upper()}")
    # rows <= 0: modo instantánea, sin límite de alto -> 10 procesos
    budget = rows - len(f.lines) - 2 if rows > 0 else 10
    if budget > 0:
        name_w = inner - 36
        f.row(f"{th.head}{'PID':>7}  {'USUARIO':<10}  {'CPU%':>6}  {'MEM%':>5}  "
              f"{'NOMBRE'}{th.reset}")
        top = sorted(s["procs"], key=lambda p: (p[key], p["cpu"] + p["mem"]),
                     reverse=True)[:budget]
        for p in top:
            f.row(f"{th.muted}{p['pid']:>7}{th.reset}  "
                  f"{pad(fit(p['user'], 10), 10)}  "
                  f"{th.level(min(p['cpu'], 100))}{p['cpu']:>6.1f}{th.reset}  "
                  f"{p['mem']:>5.1f}  "
                  f"{th.text}{fit(p['name'], name_w)}{th.reset}")

    f.bottom(f"q salir · s ordenar · cada {interval:g}s")
    return f.lines[:rows] if rows > 0 else f.lines


# ============================================================
# TERMINAL
# ============================================================

class TerminalSession:
    """Pantalla alternativa, cursor oculto y teclado en modo cbreak.

    Restaura siempre el estado original de la terminal al salir.
    """

    def __init__(self):
        self.fd = None
        self.saved = None
        if termios and sys.stdin.isatty():
            self.fd = sys.stdin.fileno()

    def __enter__(self):
        if self.fd is not None:
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        sys.stdout.write("\033[?1049h\033[?25l\033[2J")
        sys.stdout.flush()
        return self

    def __exit__(self, *exc):
        sys.stdout.write("\033[0m\033[?25h\033[?1049l")
        sys.stdout.flush()
        if self.saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
        return False

    def read_key(self, timeout):
        if self.fd is None:
            time.sleep(timeout)
            return ""
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if ready:
            return os.read(self.fd, 32).decode("utf-8", "ignore")
        return ""


def _exit_signal(signum, _frame):
    raise SystemExit(128 + signum)


def run_live(args, th):
    collector = Collector()
    time.sleep(0.4)  # primer intervalo de medición para CPU
    public_ip = PublicIP(args.public_ip)
    resized = threading.Event()

    signal.signal(signal.SIGTERM, _exit_signal)
    signal.signal(signal.SIGHUP, _exit_signal)
    if hasattr(signal, "SIGWINCH"):
        signal.signal(signal.SIGWINCH, lambda *_: resized.set())

    sort_key = "cpu"
    stats = None
    last_size = None
    next_sample = 0.0

    with TerminalSession() as term:
        while True:
            now = time.monotonic()
            if now >= next_sample or resized.is_set() or stats is None:
                if now >= next_sample or stats is None:
                    stats = collector.sample()
                    next_sample = now + args.interval
                resized.clear()
                size = shutil.get_terminal_size()
                out = []
                if size != last_size:
                    out.append("\033[2J")
                    last_size = size
                if size.columns < MIN_WIDTH or size.lines < 12:
                    out.append(f"\033[H{th.warn}Terminal demasiado pequeña "
                               f"({size.columns}x{size.lines}). Mínimo {MIN_WIDTH}x12."
                               f"{th.reset}\033[K\033[J")
                else:
                    lines = render(stats, th, size.columns, size.lines, sort_key,
                                   args.interval, public_ip)
                    out.append("\033[H" + "\033[K\n".join(lines) + "\033[K\033[J")
                sys.stdout.write("".join(out))
                sys.stdout.flush()

            wait = max(0.0, min(0.25, next_sample - time.monotonic()))
            key = term.read_key(wait).lower()
            if "q" in key:
                break
            if "s" in key:
                sort_key = "mem" if sort_key == "cpu" else "cpu"
                resized.set()  # redibujar sin volver a muestrear


def run_once(args, th):
    collector = Collector()
    time.sleep(0.5)
    public_ip = PublicIP(args.public_ip)
    if args.public_ip:
        deadline = time.monotonic() + 5
        while public_ip.get() == "consultando…" and time.monotonic() < deadline:
            time.sleep(0.1)
    cols = shutil.get_terminal_size((100, 40)).columns
    lines = render(collector.sample(), th, cols, 0, "cpu", args.interval, public_ip)
    print("\n".join(lines))


# ============================================================
# CLI
# ============================================================

def interval_type(value):
    try:
        v = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("debe ser un número")
    if not 0.5 <= v <= 60:
        raise argparse.ArgumentTypeError("debe estar entre 0.5 y 60 segundos")
    return v


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="sysmon",
        description="Monitor simple del sistema para la terminal.",
    )
    p.add_argument("-i", "--interval", type=interval_type, default=2.0,
                   help="segundos entre actualizaciones (0.5-60, por defecto 2)")
    p.add_argument("--public-ip", action="store_true",
                   help=f"consultar la IP pública en {PUBLIC_IP_URL} "
                        f"(cada {PUBLIC_IP_TTL // 60} min)")
    p.add_argument("--no-color", action="store_true",
                   help="desactivar colores (también respeta NO_COLOR)")
    p.add_argument("--once", action="store_true",
                   help="mostrar una sola instantánea y salir")
    p.add_argument("-V", "--version", action="version", version=f"sysmon {VERSION}")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    interactive = sys.stdout.isatty()
    color = interactive and not args.no_color and "NO_COLOR" not in os.environ
    th = Theme(color)
    try:
        if args.once or not interactive:
            run_once(args, th)
        else:
            run_live(args, th)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
