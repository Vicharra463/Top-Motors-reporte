#!/usr/bin/env python3
"""
Dashboard "Facturación de motos y anticipos por cobrar" — Top Motors (Finanzas)

Procesa los Excel del sistema y genera el HTML del dashboard listo para publicar.

Uso:
    python3 actualizar_dashboard.py \
        --ventas Analisis_Ventas2026.xlsx \
        --pedidos AnalisisPedido_DD.MM.xlsx \
        --plantilla plantilla_dashboard.html \
        --salida dashboard.html \
        [--previo data_ultima_version.json] \
        [--guardar-datos data_nueva_version.json]

Requiere: pandas, openpyxl.

Todo lo que define el negocio está en la sección CONFIGURACIÓN. Si cambia la
lista de precios, se confirma un precio nuevo o una excepción, se edita ahí.
"""
import argparse, json, re, sys
from collections import Counter
import pandas as pd

# ============================================================================
# CONFIGURACIÓN DEL NEGOCIO
# ============================================================================

# Etiqueta que se muestra como origen del precio.
ETIQUETA_LISTA = "Lista Oct-26"

# Lista de precios de la campaña vigente (PDF "Promociones Oct-26"), en US$.
# Se compara por PREFIJO del código SKU del pedido, en este orden (el primero
# que coincide gana, por eso los más específicos van antes).
LISTA_PRECIOS = [
    ("CB TWISTER 300", 4390), ("CB190R", 2949), ("NAVI", 1549),
    ("XL750 TRANSALP_BLA", 13290), ("XL750CT-BLA", 13290),   # Transalp con E-Clutch (blanco)
    ("XL750", 12790),                                         # Transalp sin E-Clutch (negro/gris)
    ("ELITE 125", 2269), ("PCX160", 3950), ("NX500", 8990),
    ("CRF1100AT", 19500),                                     # Africa Twin
    ("CRF300LAT", 6990), ("CRF300LRAP", 6990),                # CRF300L
    ("XBLADE", 2485), ("CBF125Z", 2299),                      # CBF125Z = CB125 Hornet
    ("CB350DV", 4190), ("XR190L", 3272), ("DIO", 1670), ("NX190", 3850),
    ("XR150L", 2674), ("CB100", 1199), ("GL125", 1794), ("WAVE", 1759), ("XR190CT", 4114),
]

# Modelos que NO están en la lista y cuyo precio confirmó Finanzas.
PRECIOS_FINANZAS = {
    "CRF1100D4T": (25090, "Lista Finanzas"),
    "CBR500RAN": (11000, "Precio aprox. (Finanzas)"),
}

# Nombre de modelo para SKUs que no aparecen en ventas o que se agrupan con otro.
MODELO_POR_SKU = {
    "CBR500RAN-ROJ": "CBR500RAN",
    "CRF300LRAP-ROJ": "CRF300LAT",      # CRF300LRAP se reporta como CRF300LAT
    "XL750CT-BLA": "XL750 TRANSALP", "XL750T-GRI": "XL750 TRANSALP",
    "CRF1100D4T-BLA": "CRF1100D4T", "CRF1100AT-BLA": "CRF1100AT",
    "CB350DV-GRIPER": "CB350DV", "CBF125Z-NEG": "CBF125Z",
}

# Excepciones confirmadas por Finanzas, por N° de pedido.
#  - precio: reemplaza el precio de lista
#  - dscto_por_moto: descuento por moto (reemplaza el de la glosa)
#  - dscto_igual_a_saldo: el saldo restante se considera descuento (queda pagado 100%)
EXCEPCIONES = {
    35152: dict(precio=13290, dscto_por_moto=500,
                detalle="Transalp E-Clutch, venta a empresa: dscto $500 por moto (3 motos)"),
    40391: dict(dscto_igual_a_saldo=True, detalle="Descuento confirmado por Finanzas"),
}

# Cobros mayores al precio ya revisados (no se vuelven a alertar).
EXCEDENTES_CONFIRMADOS = {
    40381: "Incluye Pack Navi S/850",
    40275: "Incluye adicional por comisión de financiera",
}

# El bono de $200 de la CB190R 2.0 ya está incluido en el precio de lista: no se resta.
BONO_INCLUIDO = {"CB190R 2.0": 200}

