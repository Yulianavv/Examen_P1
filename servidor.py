"""Servidor de chat TCP para participantes simultaneos.

El servidor usa un hilo para aceptar conexiones, un hilo por cliente y otro
hilo daemon para leer mensajes escritos en la consola del contenedor.
"""

import os
import socket
import threading
from typing import Dict, Tuple


# El puerto se puede cambiar sin modificar el codigo: CHAT_PORT=6000.
HOST = "0.0.0.0"
PORT = int(os.environ.get("CHAT_PORT", "5000"))
MAX_CLIENTES = int(os.environ.get("MAX_CLIENTES", "2"))

# El diccionario y el contador se protegen con este Lock porque varios hilos
# pueden conectar, desconectar o enviar mensajes al mismo tiempo.
clientes: Dict[socket.socket, int] = {}
clientes_lock = threading.Lock()
detener_servidor = threading.Event()


def enviar_linea(conexion: socket.socket, mensaje: str) -> None:
    """Envia una linea UTF-8 completa por el canal de escritura del socket."""
    conexion.sendall((mensaje + "\n").encode("utf-8"))


def obtener_numero_libre() -> int:
    """Devuelve el menor identificador de cliente que no esta ocupado."""
    numeros_usados = set(clientes.values())
    numero = 1
    while numero in numeros_usados:
        numero += 1
    return numero


def lista_clientes_conectados() -> str:
    """Devuelve los nombres conectados; el llamador debe tener el Lock."""
    return ", ".join(
        f"CLIENTE {numero}" for numero in sorted(clientes.values())
    ) or "ninguno"


def quitar_cliente(conexion: socket.socket) -> Tuple[int | None, bool]:
    """Elimina una conexion bajo el Lock y devuelve su numero si existia."""
    with clientes_lock:
        numero = clientes.pop(conexion, None)
    if numero is None:
        return None, False
    try:
        conexion.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    conexion.close()
    return numero, True


def transmitir(mensaje: str, excluir: socket.socket | None = None) -> None:
    """Distribuye un mensaje a todos salvo, opcionalmente, al emisor."""
    # Solo se copia la lista bajo el Lock; enviar puede bloquear y no debe
    # impedir que otro hilo consulte o actualice el diccionario.
    with clientes_lock:
        destinatarios = [conexion for conexion in clientes if conexion != excluir]

    conexiones_fallidas = []
    for conexion in destinatarios:
        try:
            enviar_linea(conexion, mensaje)
        except (ConnectionError, OSError):
            conexiones_fallidas.append(conexion)

    # Una desconexion abrupta se retira de forma independiente de las demas.
    for conexion in conexiones_fallidas:
        desconectar_cliente(conexion)


def desconectar_cliente(conexion: socket.socket) -> None:
    """Retira un cliente y avisa a los participantes que siguen conectados."""
    numero, existia = quitar_cliente(conexion)
    if existia and numero is not None:
        mensaje = f"[SISTEMA]: CLIENTE {numero} se desconectó"
        print(mensaje, flush=True)
        # La conexion ya fue retirada del diccionario, por lo que el aviso
        # solo llega a los clientes que permanecen conectados.
        transmitir(mensaje)
        with clientes_lock:
            conectados = lista_clientes_conectados()
        print(f"[SISTEMA]: Conectados: {conectados}", flush=True)


def atender_cliente(conexion: socket.socket, direccion: Tuple[str, int]) -> None:
    """Lee lineas de un cliente y las retransmite sin esperar turnos."""
    del direccion  # La direccion solo sirve como dato de diagnostico opcional.
    numero = None
    lector = None
    with clientes_lock:
        if len(clientes) >= MAX_CLIENTES:
            lleno = True
        else:
            lleno = False
            # La comprobacion de capacidad y la reserva del menor numero son
            # atomicas porque ocurren dentro del mismo Lock.
            numero = obtener_numero_libre()
            clientes[conexion] = numero

    if lleno:
        try:
            enviar_linea(conexion, "[SISTEMA]: Servidor lleno")
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                conexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conexion.close()
        return

    try:
        # Este primer mensaje interno permite que el cliente se identifique
        # automaticamente antes de empezar a leer el teclado.
        enviar_linea(conexion, f"ASIGNADO:{numero}")
        mensaje_conexion = f"[SISTEMA]: CLIENTE {numero} se conectó"
        # El cliente nuevo no recibe su propio aviso; los demas si lo reciben.
        transmitir(mensaje_conexion, excluir=conexion)
        with clientes_lock:
            conectados = lista_clientes_conectados()
        print(f"{mensaje_conexion} | Conectados: {conectados}", flush=True)

        # makefile crea un lector con buffer que reconstruye mensajes partidos
        # y permite procesar correctamente varios mensajes pegados.
        lector = conexion.makefile("r", encoding="utf-8", newline="\n")
        for linea in lector:
            texto = linea.rstrip("\r\n")
            if not texto:
                continue
            if texto.lower() == "salir":
                break
            mensaje = f"[CLIENTE {numero}]: {texto}"
            print(mensaje, flush=True)
            transmitir(mensaje, excluir=conexion)
    except (ConnectionError, BrokenPipeError, ConnectionResetError, OSError, UnicodeError):
        # La desconexion del cliente no debe mostrar un traceback al usuario.
        pass
    finally:
        try:
            if lector is not None:
                lector.close()
        except OSError:
            pass
        if numero is not None:
            desconectar_cliente(conexion)


def leer_consola() -> None:
    """Lee mensajes del servidor; EOF no detiene el servidor."""
    while not detener_servidor.is_set():
        try:
            texto = input()
        except EOFError:
            # docker compose run -T puede no tener stdin: es una condicion
            # normal y el servidor continua atendiendo conexiones.
            return
        except KeyboardInterrupt:
            detener_servidor.set()
            return
        if texto.lower() == "salir":
            detener_servidor.set()
            return
        if texto:
            mensaje = f"[SERVIDOR]: {texto}"
            print(mensaje, flush=True)
            transmitir(mensaje)


def cerrar_clientes() -> None:
    """Cierra todas las conexiones restantes durante el apagado."""
    with clientes_lock:
        conexiones = list(clientes)
    for conexion in conexiones:
        desconectar_cliente(conexion)


def iniciar_servidor() -> None:
    """Configura bind/listen y acepta clientes hasta recibir una senal."""
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PORT))
    servidor.listen()
    servidor.settimeout(1.0)

    print(f"Servidor escuchando en {HOST}:{PORT}", flush=True)
    threading.Thread(target=leer_consola, name="consola", daemon=True).start()

    try:
        while not detener_servidor.is_set():
            try:
                conexion, direccion = servidor.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=atender_cliente,
                args=(conexion, direccion),
                daemon=True,
            ).start()
    except KeyboardInterrupt:
        print("\n[SISTEMA]: apagando servidor", flush=True)
    finally:
        detener_servidor.set()
        cerrar_clientes()
        servidor.close()
        print("[SISTEMA]: servidor detenido", flush=True)


if __name__ == "__main__":
    iniciar_servidor()
