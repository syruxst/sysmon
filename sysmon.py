#!/usr/bin/env python3
"""
Monitor simple del sistema (SYSMon)
Muestra CPU, memoria, disco, red, IPs y procesos principales
Actualización suave sin parpadeo
"""

import psutil
import time
import os
import sys
from datetime import timedelta
import socket
import requests

# ========================
# FUNCIONES AUXILIARES
# ========================

def obtener_ip_privada():
    """Obtiene la IP privada local"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_local = s.getsockname()[0]
        s.close()
        return ip_local
    except:
        return "N/A"

def obtener_ip_publica():
    """Obtiene la IP pública usando un servicio externo"""
    try:
        return requests.get("https://api.ipify.org", timeout=3).text
    except:
        return "N/A"

def mover_cursor(fila, columna=0):
    """Mueve el cursor a una posición específica"""
    sys.stdout.write(f"\033[{fila};{columna}H")
    sys.stdout.flush()

def limpiar_linea():
    """Limpia la línea actual"""
    sys.stdout.write("\033[K")

def ocultar_cursor():
    """Oculta el cursor"""
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

def mostrar_cursor():
    """Muestra el cursor"""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

def obtener_tamaño(bytes):
    """Convierte bytes a formato legible"""
    for unidad in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unidad}"
        bytes /= 1024.0

def obtener_temperatura():
    """Obtiene temperatura del CPU si está disponible"""
    try:
        temps = psutil.sensors_temperatures()
        for key in ['coretemp', 'k10temp', 'cpu_thermal']:
            if key in temps:
                return temps[key][0].current
    except:
        pass
    return None

def mostrar_barra(porcentaje, ancho=30):
    """Crea una barra de progreso visual"""
    lleno = int(ancho * porcentaje / 100)
    vacio = ancho - lleno

    if porcentaje < 50:
        color = '\033[92m'  # Verde
    elif porcentaje < 80:
        color = '\033[93m'  # Amarillo
    else:
        color = '\033[91m'  # Rojo

    return f"{color}[{'█' * lleno}{'░' * vacio}]\033[0m {porcentaje:.1f}%"

# ========================
# INTERFAZ PRINCIPAL
# ========================

def pantalla_inicial():
    """Dibuja el marco y etiquetas fijas"""
    os.system('clear' if os.name == 'posix' else 'cls')
    ocultar_cursor()

    print("\033[1;96m" + "=" * 70)
    print("                    SYSMon - Monitor del Sistema")
    print("=" * 70 + "\033[0m\n")

    # Reservamos líneas para IPs (2 líneas)
    print()  
    print()

    # CPU
    print()
    print()
    print()
    print()
    print()

    # RAM
    print()
    print()
    print()
    print()

    # DISCO
    print()
    print()
    print()
    print()

    # RED
    print()
    print()
    print()

    # UPTIME
    print()

    # Procesos
    print()
    for _ in range(5):
        print()

def actualizar_datos():
    """Actualiza dinámicamente los valores en pantalla"""
    # IPs
    mover_cursor(4, 0)
    ip_priv = obtener_ip_privada()
    ip_pub = obtener_ip_publica()
    print(f"\033[1;97mIP Privada:\033[0m {ip_priv}   \033[1;97mIP Pública:\033[0m {ip_pub}")
    limpiar_linea()

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_count_logical = psutil.cpu_count()
    temp = obtener_temperatura()

    mover_cursor(6, 0)
    print(f"\033[1;94m📊 CPU:\033[0m")
    mover_cursor(7, 0)
    print(f"   Uso:        {mostrar_barra(cpu_percent)}")
    mover_cursor(8, 0)
    print(f"   Frecuencia: {cpu_freq.current:.0f} MHz")
    mover_cursor(9, 0)
    print(f"   Núcleos:    {cpu_count_physical} físicos, {cpu_count_logical} lógicos")
    mover_cursor(10, 0)
    if temp:
        color_temp = '\033[92m' if temp < 60 else '\033[93m' if temp < 80 else '\033[91m'
        print(f"   Temp:       {color_temp}{temp:.1f}°C\033[0m")
    else:
        print("   Temp:       N/A")

    # RAM
    mem = psutil.virtual_memory()
    mover_cursor(12, 0)
    print(f"\033[1;94m💾 MEMORIA RAM:\033[0m")
    mover_cursor(13, 0)
    print(f"   Uso:        {mostrar_barra(mem.percent)}")
    mover_cursor(14, 0)
    print(f"   Usado:      {obtener_tamaño(mem.used)} / {obtener_tamaño(mem.total)}")
    mover_cursor(15, 0)
    print(f"   Disponible: {obtener_tamaño(mem.available)}")

    # DISCO
    disk = psutil.disk_usage('/')
    mover_cursor(17, 0)
    print(f"\033[1;94m💿 DISCO (/):\033[0m")
    mover_cursor(18, 0)
    print(f"   Uso:        {mostrar_barra(disk.percent)}")
    mover_cursor(19, 0)
    print(f"   Usado:      {obtener_tamaño(disk.used)} / {obtener_tamaño(disk.total)}")
    mover_cursor(20, 0)
    print(f"   Libre:      {obtener_tamaño(disk.free)}")

    # RED
    net = psutil.net_io_counters()
    mover_cursor(22, 0)
    print(f"\033[1;94m🌐 RED:\033[0m")
    mover_cursor(23, 0)
    print(f"   Enviado:    {obtener_tamaño(net.bytes_sent)}")
    mover_cursor(24, 0)
    print(f"   Recibido:   {obtener_tamaño(net.bytes_recv)}")

    # UPTIME
    mover_cursor(26, 0)
    uptime = str(timedelta(seconds=int(time.time() - psutil.boot_time())))
    print(f"\033[1;94m⏱️  UPTIME:\033[0m {uptime}")

    # PROCESOS TOP
    mover_cursor(28, 0)
    print(f"\033[1;94m🔝 TOP 5 PROCESOS (CPU):\033[0m")
    procesos = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            procesos.append(proc.info)
        except:
            pass
    top = sorted(procesos, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:5]
    for i, p in enumerate(top):
        mover_cursor(29 + i, 0)
        nombre = p['name'][:28]
        print(f"   {p['pid']:>6} {nombre:<28} {p['cpu_percent']:>5.1f}%")
        limpiar_linea()

    mover_cursor(35, 0)
    print("\033[90mPresiona Ctrl+C para salir | Actualización cada 3s\033[0m")
    sys.stdout.flush()

# ========================
# PROGRAMA PRINCIPAL
# ========================

def monitor_sistema():
    pantalla_inicial()
    try:
        while True:
            actualizar_datos()
            time.sleep(3)
    except KeyboardInterrupt:
        mostrar_cursor()
        mover_cursor(38, 0)
        print("\n\033[92m✓ Monitor cerrado correctamente\033[0m")

if __name__ == "__main__":
    try:
        monitor_sistema()
    except ImportError:
        print("\033[91m❌ Error: necesitas instalar psutil y requests\033[0m")
        print("\033[93mEjecuta: pip install psutil requests\033[0m")
    except Exception as e:
        mostrar_cursor()
        print(f"\033[91m❌ Error: {e}\033[0m")
