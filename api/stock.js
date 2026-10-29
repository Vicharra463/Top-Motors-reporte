const TOKEN = process.env.BLOB_READ_WRITE_TOKEN || "";
const API = "https://vercel.com/api/blob/";

function parseStoreId(token) {
  const m = /^vercel_blob_rw_([A-Za-z0-9]+)_/.exec(token);
  return m ? m[1] : null;
}

function publicUrl(shortId, pathname) {
  return `https://${shortId.toLowerCase()}.public.blob.vercel-storage.com/${pathname}`;
}

module.exports = async (req, res) => {
  const { searchParams } = new URL(req.url, "http://localhost");
  let mes = searchParams.get("mes");
  if (!mes && req.method === "PUT") {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    mes = body.mes;
  }
  if (!mes || !/^\d{4}-\d{2}$/.test(mes)) {
    res.status(400).json({ error: "mes inválido (usa AAAA-MM)" });
    return;
  }
  const pathname = `stock/${mes}.json`;
  const shortId = parseStoreId(TOKEN);
  if (!shortId) {
    res.status(500).json({ error: "Almacén Blob no conectado. Sigue el README: Storage → Create Blob → Connect to Project." });
    return;
  }

  if (req.method === "GET") {
    try {
      const r = await fetch(publicUrl(shortId, pathname));
      if (r.status === 404) {
        res.json({ mes, items: {}, updatedAt: null });
        return;
      }
      if (!r.ok) {
        res.status(502).json({ error: "No se pudo leer el stock (" + r.status + ")." });
        return;
      }
      res.json(JSON.parse(await r.text()));
    } catch (e) {
      res.status(500).json({ error: "No se pudo leer el stock." });
    }
    return;
  }

  if (req.method === "PUT" || req.method === "POST") {
    try {
      const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
      const items = body.items && typeof body.items === "object" ? body.items : {};
      const clean = {};
      for (const [k, v] of Object.entries(items)) {
        const n = Math.max(0, Math.floor(Number(v) || 0));
        if (n && k.length <= 80) clean[k] = n;
      }
      const doc = { mes, items: clean, updatedAt: new Date().toISOString() };
      const r = await fetch(API + "?pathname=" + encodeURIComponent(pathname), {
        method: "PUT",
        headers: {
          authorization: "Bearer " + TOKEN,
          "x-vercel-blob-store-id": "store_" + shortId,
          "x-api-version": "13",
          "content-type": "application/json",
        },
        body: JSON.stringify(doc),
      });
      if (!r.ok) {
        res.status(502).json({ error: "No se pudo guardar (" + r.status + ")." });
        return;
      }
      res.json(doc);
    } catch (e) {
      res.status(500).json({ error: "No se pudo guardar." });
    }
    return;
  }

  res.status(405).json({ error: "Método no permitido" });
};
