// Generator for `frontend/app/src/shared/api/errors/catalogue.generated.ts`.
// Reads `schema/error-catalogue.json` (produced by the backend per
// INFP-468 US1 / T011) and emits a TypeScript discriminated union of every
// catalogue error, plus the payload interfaces inferred from each code's
// `data_schema`.
//
// Usage:
//   pnpm generate:error-bindings  → write the file
//   pnpm check:error-bindings     → fail if the file is out of date
//
// The output is committed; we don't generate at install time. That keeps
// the CI graph simple (running tests does not require a generator step)
// and makes catalogue drift visible in PR diffs.
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { compile, type JSONSchema } from "json-schema-to-typescript";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, "..", "..", "..");
const SCHEMA_PATH = path.join(REPO_ROOT, "schema", "error-catalogue.json");
const OUTPUT_PATH = path.resolve(
  SCRIPT_DIR,
  "..",
  "src",
  "shared",
  "api",
  "errors",
  "catalogue.generated.ts"
);

type CatalogueEntry = {
  description: string;
  stability: string;
  http_status: number;
  data_schema: JSONSchema & { title: string };
};

type Catalogue = {
  infrahub_catalogue_version: string;
  generated_at: string;
  codes: Record<string, CatalogueEntry>;
};

// Drop `title` from every nested property, keeping only the top-level one.
// json-schema-to-typescript extracts a separate alias for any sub-schema
// that has a `title`; without this step every code carrying `node_kind`
// gets its own `type NodeKind = string` line, and the file fails to
// compile with duplicate-identifier errors.
function stripInnerTitles(schema: JSONSchema & { title: string }): JSONSchema {
  const topTitle = schema.title;
  const cloned = JSON.parse(JSON.stringify(schema)) as Record<string, unknown>;
  function walk(node: unknown, isRoot: boolean) {
    if (node === null || typeof node !== "object") return;
    if (Array.isArray(node)) {
      for (const item of node) walk(item, false);
      return;
    }
    const obj = node as Record<string, unknown>;
    if ("title" in obj && !isRoot) {
      // biome-ignore lint/performance/noDelete: json-schema-to-typescript checks own-property `title` directly — reassigning to undefined would not stop alias extraction.
      delete obj.title;
    }
    for (const value of Object.values(obj)) walk(value, false);
  }
  walk(cloned, true);
  cloned.title = topTitle;
  return cloned as JSONSchema;
}

async function generate(): Promise<string> {
  const raw = await fs.readFile(SCHEMA_PATH, "utf-8");
  const catalogue = JSON.parse(raw) as Catalogue;

  // Sort codes alphabetically — the JSON's iteration order shouldn't drive
  // diff churn when the backend reorders entries.
  const codes = Object.keys(catalogue.codes).sort();

  // Compile each `data_schema` into a standalone TS interface. We hand
  // json-schema-to-typescript a schema whose top-level `title` is the
  // desired type name. Inner properties also carry `title` (set by the
  // backend's Pydantic-driven schema export) — those would be extracted
  // as auxiliary `type NodeKind = string` aliases, and the same alias
  // would appear in every code that uses a `node_kind` field, breaking
  // the build with duplicate-identifier errors. Strip inner titles before
  // compiling so the property types stay inline.
  const dataTypes = await Promise.all(
    codes.map(async (code) => {
      const entry = catalogue.codes[code];
      const schema = stripInnerTitles(entry.data_schema);
      const compiled = await compile(schema, entry.data_schema.title, {
        bannerComment: "",
        additionalProperties: false,
        format: false, // we run biome on the final file
      });
      return {
        code,
        typeName: entry.data_schema.title,
        httpStatus: entry.http_status,
        description: entry.description,
        body: compiled.trim(),
      };
    })
  );

  const header = [
    "// AUTO-GENERATED — DO NOT EDIT.",
    "// Source: schema/error-catalogue.json",
    `// Catalogue version: ${catalogue.infrahub_catalogue_version}`,
    "// Regenerate with: pnpm generate:error-bindings",
    "",
  ].join("\n");

  const dataBlocks = dataTypes.map((d) => d.body).join("\n\n");

  const errorCodesBlock = [
    "export const ERROR_CODES = {",
    ...codes.map((c) => `  ${c}: "${c}",`),
    "} as const;",
    "",
    "export type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];",
  ].join("\n");

  const httpStatusBlock = [
    "// Default `http_status` per code, as declared by the backend catalogue.",
    "// The runtime envelope still carries `http_status` so consumers can prefer",
    "// that; this lookup is for callers that need the status without a payload.",
    "export const ERROR_HTTP_STATUS: Record<ErrorCode, number> = {",
    ...dataTypes.map((d) => `  ${d.code}: ${d.httpStatus},`),
    "};",
  ].join("\n");

  const unionBlock = [
    "// Discriminated union over every catalogue code. Narrowing on `code`",
    "// gives full type-safety for `data` at the call site.",
    "export type CatalogueError =",
    ...dataTypes.map(
      (d) => `  | { code: typeof ERROR_CODES.${d.code}; http_status: number; data: ${d.typeName} }`
    ),
    "  ;",
  ].join("\n");

  return [header, dataBlocks, "", errorCodesBlock, "", httpStatusBlock, "", unionBlock, ""].join(
    "\n"
  );
}

async function main() {
  const checkMode = process.argv.includes("--check");
  const next = await generate();

  if (checkMode) {
    let existing = "";
    try {
      existing = await fs.readFile(OUTPUT_PATH, "utf-8");
    } catch {
      existing = "";
    }
    if (existing !== next) {
      console.error(
        `error-bindings out of date — ${path.relative(REPO_ROOT, OUTPUT_PATH)} ` +
          "does not match schema/error-catalogue.json. Run `pnpm generate:error-bindings`."
      );
      process.exit(1);
    }
    console.info("error-bindings up to date.");
    return;
  }

  await fs.mkdir(path.dirname(OUTPUT_PATH), { recursive: true });
  await fs.writeFile(OUTPUT_PATH, next);
  console.info(`wrote ${path.relative(REPO_ROOT, OUTPUT_PATH)}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
