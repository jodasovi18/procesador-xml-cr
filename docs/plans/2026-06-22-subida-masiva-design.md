# Subida masiva (ZIP / múltiples XML) — Diseño

> Documento de diseño (spec). El plan de implementación con pasos TDD va aparte:
> `docs/plans/2026-06-22-subida-masiva.md`.

## Objetivo

Permitir subir **un ZIP** (o **varios XML**) de una sola vez y procesarlos con la
ingesta existente, con **éxito parcial** (un archivo malo no aborta el lote) y un
**reporte por archivo**. Es la subida manual masiva del roadmap, previa al agente
local (1C).

## Contexto

La ingesta de un solo XML ya existe:
- `motor/ingesta.py` → `ingest_xml(db, xml_bytes) -> dict` parsea, identifica
  cliente/rol por cédula, hace upsert idempotente por `clave` (borra+reinserta), hace
  `flush` (no commit). Devuelve `{clave, rol, cliente_id, nuevo, omitido}` y para
  no-comprobantes (p.ej. MensajeHacienda) `{clave: None, omitido: True, motivo}`.
  Lanza `ParseError`/`ValueError`/`InvalidOperation` si el XML es inválido.
- `routers/ingesta.py` → `POST /api/ingesta` (un archivo): commitea, traduce errores
  a 422, y reintenta una vez ante `IntegrityError` (si no, 409).

La subida masiva **reutiliza `ingest_xml`** por archivo; no reimplementa el parseo ni
la clasificación de cliente/rol.

## Decisiones de diseño

1. **Endpoint unificado** `POST /api/ingesta/lote` que acepta `archivos: list[UploadFile]`
   donde cada uno es `.xml` o `.zip`. El endpoint single-file actual (`POST /api/ingesta`)
   queda sin cambios (aditivo).
2. **Expansión de ZIP:** se extraen **todas las entradas `.xml`** (incluso en
   subcarpetas); se ignoran directorios, entradas no-`.xml` y la basura `__MACOSX/`.
   ZIP anidados (ZIP dentro de ZIP) → fuera de alcance.
3. **Éxito parcial con savepoints:** cada XML se procesa dentro de un savepoint
   (`db.begin_nested()`); si falla, se revierte solo ese archivo y el lote continúa.
   Un único `commit` al final.
4. **Tope anti-zip-bomb:** límites por defecto al expandir un ZIP — máx. de entradas
   y máx. de tamaño descomprimido total (sumando `ZipInfo.file_size`). Si se excede,
   ese ZIP se marca como `error` (no se procesa), sin abortar el resto del lote.
5. **Reporte por archivo + resumen:** la respuesta trae contadores y el detalle de
   cada archivo.

## Componentes

### A. `motor/ingesta_lote.py`

```python
def _expandir(archivos: list[tuple[str, bytes]]) -> Iterator[tuple[str, bytes]]:
    # .zip → entradas .xml (cap de entradas/tamaño); .xml → tal cual; resto → ignorar
def ingest_lote(db: Session, archivos: list[tuple[str, bytes]]) -> dict:
    # por cada (nombre, bytes) expandido: savepoint + ingest_xml; arma resumen + detalle
```
- `_expandir` lanza/propaga por-ZIP: `BadZipFile` y exceso de tope se manejan como un
  resultado `error` del ZIP (no rompen el lote). Las entradas `.xml` sueltas pasan
  directo.
- `ingest_lote` envuelve cada `ingest_xml` en `db.begin_nested()`. Mapea el resultado
  a `estado`: `omitido` → `"omitido"`; `nuevo=True` → `"nuevo"`; `nuevo=False` →
  `"actualizado"`; excepción (`ParseError`/`ValueError`/`InvalidOperation`/`IntegrityError`)
  → `"error"` con `motivo`. `commit` al final.

Constantes de tope (módulo): `MAX_ENTRADAS_ZIP = 5000`, `MAX_BYTES_DESCOMPRIMIDO = 200 * 1024 * 1024`.

### B. `routers/ingesta.py` (extender)

```python
@router.post("/lote")
def ingesta_lote(archivos: list[UploadFile], db=Depends(get_db), _=Depends(get_current_user)):
    pares = [(a.filename or "", a.file.read()) for a in archivos]
    return ingest_lote(db, pares)
```
Protegido por JWT (como el resto). El endpoint NO lanza 422 global: los errores van
por archivo en la respuesta (200 con el reporte).

## Estructura de la respuesta

```jsonc
{
  "total": 4,            // XML procesados tras expandir
  "nuevos": 2,
  "actualizados": 1,
  "omitidos": 1,         // MensajeHacienda u otros no-comprobante
  "errores": 1,
  "archivos": [
    {"archivo": "fac1.xml", "estado": "nuevo",       "clave": "506...", "rol": "compra", "cliente_id": 1},
    {"archivo": "fac2.xml", "estado": "actualizado", "clave": "506...", "rol": "venta",  "cliente_id": 1},
    {"archivo": "msg.xml",  "estado": "omitido",     "motivo": "tipo MensajeHacienda"},
    {"archivo": "roto.xml", "estado": "error",       "motivo": "XML inválido: ..."}
  ]
}
```

## Estrategia de pruebas (TDD)

Golden tests deterministas:
1. **`_expandir`** — un ZIP con `.xml` en subcarpeta + un `.txt` + `__MACOSX/` → solo
   los `.xml`; un `.xml` suelto pasa directo; ZIP corrupto → se reporta error (no
   excepción que rompa el lote).
2. **`ingest_lote` éxito parcial** — lote con factura válida (`fe_almacen_leon.xml`),
   MensajeHacienda (`mensaje_hacienda.xml` → omitido), y un XML inválido → resumen
   `nuevos=1, omitidos=1, errores=1` y detalle correcto; los buenos quedan persistidos
   pese al malo.
3. **Idempotencia** — re-subir el mismo lote → los previos salen `actualizado`.
4. **ZIP** — empaquetar fixtures reales en un ZIP en memoria y subirlo → procesa todas
   las entradas.
5. **Endpoint** — `POST /api/ingesta/lote` (multipart con varios archivos) → 200 con
   el resumen; 401 sin token.

Fixtures: los XML reales ya presentes en `backend/tests/fixtures` + ZIP construidos en
memoria (`zipfile`/`io.BytesIO`) en el test.

## Fuera de alcance (fases posteriores)

- Procesamiento en **background** para lotes muy grandes (hoy síncrono).
- **ZIP anidados** (ZIP dentro de ZIP).
- **Dry-run** / validación previa sin persistir.
- Reporte de duplicados dentro del mismo lote (hoy el segundo simplemente reingesta).
- Límite de tamaño del request a nivel servidor (config de despliegue).

## Riesgos / supuestos

- **Síncrono:** un lote enorme puede tardar; aceptable para subida manual de una firma.
  El tope anti-zip-bomb acota el peor caso.
- **Memoria:** el ZIP se lee en memoria (`BytesIO`); el tope de tamaño descomprimido lo
  acota. Suficiente para volúmenes de una firma; streaming queda diferido.
