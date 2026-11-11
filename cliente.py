"""Cliente de chat TCP con lectura y escritura simultaneas."""

import os
import socket
import sys
import threading


# Habilita el procesamiento de secuencias ANSI en la terminal de Windows.
os.system("")

HOST = os.environ.get("CHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CHAT_PORT", "5000"))
PROMPT = "> "
detener_cliente = threading.Event()


def imprimir_mensaje(mensaje: str) -> None:
    """Limpia la linea actual, imprime el mensaje y repone el prompt."""
    print(f"\r\033[2K{mensaje}")
    if not detener_cliente.is_set():
        print(PROMPT, end="", flush=True)


def recibir_mensajes(lector) -> None:
    """Hilo daemon: recibe lineas mientras el hilo principal lee input()."""
    try:
        for linea in lector:
            mensaje = linea.rstrip("\r\n")
            if mensaje:
                imprimir_mensaje(mensaje)
        detener_cliente.set()
    except (ConnectionError, OSError, UnicodeError):
        detener_cliente.set()
    finally:
        try:
            lector.close()
        except (UnboundLocalError, OSError):
            pass


def iniciar_cliente() -> None:
    """Conecta, obtiene el numero automatico y habilita ambos canales."""
    conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lector = None
    try:
        conexion.connect((HOST, PORT))
        # El servidor envia la identificacion como primera linea del protocolo.
        # makefile conserva cualquier linea adicional que haya llegado en el
        # mismo paquete TCP, en vez de descartarla con un recv() grande.
        lector = conexion.makefile("r", encoding="utf-8", newline="\n")
        identificacion = lector.readline().strip()
        if identificacion == "[SISTEMA]: Servidor lleno":
            print(identificacion)
            return
        if not identificacion.startswith("ASIGNADO:"):
            raise ConnectionError("El servidor no envio una identificacion valida")
        numero = identificacion.split(":", 1)[1]
        print(f"Conectado como CLIENTE {numero} a {HOST}:{PORT}")

        hilo_receptor = threading.Thread(
            target=recibir_mensajes, args=(lector,), daemon=True
        )
        hilo_receptor.start()
        print(PROMPT, end="", flush=True)

        while not detener_cliente.is_set():
            try:
                texto = input()
            except EOFError:
                texto = "salir"
            except KeyboardInterrupt:
                print()
                texto = "salir"
            if texto.lower() == "salir":
                detener_cliente.set()
                break
            if texto:
                conexion.sendall((texto + "\n").encode("utf-8"))
                # input() ya dejo el cursor en la linea siguiente. Se sube a
                # la linea escrita, se reemplaza el texto y se repone el prompt.
                print(f"\033[A\033[2K[CLIENTE {numero}]: {texto}")
                print(PROMPT, end="", flush=True)
    except (ConnectionError, OSError, UnicodeError) as error:
        print(f"\nNo se pudo mantener la conexion: {error}", file=sys.stderr)
    finally:
        detener_cliente.set()
        try:
            conexion.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conexion.close()
        if lector is not None:
            try:
                lector.close()
            except OSError:
                pass
        print("Conexion cerrada.")


if __name__ == "__main__":
    iniciar_cliente()
