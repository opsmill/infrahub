import { Button } from "@infrahub/ui";

import type { AttributeValue } from "@/entities/rack-elevation/domain/model/schema";
import { getDisplayLabel } from "@/entities/rack-elevation/domain/rules/resolve-path";
import { Section } from "@/entities/rack-elevation/ui/object-details";
import { useRackElevationStore } from "@/entities/rack-elevation/ui/rack-elevation-store";

function formatValue(value: AttributeValue) {
  return value === null ? "empty" : String(value);
}

export function ChangesPanel({ onOpenNode }: { onOpenNode: (nodeId: string) => void }) {
  const { changes, nodes, schema, discardChanges } = useRackElevationStore();

  return (
    <Section title={`Changes to objects (${changes.length})`}>
      {changes.length === 0 ? (
        <p className="text-foreground-muted text-xs">
          Moving, mounting or editing an object in the rack changes the object itself. The changes
          appear here.
        </p>
      ) : (
        <>
          <ul className="flex flex-col gap-1 text-xs">
            {changes.map((change) => {
              const node = nodes[change.nodeId];
              if (!node) return null;
              return (
                <li key={`${change.nodeId}.${change.attribute}`}>
                  <button
                    type="button"
                    onClick={() => onOpenNode(change.nodeId)}
                    className="w-full rounded-md px-1 py-0.5 text-left hover:bg-content-strong"
                  >
                    <span className="font-medium">{getDisplayLabel(node, schema)}</span>
                    <span className="text-foreground-muted">
                      {" "}
                      {node.kind}.{change.attribute}
                    </span>
                    <span className="block tabular-nums">
                      <span className="text-diff-removed line-through">
                        {formatValue(change.before)}
                      </span>
                      {" → "}
                      <span className="text-diff-added">{formatValue(change.after)}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <div>
            <Button size="xs" variant="outline" onPress={discardChanges}>
              Discard all changes
            </Button>
          </div>
        </>
      )}
    </Section>
  );
}
