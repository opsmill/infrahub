import type { ValueSource } from "@/entities/rack-elevation/domain/model/mapping";
import type {
  AttributeValue,
  GraphNode,
  NodeStore,
  Schema,
} from "@/entities/rack-elevation/domain/model/schema";

export interface ResolvedValue {
  value: AttributeValue;
  origin: { nodeId: string; attribute: string } | null;
}

const EMPTY: ResolvedValue = { value: null, origin: null };

const TEMPLATE_TOKEN = /\{([a-z0-9_.]+)\}/gi;

export function getDisplayLabel(node: GraphNode, schema: Schema): string {
  const attribute = schema[node.kind]?.displayAttribute;
  const value = attribute ? node.attributes[attribute] : null;
  return value === null || value === undefined ? node.id : String(value);
}

export function resolvePath(
  path: string[],
  node: GraphNode,
  store: NodeStore,
  schema: Schema
): ResolvedValue {
  let current: GraphNode | undefined = node;

  for (const [index, segment] of path.entries()) {
    if (!current) return EMPTY;
    const isLast = index === path.length - 1;
    const schemaKind = schema[current.kind];

    if (schemaKind?.attributes.some((attribute) => attribute.name === segment)) {
      if (!isLast) return EMPTY;
      return {
        value: current.attributes[segment] ?? null,
        origin: { nodeId: current.id, attribute: segment },
      };
    }

    const peerId: string | string[] | null | undefined = current.relationships[segment];
    if (typeof peerId !== "string") return EMPTY;
    current = store[peerId];
    if (isLast) return { value: current ? getDisplayLabel(current, schema) : null, origin: null };
  }

  return EMPTY;
}

export function renderTemplate(
  template: string,
  node: GraphNode,
  store: NodeStore,
  schema: Schema
): string {
  return template
    .replace(TEMPLATE_TOKEN, (_, token: string) => {
      const { value } = resolvePath(token.split("."), node, store, schema);
      return value === null ? "" : String(value);
    })
    .trim();
}

export function getTemplatePaths(template: string): string[][] {
  return [...template.matchAll(TEMPLATE_TOKEN)].flatMap((match) =>
    match[1] ? [match[1].split(".")] : []
  );
}

export function resolveValueSource(
  source: ValueSource,
  node: GraphNode,
  store: NodeStore,
  schema: Schema
): ResolvedValue {
  if (source.type === "constant") return { value: source.value, origin: null };
  if (source.type === "template") {
    return { value: renderTemplate(source.template, node, store, schema), origin: null };
  }
  if (source.path.length === 0) return EMPTY;
  return resolvePath(source.path, node, store, schema);
}

export function resolveCollection(
  relationship: string,
  node: GraphNode,
  store: NodeStore
): GraphNode[] {
  const peerIds = node.relationships[relationship];
  if (!Array.isArray(peerIds)) return [];
  return peerIds.flatMap((peerId) => (store[peerId] ? [store[peerId]] : []));
}
