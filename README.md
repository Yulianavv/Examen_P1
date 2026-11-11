# Chat TCP distribuido

Servidor en Docker y dos clientes Python con comunicación en tiempo real.

## Requisitos

- Docker Desktop iniciado.
- Python 3.11 o posterior.
- Tres terminales independientes.

## Ejecución

### Terminal 1: servidor

Windows PowerShell, Linux o macOS:

```bash
docker compose down
docker compose run --rm --service-ports servidor
```

Debe aparecer:

```text
Servidor escuchando en 0.0.0.0:5000
```

### Terminal 2: Cliente 1

Windows:

```powershell
python cliente.py
```

Linux/macOS:

```bash
python3 cliente.py
```

Debe conectarse como `CLIENTE 1`.

### Terminal 3: Cliente 2

Ejecutar el mismo comando. Debe conectarse como `CLIENTE 2`.

## Prueba rápida

1. Escribir un mensaje en Cliente 1. Debe aparecer en el servidor y en
   Cliente 2 como `[CLIENTE 1]: mensaje`.
2. Escribir un mensaje en Cliente 2. Debe aparecer en el servidor y en
   Cliente 1 como `[CLIENTE 2]: mensaje`.
3. Escribir un mensaje en la Terminal 1. Debe aparecer en ambos clientes como
   `[SERVIDOR]: mensaje`.
4. Escribir mensajes en ambos clientes sin esperar turnos.
5. Para salir, escribir `salir` o pulsar `Ctrl+C`.

El servidor admite dos clientes por defecto. Un tercero recibe
`[SISTEMA]: Servidor lleno`. Al desconectarse un cliente, su número queda
disponible para el siguiente.

## Configuración opcional

El puerto predeterminado es `5000` y el máximo de clientes es `2`.

Windows PowerShell:

```powershell
$env:CHAT_PORT = "6000"
$env:MAX_CLIENTES = "2"
docker compose down
docker compose run --rm --service-ports servidor
```

En los clientes:

```powershell
$env:CHAT_PORT = "6000"
python cliente.py
```

Linux/macOS:

```bash
CHAT_PORT=6000 MAX_CLIENTES=2 docker compose run --rm --service-ports servidor
CHAT_PORT=6000 python3 cliente.py
```

## Solución de problemas

- **Puerto ocupado:** ejecutar `docker compose down` y utilizar otro
  `CHAT_PORT` en el servidor y los clientes.
- **Docker apagado:** iniciar Docker Desktop.
- **Clientes fantasma:** cerrar terminales antiguas y ejecutar:
  `docker compose down`; después iniciar nuevamente el servidor.
- **No conecta:** verificar que el servidor esté ejecutándose y que todos
  utilicen el mismo puerto.

