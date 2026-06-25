# Agente de subida de XML — Sistema XML

Agente que corre en la máquina del contador: escanea carpetas, encuentra los XML de
comprobantes y los sube al backend (`POST /api/ingesta/lote`), evitando re-subir lo ya
enviado (dedup por hash de contenido). Es **standalone** (solo depende de `httpx` +
stdlib) y se empaqueta como un `.exe` que corre por **Tarea Programada**.

## Requisitos

- **Para construir el `.exe`:** Python 3.11 + PyInstaller (lo instala `build.ps1`).
- **Para correrlo en la máquina del contador:** solo el `.exe` (no requiere Python).

## 1. Construir el ejecutable

Desde `agent/`:

```powershell
.\build.ps1
# o con un intérprete explícito (en este repo, el venv):
.\build.ps1 -Python "C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe"
```

Resultado: `agent\dist\sxml_agent.exe`.

## 2. Configurar `agent.toml`

Copiar `agent.example.toml` a `agent.toml` (junto al `.exe`, o en otra ruta) y completar:

```toml
backend_url = "https://<host-del-backend>"
# Token de agente (recomendado): pedirlo a un admin con POST /api/agent-tokens
token = "PEGAR-TOKEN-DEL-BACKEND"
# (alternativa: usuario = "...", clave = "...")
carpetas = [
  "C:/Users/<usuario>/OneDrive/OFICINA/CONTAS/IVA",
]
lote_size = 100
estado_path = "C:/sxml/estado.json"
```

**Obtener el token** (un admin, autenticado por JWT):

```
POST /api/agent-tokens   {"label": "PC-contador"}
→ { "id": 1, "label": "PC-contador", "token": "<copiar este valor UNA vez>" }
```

El backend guarda solo el hash del token; si se filtra, se revoca con
`DELETE /api/agent-tokens/{id}` (no cambia la clave de ningún usuario).

## 3. Instalar la Tarea Programada

Corre el `.exe` en modo "un disparo" cada N minutos (el Programador de tareas es el
bucle). Desde `agent/`:

```powershell
.\instalar-tarea.ps1 -ExePath "C:\sxml\sxml_agent.exe" -ConfigPath "C:\sxml\agent.toml" -IntervaloMin 30
```

Desinstalar:

```powershell
.\instalar-tarea.ps1 -Accion uninstall
```

La tarea corre con el usuario actual y **solo con sesión iniciada** (no se guardan
contraseñas). La PC debe estar logueada durante el horario de trabajo.

## 4. Operación

- **Prueba manual** (una corrida): `sxml_agent.exe --config C:\sxml\agent.toml`. Imprime
  un resumen JSON (`escaneados`, `ya_subidos_local`, `enviados`, `nuevos`, `actualizados`,
  `omitidos`, `errores`, `tandas_fallidas`).
- **Modo continuo manual** (opcional, no usado por la tarea): `sxml_agent.exe --watch
  --config C:\sxml\agent.toml`.
- **Logs:** redirigir la salida a un archivo, p.ej. en la acción de la tarea o corriendo
  `sxml_agent.exe --config ... *>> C:\sxml\agente.log`.
- **Estado / dedup:** `estado_path` (JSON) guarda los hashes ya subidos; no se re-suben.
  Si se borra, la próxima corrida re-sube todo (inofensivo: el backend es idempotente).
- **Idempotencia:** subir dos veces el mismo XML no duplica (el backend deduplica por
  clave; el agente, por hash).

## 5. Troubleshooting

- **`ERROR: Archivo de configuración no encontrado` / `Faltan claves requeridas`** →
  revisar la ruta de `--config` y que `agent.toml` tenga `backend_url`, `carpetas`, y
  `token` (o `usuario`+`clave`).
- **`tandas_fallidas` > 0 / 401** → el token es inválido o fue revocado: pedir uno nuevo
  (`POST /api/agent-tokens`) y actualizar `agent.toml`. O el backend está inalcanzable.
- **`build.ps1` no instala PyInstaller** → la red bloquea PyPI; pre-instalar PyInstaller
  o usar un wheel local (`pip install pyinstaller-<ver>.whl`), luego re-correr `build.ps1`.
- **Windows SmartScreen advierte sobre el `.exe`** → es por no estar firmado (firma de
  código diferida); "Más información → Ejecutar de todas formas", o firmar el `.exe`.
- **Carpeta de `carpetas` inexistente** → se omite con aviso; no aborta la corrida.

## Notas

- Empaquetado y firma: el `.exe` no está firmado (puede disparar SmartScreen). Firma de
  código / instalador MSI / correr como servicio quedan como mejoras futuras.
- Seguridad: el `token` queda en `agent.toml` en texto plano (es un secreto revocable y
  acotado a la ingesta, no la clave del contador). Guardarlo en el keyring del SO es una
  mejora futura.
