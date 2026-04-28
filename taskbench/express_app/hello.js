"use strict";
const cluster = require("cluster");
const http    = require("http");
const express = require("express");

const PORT    = 9011;
const WORKERS = 1;

if (cluster.isPrimary) {
  for (let i = 0; i < WORKERS; i++) cluster.fork();
  cluster.on("exit", (w) => { console.error(`Worker ${w.process.pid} died`); cluster.fork(); });
  console.log(`  🟢  Express hello  |  0.0.0.0:${PORT}  |  ${WORKERS} workers  |  PRODUCTION`);
} else {
  const app = express();

  app.get("/hello", (_req, res) => {
    res.type("text").send("Hello, World!");
  });

  http.createServer(app).listen(PORT, "0.0.0.0");
}
