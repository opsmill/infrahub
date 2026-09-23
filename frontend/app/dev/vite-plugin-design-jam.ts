/**
 * Dev-only bridge from the prototype back into the repo.
 *
 * Without this, knob values and annotations live in the browser and reach the agent as a
 * pasted block. With it, Save writes them into `.design/<slug>/`, so they are committed
 * with the rest of the design history and the agent's next turn just reads them.
 *
 * `apply: "serve"` is not a precaution, it is the whole safety story: this plugin writes
 * files from an unauthenticated POST and must never exist in a production build.
 *
 * Register in vite.config.ts:
 *   import { designJam } from "./dev/vite-plugin-design-jam";
 *   plugins: [react(), designJam()]
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

import type { Plugin } from "vite";

type Payload = {
  slug: string;
  variant: string;
  rev: number;
  knobs: Record<string, unknown>;
  /** Markdown, already formatted by the panel. */
  notes: string;
};

const SAFE_SLUG = /^[a-z0-9][a-z0-9-]{0,63}$/;

export function designJam(options: { root?: string } = {}): Plugin {
  const base = options.root ?? ".design";

  return {
    name: "design-jam",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__design-jam/save", (req, res) => {
        if (req.method !== "POST") {
          res.statusCode = 405;
          res.end();
          return;
        }

        let body = "";
        req.on("data", (chunk) => {
          body += chunk;
          if (body.length > 1_000_000) req.destroy();
        });

        req.on("end", () => {
          let payload: Payload;
          try {
            payload = JSON.parse(body);
          } catch {
            res.statusCode = 400;
            res.end("bad json");
            return;
          }

          if (!SAFE_SLUG.test(payload.slug ?? "")) {
            res.statusCode = 400;
            res.end("bad slug");
            return;
          }

          const dir = resolve(server.config.root, base, payload.slug);
          const root = resolve(server.config.root, base);
          if (dirname(dir) !== root) {
            res.statusCode = 400;
            res.end("bad path");
            return;
          }

          const stamp = new Date().toISOString();
          const scope = `${payload.variant} · rev ${payload.rev}`;

          try {
            mkdirSync(dir, { recursive: true });
            writeFileSync(
              join(dir, "knobs.json"),
              `${JSON.stringify(
                { variant: payload.variant, rev: payload.rev, knobs: payload.knobs },
                null,
                2
              )}\n`
            );
            writeFileSync(
              join(dir, "feedback.md"),
              `# Feedback — ${scope}\n\n_Saved ${stamp} from the prototype._\n\n${
                payload.notes || "_No notes._"
              }\n`
            );
          } catch (error) {
            server.config.logger.error(`[design-jam] write failed: ${error}`);
            res.statusCode = 500;
            res.end("write failed");
            return;
          }

          server.config.logger.info(`[design-jam] saved ${payload.slug} (${scope})`);
          // A JSON body with an explicit marker, not a bare 204: when this plugin is not
          // registered, Vite's SPA fallback answers the same URL with 200 and index.html,
          // and a client that only checks `res.ok` reports a successful save that never
          // happened. The marker is what the panel actually verifies.
          res.statusCode = 200;
          res.setHeader("content-type", "application/json");
          res.end(
            JSON.stringify({
              designJam: true,
              path: `${base}/${payload.slug}/feedback.md`,
            })
          );
        });
      });
    },
  };
}
