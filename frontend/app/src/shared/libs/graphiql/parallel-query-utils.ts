import { type ArgumentNode, type FieldNode, Kind, parse, print, visit } from "graphql";

export interface ParsedQueryInfo {
  hasOffset: boolean;
  hasLimit: boolean;
  hasCount: boolean;
  rootFieldName: string | null;
  canParallelize: boolean;
}

/**
 * Parse a GraphQL query to detect if it uses offset/limit arguments
 */
export function analyzeQuery(query: string): ParsedQueryInfo {
  try {
    const ast = parse(query);
    let hasOffset = false;
    let hasLimit = false;
    let hasCount = false;
    let rootFieldName: string | null = null;

    visit(ast, {
      OperationDefinition: {
        enter(node) {
          // Only analyze query operations, not mutations or subscriptions
          if (node.operation !== "query") {
            return false; // Skip traversal for non-query operations
          }
          return;
        },
      },
      Field: {
        enter(node: FieldNode, _key, parent) {
          // Capture root field name (first level query field under query root)
          // Check if parent is SelectionSet and grandparent would be OperationDefinition
          if (!rootFieldName && node.selectionSet && Array.isArray(parent)) {
            rootFieldName = node.name.value;
          }

          // Check for count field in selection
          if (node.name.value === "count") {
            hasCount = true;
          }

          // Check for offset/limit arguments
          node.arguments?.forEach((arg: ArgumentNode) => {
            if (arg.name.value === "offset") hasOffset = true;
            if (arg.name.value === "limit") hasLimit = true;
          });
        },
      },
    });

    return {
      hasOffset,
      hasLimit,
      hasCount,
      rootFieldName,
      canParallelize: !hasOffset && !hasLimit && rootFieldName !== null,
    };
  } catch {
    return {
      hasOffset: false,
      hasLimit: false,
      hasCount: false,
      rootFieldName: null,
      canParallelize: false,
    };
  }
}

/**
 * Generate paginated queries with offset/limit
 */
export function generatePaginatedQueries(
  query: string,
  rootFieldName: string,
  totalCount: number,
  pageSize: number
): string[] {
  const totalPages = Math.ceil(totalCount / pageSize);
  const queries: string[] = [];

  for (let page = 0; page < totalPages; page++) {
    const offset = page * pageSize;
    const ast = parse(query);

    const paginatedAst = visit(ast, {
      Field: {
        enter(node: FieldNode) {
          if (node.name.value === rootFieldName) {
            const existingArgs = node.arguments || [];
            return {
              ...node,
              arguments: [
                ...existingArgs,
                {
                  kind: Kind.ARGUMENT,
                  name: { kind: Kind.NAME, value: "offset" },
                  value: { kind: Kind.INT, value: String(offset) },
                },
                {
                  kind: Kind.ARGUMENT,
                  name: { kind: Kind.NAME, value: "limit" },
                  value: { kind: Kind.INT, value: String(pageSize) },
                },
              ],
            };
          }
          return;
        },
      },
    });

    queries.push(print(paginatedAst));
  }

  return queries;
}

/**
 * Merge paginated results into a single response
 */
export function mergeResults(
  results: Array<{ data: Record<string, unknown> }>,
  rootFieldName: string,
  totalCount: number
): Record<string, unknown> {
  if (results.length === 0) return {};

  const mergedEdges: unknown[] = [];

  for (const result of results) {
    const fieldData = result.data?.[rootFieldName] as Record<string, unknown> | undefined;
    if (fieldData?.edges && Array.isArray(fieldData.edges)) {
      mergedEdges.push(...fieldData.edges);
    }
  }

  // Get the first result as template for structure
  const firstFieldData = results[0]?.data?.[rootFieldName] as Record<string, unknown> | undefined;

  // Build merged field data - only include count if it was requested in the original query
  const mergedFieldData: Record<string, unknown> = {
    ...firstFieldData,
    edges: mergedEdges,
  };

  // Only include count if the user requested it (present in first result)
  if (firstFieldData && "count" in firstFieldData) {
    mergedFieldData.count = totalCount;
  }

  // Return merged structure
  return {
    [rootFieldName]: mergedFieldData,
  };
}
