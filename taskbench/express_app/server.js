'use strict';
/**
 * Express task manager — PostgreSQL (schema: ember)
 */
const cluster = require('cluster');
const os      = require('os');
const express = require('express');
const { Pool } = require('pg');

const PORT    = 9003;
const WORKERS = 1;

if (cluster.isMaster || cluster.isPrimary) {
  console.log(`  🟢  Express  |  0.0.0.0:${PORT}  |  ${WORKERS} workers  |  PRODUCTION`);
  for (let i = 0; i < WORKERS; i++) cluster.fork();
  cluster.on('exit', () => cluster.fork());
  return;
}

// ── DB pool (per worker) ───────────────────────────────────────────────────────
const pool = new Pool({
  host: 'localhost', port: 5333,
  user: 'postgres', password: 'postgres', database: 'salesbird',
  max: 20, idleTimeoutMillis: 30000,
  options: '-c search_path=ember',
});

// ── App ────────────────────────────────────────────────────────────────────────
const app = express();
app.use(express.json());
app.disable('x-powered-by');
app.disable('etag');

const rowToObj = r => ({
  ...r,
  id:         r.id,
  created_at: r.created_at.toISOString(),
  updated_at: r.updated_at.toISOString(),
});

// ── Routes ─────────────────────────────────────────────────────────────────────

app.get('/health', async (req, res) => {
  const { rows } = await pool.query('SELECT COUNT(*) FROM tasks');
  res.json({ status: 'ok', tasks: parseInt(rows[0].count) });
});

app.get('/tasks', async (req, res) => {
  const page   = parseInt(req.query.page  || '1',  10);
  const limit  = parseInt(req.query.limit || '20', 10);
  const offset = (page - 1) * limit;
  const [data, count] = await Promise.all([
    pool.query('SELECT * FROM tasks ORDER BY created_at DESC LIMIT $1 OFFSET $2', [limit, offset]),
    pool.query('SELECT COUNT(*) FROM tasks'),
  ]);
  res.json({ tasks: data.rows.map(rowToObj), total: parseInt(count.rows[0].count), page, limit });
});

app.get('/tasks/all', async (req, res) => {
  const { rows } = await pool.query('SELECT * FROM tasks ORDER BY created_at DESC');
  res.json({ tasks: rows.map(rowToObj), total: rows.length });
});

app.get('/tasks/:id', async (req, res) => {
  const { rows } = await pool.query('SELECT * FROM tasks WHERE id = $1', [req.params.id]);
  if (!rows.length) return res.status(404).json({ error: 'Task not found' });
  res.json(rowToObj(rows[0]));
});

app.post('/tasks', async (req, res) => {
  const { title = 'Untitled', description = '', completed = false, priority = 'medium' } = req.body;
  const { rows } = await pool.query(
    'INSERT INTO tasks (title,description,completed,priority) VALUES($1,$2,$3,$4) RETURNING *',
    [title, description, Boolean(completed), priority],
  );
  res.status(201).json(rowToObj(rows[0]));
});

app.patch('/tasks/:id', async (req, res) => {
  const { title, description, completed, priority } = req.body;
  const { rows } = await pool.query(
    `UPDATE tasks SET
       title       = COALESCE($2, title),
       description = COALESCE($3, description),
       completed   = COALESCE($4, completed),
       priority    = COALESCE($5, priority),
       updated_at  = NOW()
     WHERE id = $1 RETURNING *`,
    [req.params.id,
     title       ?? null,
     description ?? null,
     completed   != null ? Boolean(completed) : null,
     priority    ?? null],
  );
  if (!rows.length) return res.status(404).json({ error: 'Task not found' });
  res.json(rowToObj(rows[0]));
});

app.delete('/tasks/:id', async (req, res) => {
  const result = await pool.query('DELETE FROM tasks WHERE id = $1', [req.params.id]);
  if (result.rowCount === 0) return res.status(404).json({ error: 'Task not found' });
  res.status(204).send();
});

app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).json({ error: err.message });
});

const server = app.listen(PORT, '0.0.0.0');
server.keepAliveTimeout = 65000;
server.headersTimeout   = 66000;
