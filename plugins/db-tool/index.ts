/**
 * db-tool — OpenClaw plugin
 *
 * Registers `db_query` as an OPTIONAL agent tool backed by PostgreSQL.
 *
 * Because the tool is registered with `{ optional: true }`, it is NEVER
 * auto-enabled. Only agents that explicitly list "db_query" (or "db-tool")
 * in their `agents.list[].tools.allow` array will see it.
 *
 * Connection config lives in openclaw.json:
 *   plugins.entries.db-tool.config.{ host, port, database, user, password, ssl, maxRows }
 */

import { Pool } from "pg";

// Sentinel so we can detect first-call lazy init
let pool: InstanceType<typeof Pool> | null = null;

/** Allowed SQL statement types (read-only guard) */
const READ_ONLY_RE = /^\s*(SELECT|WITH|EXPLAIN|SHOW|TABLE)\b/i;

/** Maximum rows returned per query (configurable, hard-capped at 500) */
const HARD_CAP = 500;

export default function register(api: any) {
  api.registerTool(
    {
      name: "db_query",
      description:
        "Run a read-only SQL query against the PostgreSQL database. " +
        "Only SELECT / WITH / EXPLAIN / SHOW / TABLE statements are allowed. " +
        "Returns rows as a JSON array. Use $1, $2, … for parameterised values.",

      parameters: {
        type: "object",
        additionalProperties: false,
        properties: {
          sql: {
            type: "string",
            description:
              "The SQL statement to execute. Must be a read-only statement (SELECT, WITH, EXPLAIN, SHOW, TABLE).",
          },
          params: {
            type: "array",
            items: { type: "string" },
            description:
              "Optional positional parameters that replace $1, $2, … placeholders in the SQL.",
          },
          limit: {
            type: "number",
            description:
              "Max rows to return (default 100, max 500). Use this to avoid huge result sets.",
          },
        },
        required: ["sql"],
      },

      async execute(_id: string, args: { sql: string; params?: string[]; limit?: number }) {
        const { sql, params = [], limit = 100 } = args;

        // ── Safety: read-only guard ────────────────────────────────────────
        if (!READ_ONLY_RE.test(sql)) {
          return {
            content: [
              {
                type: "text",
                text: `Error: only read-only statements are allowed (SELECT, WITH, EXPLAIN, SHOW, TABLE). Got: "${sql.slice(0, 80)}"`,
              },
            ],
          };
        }

        // ── Lazy pool init from plugin config ──────────────────────────────
        if (!pool) {
          const cfg = api.config?.plugins?.entries?.["db-tool"]?.config ?? {};
          if (!cfg.host || !cfg.database || !cfg.user || !cfg.password) {
            return {
              content: [
                {
                  type: "text",
                  text:
                    "Error: db-tool plugin is not configured. " +
                    "Set plugins.entries.db-tool.config.{ host, database, user, password } in openclaw.json.",
                },
              ],
            };
          }
          pool = new Pool({
            host:     cfg.host,
            port:     cfg.port     ?? 5432,
            database: cfg.database,
            user:     cfg.user,
            password: cfg.password,
            ssl:      cfg.ssl      ?? false,
            max:      5,           // connection pool size
            idleTimeoutMillis: 30000,
          });
          api.logger?.info("[db-tool] connection pool initialised", { host: cfg.host, database: cfg.database });
        }

        // ── Execute query ──────────────────────────────────────────────────
        const maxRows = Math.min(limit ?? 100, HARD_CAP);
        // Wrap in a LIMIT so we never accidentally pull millions of rows
        const limitedSql = /\bLIMIT\b/i.test(sql)
          ? sql
          : `${sql.replace(/;\s*$/, "")} LIMIT ${maxRows}`;

        try {
          const result = await pool.query(limitedSql, params);
          const rows = result.rows;

          const summary =
            rows.length === 0
              ? "Query returned 0 rows."
              : `${rows.length} row${rows.length === 1 ? "" : "s"} returned${rows.length >= maxRows ? ` (capped at ${maxRows})` : ""}.`;

          return {
            content: [
              {
                type: "text",
                text: `${summary}\n\n${JSON.stringify(rows, null, 2)}`,
              },
            ],
          };
        } catch (err: any) {
          api.logger?.warn("[db-tool] query error", { error: err.message });
          return {
            content: [
              {
                type: "text",
                text: `Database error: ${err.message}`,
              },
            ],
          };
        }
      },
    },

    // ── OPTIONAL: never auto-enabled, must be listed in agent's tools.allow ──
    { optional: true },
  );
}
