# Dashboard Top Motors — Facturación de motos y anticipos por cobrar

Dashboard web para el área comercial de **Top Motors** (Honda Perú), en US$:

1. **Facturación de motos 2026** — motos facturadas, importe, ventas por asesor y por mes, con descarga a Excel.
2. **Anticipos por cobrar** — valor, cobrado y saldo por modelo/color, con proyección de cobro según stock HDP.

📄 **[Ver dashboard publicado](https://vicharra463.github.io/Top-Motors-reporte/)** (se actualiza con cada carga).

📖 **[PROMPT_MAESTRO.md](./PROMPT_MAESTRO.md)** — reglas de negocio completas y flujo de trabajo con Finanzas.

---

## Cargar los Excel de la semana (paso a paso)

Cada vez que el sistema exporte los dos archivos nuevos:

1. Copia los archivos a la carpeta `datos/` (reemplazando los viejos o junto con ellos):
   - `Analisis_Ventas2026_*.xlsx` (boletas, facturas, NC/ND del año)
   - `AnalisisPedido_DD.MM.xlsx` (pedidos → modelo, color, asesor)
2. Ejecuta desde la carpeta del repo:

   ```
   pip install -r requirements.txt
   python actualizar_dashboard.py --ventas datos/Analisis_Ventas2026.xlsx --pedidos datos/AnalisisPedido_DD.MM.xlsx --plantilla plantilla_dashboard.html --salida index.html --previo data_ultima_version.json --guardar-datos data_nueva_version.json
   ```

3. Lee el resumen que imprime (totales, pedidos nuevos/salidos y **PARA REVISAR CON FINANZAS**).
   - Si hay casos para revisar, **no publiques**: muéstralos a Finanzas primero.
4. Sube los cambios a GitHub:

   ```
   git add .
   git commit -m "feat: dashboard corte DD/MM/AAAA"
   git push
   ```

   GitHub Pages republisha solo en ~1 minuto.
5. Renombra `data_nueva_version.json` → `data_ultima_version.json` (queda como comparación para la próxima carga) y súbelo también.

## Ver el dashboard en local (sin subir)

```
python actualizar_dashboard.py --ventas datos/analisis.xlsx --pedidos datos/pedido.xlsx --plantilla plantilla_dashboard.html --salida index.html
```

Abre `index.html` en el navegador.

## Stock HDP editable (Vercel)

La edición del stock y la proyección de cobro se guardan en **Vercel Blob** vía el endpoint `/api/stock` (cuando la página se sirve en Vercel). Activación (una sola vez):

1. En el dashboard de Vercel: **Storage → Create Store → Blob** (nombre libre, plan Hobby alcanza).
2. **Connect to Project** → elegir este proyecto (inyecta `BLOB_READ_WRITE_TOKEN` solo).
3. **Redeploy** el proyecto.

Después de eso, "Editar Stock HDP" guarda y lee en el almacén compartido: todos los que abran el enlace ven la misma proyección. En GitHub Pages (sin API) el botón queda en solo lectura con aviso.

Nota de seguridad: el endpoint de guardado no tiene autenticación (cualquiera con el enlace puede editar el stock). Si querés protegerlo, agregamos una clave compartida.

## Editar precios, excepciones o modelo de un SKU

Todo lo de negocio vive en la sección **CONFIGURACIÓN** de `actualizar_dashboard.py`:

| Qué cambió | Dónde se edita |
|---|---|
| Nueva campaña de precios | `LISTA_PRECIOS` y `ETIQUETA_LISTA` |
| Precio confirmado fuera de lista | `PRECIOS_FINANZAS` |
| SKU que agrupa con otro modelo | `MODELO_POR_SKU` |
| Excepción por pedido (dscto/precio) | `EXCEPCIONES` |
| Cobrado mayor ya revisado | `EXCEDENTES_CONFIRMADOS` |

Si cambia la lista de precios, pide el PDF nuevo a Finanzas y guárdalo en `docs/`.

## Estructura

```
actualizar_dashboard.py   ← motor: procesa Excel y genera el HTML
plantilla_dashboard.html  ← diseño (marcador __DATA__)
index.html                ← dashboard publicado (se genera con el script)
data_ultima_version.json  ← datos de la última versión publicada
datos/                    ← Excel de prueba (corte 26/10/2026)
docs/                     ← lista de precios vigente (PDF)
PROMPT_MAESTRO.md         ← reglas de negocio y flujo con Finanzas
```

## Corte de referencia (prueba inicial 26/10/2026)

- Facturación: **1,471 motos · US$ 4,562,293.57**
- Anticipos: **94 motos en 92 pedidos · saldo US$ 343,419.17 · 15 cobradas al 100%**
