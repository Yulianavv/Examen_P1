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
lock_pantalla = threading.Lock()


def redibujar_linea(mensaje: str, buffer: str) -> None:
    """Redibuja un mensaje y conserva visible el texto escrito a medias."""
    print(f"\r\033[2K{mensaje}\n{PROMPT}{buffer}", end="", flush=True)


def imprimir_mensaje(mensaje: str, buffer: list[str]) -> None:
    """Imprime una recepción sin mezclarla con el buffer del teclado."""
    with lock_pantalla:
        redibujar_linea(mensaje, buffer[0])


def leer_teclado(buffer: list[str]) -> str | None:
    """Lee caracteres, controla el buffer y devuelve una línea al pulsar Enter."""
    if not sys.stdin.isatty():
        try:
            return input()
        except EOFError:
            return None

    if os.name == "nt":
        import msvcrt

        while True:
            caracter = msvcrt.getwch()
            if caracter in ("\r", "\n"):
                with lock_pantalla:
                    texto = buffer[0]
                    buffer[0] = ""
                return texto
            if caracter in ("\x03", "\x1a"):
                return None
            if caracter in ("\x00", "\xe0"):
                msvcrt.getwch()
                continue
            if caracter in ("\b", "\x7f"):
                with lock_pantalla:
                    if buffer[0]:
                        buffer[0] = buffer[0][:-1]
                        print("\b \b", end="", flush=True)
                continue
            with lock_pantalla:
                buffer[0] += caracter
                print(caracter, end="", flush=True)

    import termios
    import tty

    descriptor = sys.stdin.fileno()
    estado_original = termios.tcgetattr(descriptor)
    try:
        tty.setcbreak(descriptor)
        estado_sin_eco = termios.tcgetattr(descriptor)
        estado_sin_eco[3] &= ~termios.ECHO
        termios.tcsetattr(descriptor, termios.TCSANOW, estado_sin_eco)
        while True:
            caracter = sys.stdin.read(1)
            if caracter in ("\r", "\n"):
                with lock_pantalla:
                    texto = buffer[0]
                    buffer[0] = ""
                return texto
            if caracter in ("\x03", "\x04", "\x1a"):
                return None
            if caracter in ("\x7f", "\b"):
                with lock_pantalla:
                    if buffer[0]:
                        buffer[0] = buffer[0][:-1]
                        print("\b \b", end="", flush=True)
                continue
            with lock_pantalla:
                buffer[0] += caracter
                print(caracter, end="", flush=True)
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, estado_original)


def recibir_mensajes(lector, buffer: list[str]) -> None:
    """Hilo daemon que recibe mensajes sin bloquear el teclado."""
    try:
        for linea in lector:
            mensaje = linea.rstrip("\r\n")
            if mensaje:
                imprimir_mensaje(mensaje, buffer)
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

        buffer = [""]
        hilo_receptor = threading.Thread(
            target=recibir_mensajes, args=(lector, buffer), daemon=True
        )
        hilo_receptor.start()
        with lock_pantalla:
            print(PROMPT, end="", flush=True)

        while not detener_cliente.is_set():
            texto = leer_teclado(buffer)
            if texto is None or texto.lower() == "salir":
                detener_cliente.set()
                break
            if texto:
                conexion.sendall((texto + "\n").encode("utf-8"))
                with lock_pantalla:
                    print(f"\r\033[2K[CLIENTE {numero}]: {texto}")
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
