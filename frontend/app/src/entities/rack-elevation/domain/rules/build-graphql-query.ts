import type {
  RackElevationMapping,
  ValueSource,
} from "@/entities/rack-elevation/domain/model/mapping";
import type { Schema } from "@/entities/rack-elevation/domain/model/schema";
import { getTemplatePaths } from "@/entities/rack-elevation/domain/rules/resolve-path";

interface FieldTree {
  [field: string]: FieldTree;
}

const INDENT = "  ";

function addPath(tree: FieldTree, path: string[]) {
  let current = tree;
  for (const segment of path) {
    current[segment] ??= {};
    current = current[segment];
  }
}

function sourcePaths(source: ValueSource): string[][] {
  if (source.type === "path") return source.path.length > 0 ? [source.path] : [];
  if (source.type === "template") return getTemplatePaths(source.template);
  return [];
}

function renderNode(tree: FieldTree, kind: string, schema: Schema, depth: number): string[] {
  const pad = INDENT.repeat(depth);
  const lines = [`${pad}id`];
  const schemaKind = schema[kind];
  if (!schemaKind) return lines;

  for (const [field, children] of Object.entries(tree)) {
    if (schemaKind.attributes.some((attribute) => attribute.name === field)) {
      lines.push(`${pad}${field} { value }`);
      continue;
    }
    const relationship = schemaKind.relationships.find((candidate) => candidate.name === field);
    if (!relationship) continue;

    const displayAttribute = schema[relationship.peer]?.displayAttribute;
    const peerTree: FieldTree = displayAttribute
      ? { [displayAttribute]: {}, ...children }
      : children;
    if (relationship.cardinality === "one") {
      const body = renderNode(peerTree, relationship.peer, schema, depth + 2);
      lines.push(
        `${pad}${field} {`,
        `${pad}${INDENT}node {`,
        ...body,
        `${pad}${INDENT}}`,
        `${pad}}`
      );
    } else {
      const edgeBody = renderNode(peerTree, relationship.peer, schema, depth + 3);
      lines.push(
        `${pad}${field} {`,
        `${pad}${INDENT}edges {`,
        `${pad}${INDENT}${INDENT}node {`,
        ...edgeBody,
        `${pad}${INDENT}${INDENT}}`,
        `${pad}${INDENT}}`,
        `${pad}}`
      );
    }
  }
  return lines;
}

/** Builds the Infrahub GraphQL query that would load one rack and everything the mapping reads. */
export function buildGraphqlQuery(mapping: RackElevationMapping, schema: Schema): string {
  const tree: FieldTree = {};
  for (const path of [...sourcePaths(mapping.rack.label), ...sourcePaths(mapping.rack.height)]) {
    addPath(tree, path);
  }
  for (const source of mapping.itemSources) {
    if (!source.relationship) continue;
    addPath(tree, [source.relationship]);
    for (const value of Object.values(source.fields)) {
      for (const path of sourcePaths(value)) addPath(tree, [source.relationship, ...path]);
    }
  }

  const body = renderNode(tree, mapping.rackKind, schema, 4);
  return [
    "query RackElevation($rack_id: ID!) {",
    `${INDENT}${mapping.rackKind}(ids: [$rack_id]) {`,
    `${INDENT}${INDENT}edges {`,
    `${INDENT}${INDENT}${INDENT}node {`,
    ...body,
    `${INDENT}${INDENT}${INDENT}}`,
    `${INDENT}${INDENT}}`,
    `${INDENT}}`,
    "}",
  ].join("\n");
}
