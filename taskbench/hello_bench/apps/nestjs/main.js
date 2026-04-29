"use strict";
require("reflect-metadata");
const cluster = require("cluster");
const { NestFactory } = require("@nestjs/core");
const { Module, Controller, Get, Header } = require("@nestjs/common");

const PORT = parseInt(process.env.PORT || "9014", 10);
const WORKERS = parseInt(process.env.WORKERS || "1", 10);

let HelloController = class HelloController {
  hello() { return "Hello, World!"; }
};
const getDecorator = Get("/hello");
getDecorator(HelloController.prototype, "hello", Object.getOwnPropertyDescriptor(HelloController.prototype, "hello"));
const headerDecorator = Header("Content-Type", "text/plain; charset=utf-8");
headerDecorator(HelloController.prototype, "hello", Object.getOwnPropertyDescriptor(HelloController.prototype, "hello"));
HelloController = Controller()(HelloController) || HelloController;

let AppModule = class AppModule {};
AppModule = Module({ controllers: [HelloController] })(AppModule) || AppModule;

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { logger: false });
  await app.listen(PORT, "0.0.0.0");
  if (WORKERS === 1) console.log(`NestJS on :${PORT}, single worker`);
}

if (cluster.isPrimary && WORKERS > 1) {
  for (let i = 0; i < WORKERS; i++) cluster.fork();
  cluster.on("exit", (w) => { console.error(`worker ${w.process.pid} died`); cluster.fork(); });
  console.log(`NestJS on :${PORT}, ${WORKERS} workers`);
} else {
  bootstrap().catch((e) => { console.error(e); process.exit(1); });
}
