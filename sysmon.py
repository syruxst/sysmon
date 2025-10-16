#!/usr/bin/env python3
"""
Monitor simple del sistema
Muestra CPU, memoria, temperatura y disco de forma clara
Con actualización suave sin parpadeo
"""

import psutil
import time
import os
import sys
from datetime import timedelta

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
        if 'coretemp' in temps:
            return temps['coretemp'][0].current
        elif 'k10temp' in temps:  # Para AMD
            return temps['k10temp'][0].current
        elif 'cpu_thermal' in temps:  # Para Raspberry Pi
            return temps['cpu_thermal'][0].current
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

def pantalla_inicial():
    """Dibuja la pantalla inicial una sola vez"""
    os.system('clear' if os.name == 'posix' else 'cls')
    ocultar_cursor()
    
    print("\033[1;96m" + "=" * 70)
    print("                      MONITOR DEL SISTEMA")
    print("=" * 70 + "\033[0m\n")
    
    # CPU - líneas 5-9
    print()  # Título con icono
    print()  # Uso
    print()  # Frecuencia
    print()  # Núcleos
    print()  # Temp
    
    # Memoria RAM - líneas 11-14
    print()  # Título con icono
    print()  # Uso
    print()  # Usado
    print()  # Disponible
    
    # Disco - líneas 16-19
    print()  # Título con icono
    print()  # Uso
    print()  # Usado
    print()  # Libre
    
    # Red - líneas 21-23
    print()  # Título con icono
    print()  # Enviado
    print()  # Recibido
    
    # Uptime - línea 25
    print()
    
    # Procesos top - líneas 26-31
    print()  # Título con icono
    for i in range(5):
        print()

def actualizar_datos():
    """Actualiza solo los datos sin redibujar toda la pantalla"""
    
    # CPU - Líneas 5-8
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_count_logical = psutil.cpu_count()
    
    mover_cursor(5, 0)
    print(f"\033[1;94m📊 CPU:\033[0m", end='')
    limpiar_linea()
    
    mover_cursor(6, 0)
    print(f"   Uso:        {mostrar_barra(cpu_percent)}", end='')
    limpiar_linea()
    
    mover_cursor(7, 0)
    print(f"   Frecuencia: {cpu_freq.current:.0f} MHz", end='')
    limpiar_linea()
    
    mover_cursor(8, 0)
    print(f"   Núcleos:    {cpu_count_physical} físicos, {cpu_count_logical} lógicos", end='')
    limpiar_linea()
    
    mover_cursor(9, 0)
    temp = obtener_temperatura()
    if temp:
        temp_color = '\033[92m' if temp < 60 else '\033[93m' if temp < 80 else '\033[91m'
        print(f"   Temp:       {temp_color}{temp:.1f}°C\033[0m", end='')
    else:
        print("   Temp:       N/A", end='')
    limpiar_linea()
    
    # Memoria RAM - Líneas 11-14
    mem = psutil.virtual_memory()
    
    mover_cursor(11, 0)
    print(f"\033[1;94m💾 MEMORIA RAM:\033[0m", end='')
    limpiar_linea()
    
    mover_cursor(12, 0)
    print(f"   Uso:        {mostrar_barra(mem.percent)}", end='')
    limpiar_linea()
    
    mover_cursor(13, 0)
    print(f"   Usado:      {obtener_tamaño(mem.used)} / {obtener_tamaño(mem.total)}", end='')
    limpiar_linea()
    
    mover_cursor(14, 0)
    print(f"   Disponible: {obtener_tamaño(mem.available)}", end='')
    limpiar_linea()
    
    # Disco - Líneas 16-19
    disk = psutil.disk_usage('/')
    
    mover_cursor(16, 0)
    print(f"\033[1;94m💿 DISCO (/):\033[0m", end='')
    limpiar_linea()
    
    mover_cursor(17, 0)
    print(f"   Uso:        {mostrar_barra(disk.percent)}", end='')
    limpiar_linea()
    
    mover_cursor(18, 0)
    print(f"   Usado:      {obtener_tamaño(disk.used)} / {obtener_tamaño(disk.total)}", end='')
    limpiar_linea()
    
    mover_cursor(19, 0)
    print(f"   Libre:      {obtener_tamaño(disk.free)}", end='')
    limpiar_linea()
    
    # Red - Líneas 21-23
    net = psutil.net_io_counters()
    
    mover_cursor(21, 0)
    print(f"\033[1;94m🌐 RED:\033[0m", end='')
    limpiar_linea()
    
    mover_cursor(22, 0)
    print(f"   Enviado:    {obtener_tamaño(net.bytes_sent)}", end='')
    limpiar_linea()
    
    mover_cursor(23, 0)
    print(f"   Recibido:   {obtener_tamaño(net.bytes_recv)}", end='')
    limpiar_linea()
    
    # Uptime - Línea 25
    boot_time = psutil.boot_time()
    uptime = time.time() - boot_time
    uptime_str = str(timedelta(seconds=int(uptime)))
    
    mover_cursor(25, 0)
    print(f"\033[1;94m⏱️  TIEMPO DE USO DEL PC:\033[0m {uptime_str}", end='')
    limpiar_linea()
    
    # Procesos top - Líneas 26-31
    mover_cursor(26, 0)
    print(f"\033[1;94m🔝 TOP 5 PROCESOS (CPU):\033[0m", end='')
    limpiar_linea()
    
    procesos = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            procesos.append(proc.info)
        except:
            pass
    
    procesos_top = sorted(procesos, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:5]
    
    for i, proc in enumerate(procesos_top):
        mover_cursor(27 + i, 0)
        nombre = proc['name'][:30]
        print(f"   {proc['pid']:>6} {nombre:<30} {proc['cpu_percent']:>5.1f}%", end='')
        limpiar_linea()
    
    # Rellenar líneas vacías si hay menos de 5 procesos
    for i in range(len(procesos_top), 5):
        mover_cursor(27 + i, 0)
        print("   ", end='')
        limpiar_linea()
    
    # Mensaje al final - Línea 33
    mover_cursor(33, 0)
    print("\n\033[90mPresiona Ctrl+C para salir | Actualización cada 3 segundos\033[0m", end='')
    limpiar_linea()
    
    sys.stdout.flush()

def monitor_sistema():
    """Función principal de monitoreo"""
    pantalla_inicial()
    
    try:
        while True:
            actualizar_datos()
            time.sleep(3)  # Actualiza cada 3 segundos
    except KeyboardInterrupt:
        mostrar_cursor()
        mover_cursor(36, 0)
        print("\n\033[92m✓ Monitor cerrado\033[0m")

if __name__ == "__main__":
    try:
        monitor_sistema()
    except ImportError:
        print("\033[91m❌ Error: Necesitas instalar psutil\033[0m")
        print("\033[93mEjecuta: pip install psutil\033[0m")
    except Exception as e:
        mostrar_cursor()
        print(f"\033[91m❌ Error: {e}\033[0m")