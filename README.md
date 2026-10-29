# Dashboard Top Motors — Facturación de motos y anticipos por cobrar

Dashboard web para el área comercial de **Top Motors** (Honda Perú), en US$:

1. **Facturación de motos 2026** — motos facturadas, importe, ventas por asesor y por mes, con descarga a Excel.
2. **Anticipos por cobrar** — valor, cobrado y saldo por modelo/color, con proyección de cobro según stock HDP **editable y compartida** (guardada en Vercel Blob).

📖 **[PROMPT_MAESTRO.md](./PROMPT_MAESTRO.md)** — reglas de negocio completas.

---

## Publicación (una sola vez por proyecto)

1. En [vercel.com/new](https://vercel.com/new): importar el repo `Vicharra463/Top-Motors-reporte` (se detecta solo; no tocar nada).
2. **Storage → Create Store → Blob** (nombre libre) → **Connect to Project** → elegir este proyecto.
3. **Deployments → Redeploy.**

Listo: el sitio sirve `public/index.html` y el endpoint `/api/stock` guarda el stock HDP en Blob — todos los que abran el enlace ven y editan la misma proyección.

## Cargar los Excel de la semana

1. Copia los archivos nuevos a `datos/`:
   - `Analisis_Ventas2026_*.xlsx` (boletas, facturas, NC/ND del año)
   - `AnalisisPedido_DD.MM.xlsx` (pedidos → modelo, color, asesor)
2. Ejecuta desde la carpeta del repo:

   ```
   pip install -r requirements.txt
   python actualizar_dashboard.py --ventas datos/Analisis_Ventas2026.xlsx --pedidos datos/AnalisisPedido_DD.MM.xlsx --plantilla plantilla_dashboard.html --salida public/index.html --previo data_ultima_version.json --guardar-datos data_nueva_version.json
   ```

3. Lee el resumen (totales, pedidos nuevos/salidos y **PARA REVISAR CON FINANZAS**). Si hay casos para revisar, no publiques: resolvelos con Finanzas primero (se agregan en CONFIGURACIÓN del script).
4. Sube los cambios:

   ```
   git add .
   git commit -m "feat: dashboard corte DD/MM/AAAA"
   git push
   ```

   Vercel republica solo en ~1 minuto.
5. Renombra `data_nueva_version.json` → `data_ultima_version.json` y súbelo (queda como comparación para la próxima).

## Ver el dashboard en local

```
python actualizar_dashboard.py --ventas datos/analisis.xlsx --pedidos datos/pedido.xlsx --plantilla plantilla_dashboard.html --salida public/index.html
```

Abre `public/index.html` en el navegador (el botón "Editar Stock HDP" requiere el sitio desplegado en Vercel con Blob conectado).

## Estructura

```
actualizar_dashboard.py   ← motor: procesa Excel y genera el HTML
plantilla_dashboard.html  ← diseño (marcador __DATA__)
public/index.html         ← sitio publicado (se genera con el script)
api/stock.js              ← endpoint que guarda/lee el stock HDP (Vercel Blob)
data_ultima_version.json  ← datos de la última versión publicada
datos/                    ← Excel de muestra (corte 26/10/2026)
docs/                     ← lista de precios vigente (PDF)
PROMPT_MAESTRO.md         ← reglas de negocio
```

## Corte de referencia (prueba inicial 26/10/2026)

- Facturación: **1,471 motos · US$ 4,562,293.57**
- Anticipos: **94 motos en 92 pedidos · saldo US$ 343,419.17 · 15 cobradas al 100%**

<!-- rebuild -->
