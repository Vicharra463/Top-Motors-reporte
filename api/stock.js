const { head, put } = require("@vercel/blob");

const MES_RE = /^\d{4}-\d{2}$/;

module.exports = async (req, res) => {
  const { searchParams } = new URL(req.url, "http://localhost");
  let mes = searchParams.get("mes");
  if (!mes && req.method === "PUT") {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    mes = body.mes;
  }
  if (!mes || !MES_RE.test(mes)) {
    res.status(400).json({ error: "mes inválido (usa AAAA-MM)" });
    return;
  }
  const path = `stock/${mes}.json`;

  if (req.method === "GET") {
    try {
      const meta = await head(path);
      if (!meta) {
        res.json({ mes, items: {}, updatedAt: null });
        return;
      }
      const txt = await (await fetch(meta.url)).text();
      res.json(JSON.parse(txt));
    } catch (e) {
      res.status(500).json({ error: "No se pudo leer el stock. ¿Está conectado el almacén Blob en Vercel?" });
    }
    return;
  }

  if (req.method === "PUT") {
    try {
      const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
      const items = body.items && typeof body.items === "object" ? body.items : {};
      const clean = {};
      for (const [k, v] of Object.entries(items)) {
        const n = Math.max(0, Math.floor(Number(v) || 0));
        if (n && k.length <= 80) clean[k] = n;
      }
      const doc = { mes, items: clean, updatedAt: new Date().toISOString() };
      await put(path, JSON.stringify(doc), { access: "public", allowOverwrite: true });
      res.json(doc);
    } catch (e) {
      res.status(500).json({ error: "No se pudo guardar. ¿Está conectado el almacén Blob en Vercel?" });
    }
    return;
  }

  res.status(405).json({ error: "Método no permitido" });
};
