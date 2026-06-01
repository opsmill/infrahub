// @ts-check
// Generator for `frontend/app/src/shared/api/errors/catalogue.generated.ts`.
//
// Reads `schema/error-catalogue.json` (produced by the backend per
// INFP-468 US1 / T011) and emits a TypeScript discriminated union of
// every catalogue error, plus a per-code HTTP status lookup and the
// payload interfaces inferred from each code's `data_schema`.
//
// Usage:
//   pnpm generate:error-bindings   → write the file
//   pnpm check:error-bindings      → fail if the file is out of date
//
// Why hand-rolled instead of `json-schema-to-typescript`?
//   The catalogue's JSON Schema uses a narrow vocabulary today: primitive
//   types, nullable wrappers via `anyOf [..., {type: "null"}]`, and flat
//   objects with `required` lists. Hand-rolling that conversion is ~30
//   lines and avoids a ~10 MB devDep + a TS runner. If the backend ever
//   introduces nested objects, `$ref`s, arrays, or other constructs, this
//   script throws an `Unsupported schema` error with the offending blob —
//   that's the right time to reach for a fuller library, not before.
//
// The output is committed; we don't generate at install time. That keeps
// the CI graph simple and makes catalogue drift visible in PR diffs.
// `frontend-validate-error-catalogue` in .github/workflows/ci.yml runs
// `pnpm check:error-bindings` and fails when the committed file is stale.
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

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

/**
 * @param {unknown} condition
 * @param {string} message
 * @returns {asserts condition}
 */
function assert(condition, message) {
  if (!condition) throw new Error(message);
}

/**
 * Map a JSON Schema fragment to the TypeScript expression that represents
 * the same value. Throws for unsupported constructs so the build fails
 * loudly when the backend extends the catalogue's schema vocabulary.
 * @param {any} schema
 * @returns {string}
 */
function mapType(schema) {
  // Union form. The catalogue uses this for nullable wrappers
  // (`anyOf: [<T>, {type: "null"}]`); supporting deeper unions is free.
  if (Array.isArray(schema.anyOf)) {
    return schema.anyOf.map(mapType).join(" | ");
  }
  switch (schema.type) {
    case "string":
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "null":
      return "null";
    default:
      throw new Error(
        `Unsupported JSON Schema fragment in error-catalogue.json: ${JSON.stringify(schema)}. ` +
          "Update scripts/generate-error-bindings.mjs to handle the new construct."
      );
  }
}

/**
 * Emit a TypeScript interface (or `Record<string, never>` for the empty
 * case) for one code's `data_schema`.
 * @param {string} name
 * @param {any} schema
 * @returns {string}
 */
function generateInterface(name, schema) {
  const required = new Set(schema.required ?? []);
  const props = Object.entries(schema.properties ?? {});

  if (props.length === 0) {
    return `export type ${name} = Record<string, never>;`;
  }

  const lines = props.map(([key, propSchema]) => {
    const optional = required.has(key) ? "" : "?";
    return `  ${key}${optional}: ${mapType(propSchema)};`;
  });
  return `export interface ${name} {\n${lines.join("\n")}\n}`;
}

async function generate() {
  const raw = await fs.readFile(SCHEMA_PATH, "utf-8");
  const catalogue = JSON.parse(raw);

  assert(
    catalogue && typeof catalogue === "object" && !Array.isArray(catalogue),
    "schema/error-catalogue.json root must be an object."
  );
  assert(
    catalogue.codes && typeof catalogue.codes === "object" && !Array.isArray(catalogue.codes),
    "schema/error-catalogue.json must contain a `codes` object."
  );

  // Sort codes alphabetically — the JSON's iteration order shouldn't drive
  // diff churn when the backend reorders entries.
  const codes = Object.keys(catalogue.codes).sort();
  assert(codes.length > 0, "schema/error-catalogue.json `codes` is empty.");

  const entries = codes.map((code) => {
    const entry = catalogue.codes[code];
    assert(
      entry && typeof entry === "object",
      `Catalogue entry "${code}" must be an object.`
    );
    assert(
      Number.isInteger(entry.http_status),
      `Catalogue entry "${code}" must have an integer \`http_status\` (got ${JSON.stringify(entry.http_status)}).`
    );
    assert(
      entry.data_schema && typeof entry.data_schema === "object",
      `Catalogue entry "${code}" must have a \`data_schema\` object.`
    );
    assert(
      typeof entry.data_schema.title === "string" && entry.data_schema.title.length > 0,
      `Catalogue entry "${code}" must have a non-empty \`data_schema.title\` (used as the TS interface name).`
    );

    const typeName = entry.data_schema.title;
    return {
      code,
      typeName,
      httpStatus: entry.http_status,
      body: generateInterface(typeName, entry.data_schema),
    };
  });

  const header = [
    "// AUTO-GENERATED — DO NOT EDIT.",
    "// Source: schema/error-catalogue.json",
    `// Catalogue version: ${catalogue.infrahub_catalogue_version}`,
    "// Regenerate with: pnpm generate:error-bindings",
  ].join("\n");

  const dataBlocks = entries.map((e) => e.body).join("\n\n");

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
    ...entries.map((e) => `  ${e.code}: ${e.httpStatus},`),
    "};",
  ].join("\n");

  const unionBlock = [
    "// Discriminated union over every catalogue code. Narrowing on `code`",
    "// gives full type-safety for `data` at the call site.",
    "export type CatalogueError =",
    ...entries.map(
      (e) => `  | { code: typeof ERROR_CODES.${e.code}; http_status: number; data: ${e.typeName} }`
    ),
    "  ;",
  ].join("\n");

  return `${[header, "", dataBlocks, "", errorCodesBlock, "", httpStatusBlock, "", unionBlock].join("\n")}\n`;
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

// Only execute when invoked directly (e.g. via `pnpm generate:error-bindings`).
// Importing this module — from a test, knip, or a programmatic caller — must
// not write to disk as a side effect.
const isDirectInvocation =
  process.argv[1] !== undefined &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectInvocation) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
