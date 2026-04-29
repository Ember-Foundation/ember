"use strict";
const cluster = require("cluster");
const http = require("http");
const path = require("path");

// Reuse the existing taskbench express install to avoid duplicating node_modules.
const express = require(path.join(__dirname, "..", "..", "..", "express_app", "node_modules", "express"));

const PORT = parseInt(process.env.PORT || "9011", 10);
const WORKERS = parseInt(process.env.WORKERS || "1", 10);

if (cluster.isPrimary && WORKERS > 1) {
  for (let i = 0; i < WORKERS; i++) cluster.fork();
  cluster.on("exit", (w) => { console.error(`worker ${w.process.pid} died`); cluster.fork(); });
  console.log(`Express on :${PORT}, ${WORKERS} workers`);
} else {
  const app = express();
  app.get("/hello", (_req, res) => res.type("text").send("Hello, World!"));
  http.createServer(app).listen(PORT, "0.0.0.0", () => {
    if (WORKERS === 1) console.log(`Express on :${PORT}, single worker`);
  });
}