# Colores reconocidos en la descripción del pedido (los compuestos primero).
COLORES = ["NEGRO BRILLANTE", "NEGRO METÁLICO", "NEGRO METALICO", "GRIS PERLADO", "GRIS METÁLICO",
           "GRIS METALICO", "BLANCO", "ROJO", "ROJA", "AZUL", "ANARANJADO", "NARANJA", "ROSADO",
           "VERDE", "GRIS", "NEGRO", "BEIGE", "AMARILLO", "PLATA", "TURQUESA"]

# ============================================================================


def leer_ventas(path):
    v = pd.read_excel(path, header=1).iloc[:, :23]
    v = v[v["Documento"].notna() & v["Categorias"].notna()].copy()
    v = v[~v["Estado"].astype(str).str.contains("Total")]             # subtotales de la tabla dinámica
    v["Fecha"] = pd.to_datetime(v["Fecha"])
    v["USD"] = v["Importe Total $"].round(2)
    v["tipo"] = v["Documento"].str[:2]
    filas_dup = v[v.duplicated(["Documento", "Lote"], keep="first") & (v.Categorias == "VEHICULOS")]
    v = v.drop_duplicates(subset=["Documento", "Código (SKU)", "Lote", "USD"])  # misma boleta en 2 guías
    v["VIN"] = v["Lote"].astype(str).str.extract(r"SERIE:([^|]+)")[0].str.strip()
    # Regla 1: documento referenciado por NC/ND con el MISMO importe = anulado (se excluyen ambos)
    orig = v[v.tipo.isin(["BV", "FT"])].groupby("Documento").USD.sum()
    nc = v[v.tipo.isin(["NC", "ND"])]
    anul = {ref for ref, g in nc.groupby("Doc. Referencia")
            if ref in orig.index and any(abs(x + orig[ref]) < 0.05 for x in g.USD)}
    v["anulado"] = v.Documento.isin(anul)
    v["nc_fuera"] = v.tipo.isin(["NC", "ND"]) & ~v["Doc. Referencia"].isin(orig.index)
    v["nc_parcial"] = v.tipo.isin(["NC", "ND"]) & v["Doc. Referencia"].isin(orig.index) & ~v["Doc. Referencia"].isin(anul)
    return v, filas_dup


