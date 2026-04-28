"""Create ember schema, tasks table, and seed 1000 rows."""
import asyncio
import asyncpg

DB = dict(host="localhost", port=5333, user="postgres", password="postgres", database="salesbird")
PRIORITIES = ["low", "medium", "high"]


async def main():
    conn = await asyncpg.connect(**DB)

    # Schema
    await conn.execute("CREATE SCHEMA IF NOT EXISTS ember;")

    # Table inside ember schema
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ember.tasks (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            title       TEXT        NOT NULL,
            description TEXT        NOT NULL DEFAULT '',
            completed   BOOLEAN     NOT NULL DEFAULT FALSE,
            priority    TEXT        NOT NULL DEFAULT 'medium',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS tasks_created_at_idx ON ember.tasks (created_at DESC);"
    )

    count = await conn.fetchval("SELECT COUNT(*) FROM ember.tasks")
    if count >= 1000:
        print(f"Already seeded ({count} rows) — truncating and re-seeding...")
        await conn.execute("TRUNCATE TABLE ember.tasks RESTART IDENTITY;")

    rows = [
        (
            f"Task {i}: Fix issue #{i * 7}",
            f"Description for task {i}. Priority escalation needed.",
            i % 3 == 0,
            PRIORITIES[i % 3],
        )
        for i in range(1, 1001)
    ]

    await conn.executemany(
        "INSERT INTO ember.tasks (title, description, completed, priority) VALUES ($1,$2,$3,$4)",
        rows,
    )

    final = await conn.fetchval("SELECT COUNT(*) FROM ember.tasks")
    print(f"Schema: ember  |  Table: tasks  |  Rows: {final}")
    await conn.close()


asyncio.run(main())