def leer_pedidos(path):
    p = pd.read_excel(path, header=1)
    p = p[p["Nro Pedido"].notna()].copy()
    p["Nro Pedido"] = p["Nro Pedido"].astype(int)
    # "Cant. Pedido" de la tabla dinámica cuenta documentos, no motos: precio unitario = P.U. / Cant.
    p["precio_ped"] = (p["P.U. Pedido"] / p["Cant. Pedido"]).round(2)
    return p.set_index("Nro Pedido")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ventas", required=True)
    ap.add_argument("--pedidos", required=True)
    ap.add_argument("--plantilla", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--previo")
    ap.add_argument("--guardar-datos")
    a = ap.parse_args()

    v, filas_dup = leer_ventas(a.ventas)
    P = leer_pedidos(a.pedidos)
    sku2mod = v[v.Modelo.notna()].groupby("Código (SKU)").Modelo.first().to_dict()
    revisar = []

    def modelo(sku):
        if sku in sku2mod: return sku2mod[sku]
        if sku in MODELO_POR_SKU: return MODELO_POR_SKU[sku]
        for k in sorted(set(sku2mod.values()), key=len, reverse=True):
            if sku.upper().replace("XBLADE", "X-BLADE").startswith(k.replace("CB TWISTER 300 ABS", "CB TWISTER 300")):
                return k
        return sku

    def precio(sku):
        s = sku.upper()
        for k, pr in LISTA_PRECIOS:
            if s.startswith(k): return pr, ETIQUETA_LISTA
        for k, (pr, et) in PRECIOS_FINANZAS.items():
            if s.startswith(k): return pr, et
        return None, None

    def color(ped):
        d = str(P.loc[ped, "Descripción"]).upper().replace("_", " ").replace("-", " ")
        for c in COLORES:
            if re.search(r"\b" + c + r"\b", d):
                return {"ROJA": "Rojo", "NARANJA": "Anaranjado"}.get(c, c.title().replace("Metalico", "Metálico"))
        return "—"

    rx = re.compile(r"(?:DSCTO?|DSTO|DESCUENTO|BONO)\s*\$\s*\.?\s*([\d,]+(?:\.\d+)?)|\$\s*([\d,]+(?:\.\d+)?)\s*(?:DSCTO?|DSTO|DESCUENTO|DCTO)", re.I)

    # ---------------- Anticipos vigentes ----------------
    ant = v[(v.Categorias == "ANTICIPOS") & v.tipo.isin(["BV", "FT"]) & ~v.anulado]
    sin_ped = ant[ant["N° Pedido"].isna()]
    for _, r in sin_ped.iterrows():
        revisar.append(f"Anticipo sin N° de pedido: {r.Documento} · {r.Cliente.strip()} · US$ {r.USD:,.2f} (no se incluye)")
    rows = []
    for ped, g in ant[ant["N° Pedido"].notna()].groupby("N° Pedido"):
        ped = int(ped); g = g.sort_values("Fecha")
        if ped not in P.index:
            revisar.append(f"Pedido {ped} no está en el archivo de pedidos (no se incluye)"); continue
        sku = P.loc[ped, "Código"]; mod = modelo(sku)
        glosa = " | ".join(g["glosa cabecera"].dropna().unique())
        lp, fuente = precio(sku)
        if lp is None:
            revisar.append(f"Pedido {ped}: modelo {sku} sin precio de lista. Se usó el precio del pedido ${P.loc[ped,'precio_ped']:,.2f}; confirmar con Finanzas")
            lp, fuente = float(P.loc[ped, "precio_ped"]), "Precio de pedido (confirmar)"
        n = 1
        m = re.search(r"SEPARACI[OÓ]N DE (\d+)", glosa, re.I)
        if m:
            n = int(m.group(1))
            if ped not in EXCEPCIONES: revisar.append(f"Pedido {ped}: la glosa indica {n} unidades; se calcularon {n} motos")
        dsc, det = 0.0, ""
        dm = rx.search(glosa)
        if dm:
            dsc = float((dm.group(1) or dm.group(2)).replace(",", "").rstrip("."))
            if BONO_INCLUIDO.get(mod) == dsc: dsc, det = 0.0, f"Bono ${BONO_INCLUIDO[mod]} ya incluido en precio de lista"
            else: det = f"Dscto ${dsc:,.2f} (glosa)"
        cob = round(g.USD.sum(), 2)
        ex = EXCEPCIONES.get(ped)
        if ex:
            if "precio" in ex: lp = ex["precio"]
            if "dscto_por_moto" in ex: dsc = ex["dscto_por_moto"]
            if ex.get("dscto_igual_a_saldo"): dsc = round(lp - cob, 2)
            det = ex.get("detalle", det)
        valor = round(lp * n - dsc * n, 2); saldo = round(valor - cob, 2)
        if saldo < -0.5:
            extra = EXCEDENTES_CONFIRMADOS.get(ped) or ("Incluye Pack Navi S/850" if re.search(r"NAVI PACK", glosa, re.I) else "Cobrado mayor al precio (adicional / comisión financiera)")
            det = (det + " · " if det else "") + extra
            if ped not in EXCEDENTES_CONFIRMADOS: revisar.append(f"Pedido {ped} ({mod}): cobrado ${cob:,.2f} supera el valor ${valor:,.2f} en ${-saldo:,.2f} → {extra}")
        rows.append(dict(ped=ped, fecha=g.Fecha.min().strftime("%d/%m/%Y"), cli=g.Cliente.iloc[0].strip().title(),
                         ase=g.Vendedor.iloc[0].title(), mod=mod, sku=sku, color=color(ped), motos=n, lista=lp,
                         fuente=fuente, dsc=dsc * n, det=det, valor=valor, cob=cob, saldo=max(saldo, 0),
                         exceso=max(-saldo, 0), pagos=len(g), docs=", ".join(g.Documento),
                         precio_ped=float(P.loc[ped, "precio_ped"])))

    # ---------------- Motos facturadas ----------------
    veh = v[(v.Categorias == "VEHICULOS") & v.tipo.isin(["BV", "FT"]) & ~v.anulado]
    for vin, n in Counter(veh.VIN).items():
        if n > 1:
            docs = ", ".join(veh[veh.VIN == vin].Documento)
            revisar.append(f"VIN DUPLICADO {vin}: {docs} — revisar antes de publicar")
    fact = [dict(f=r.Fecha.strftime("%Y-%m-%d"), doc=r.Documento,
                 ped=(int(r["N° Pedido"]) if pd.notna(r["N° Pedido"]) else None),
                 cli=r.Cliente.strip().title(), ase=r.Vendedor.title(), mod=r.Modelo, usd=round(r.USD, 2))
            for _, r in veh.iterrows()]
    for _, r in v[v.nc_parcial].iterrows():
        revisar.append(f"Nota de crédito parcial {r.Documento} sobre {r['Doc. Referencia']} (US$ {r.USD:,.2f}): el documento no se anuló; revisar")

    # ---------------- Criterios (se generan con los datos) ----------------
    con_dscto = [r for r in rows if r["dsc"] > 0]
    dtxt = "; ".join(f"{r['mod']} ${r['dsc']:,.2f} ({r['ped']})" for r in sorted(con_dscto, key=lambda r: r["ped"]))
    exc = [r for r in rows if r["exceso"] > 0.5]
    etxt = " ".join(f"{r['mod']} {r['ped']}: {r['det'].split(' · ')[-1]}." for r in exc)
    obs = [
        dict(t="Documentos anulados", h="Si una nota de crédito referencia un documento por el mismo importe, se excluyen ambos. Así salen las devoluciones y los anticipos ya aplicados a la factura de la moto."),
        dict(t="Cobrado", h="Suma de los anticipos vigentes facturados (Analisis_Ventas2026), en US$."),
        dict(t="Valor de la moto", h="Precio de la lista de precios vigente, menos el descuento de la glosa."),
        dict(t="Descuentos aplicados", h=(dtxt + "." if dtxt else "Sin descuentos en los anticipos vigentes.")),
    ]
    if exc: obs.append(dict(t="Cobrado mayor al valor", h="Se considera cobrado al 100%. " + etxt))

    data = dict(anticipos=rows, fact=fact, obs=obs, corte=v.Fecha.max().strftime("%d/%m/%Y"))
    html = open(a.plantilla, encoding="utf-8").read()
    if "__DATA__" not in html: sys.exit("La plantilla no tiene el marcador __DATA__")
    open(a.salida, "w", encoding="utf-8").write(html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
    if a.guardar_datos: json.dump(data, open(a.guardar_datos, "w", encoding="utf-8"), ensure_ascii=False)

    # ---------------- Resumen y cambios vs. versión previa ----------------
    S = lambda k: sum(r[k] for r in rows)
    print(f"Corte: {data['corte']}")
    print(f"Facturación: {len(fact)} motos · US$ {sum(x['usd'] for x in fact):,.2f}")
    print(f"Anticipos: {S('motos')} motos en {len(rows)} pedidos · valor US$ {S('valor'):,.2f} · cobrado US$ {S('cob'):,.2f} · saldo US$ {S('saldo'):,.2f} · cobradas 100%: {sum(r['motos'] for r in rows if r['saldo'] <= 0.005)}")
    if a.previo:
        prev = json.load(open(a.previo, encoding="utf-8"))
        O = {r["ped"]: r for r in prev["anticipos"]}; N = {r["ped"]: r for r in rows}
        print(f"Pedidos que salieron (facturados/anulados): {sorted(set(O) - set(N))}")
        print(f"Pedidos nuevos: {sorted(set(N) - set(O))}")
        for k in sorted(set(N) & set(O)):
            if abs(N[k]["cob"] - O[k]["cob"]) > 0.01:
                print(f"  Pedido {k} ({N[k]['mod']}): cobrado {O[k]['cob']:,.2f} → {N[k]['cob']:,.2f}")
    print("\nPARA REVISAR CON FINANZAS:" if revisar else "\nSin casos nuevos para revisar.")
    for x in revisar: print(" - " + x)


if __name__ == "__main__":
    main()
