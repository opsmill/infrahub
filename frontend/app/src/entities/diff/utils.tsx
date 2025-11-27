import { Icon } from "@iconify-icon/react";

import { NODE_PATH_EXCLUDELIST } from "@/config/constants";
import { QSP } from "@/config/qsp";

import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { Badge } from "@/shared/components/ui/badge";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

function extractNodeId(path: string) {
  // Expect an ID immediately following "data/"; support optional leading slash
  const match = path?.match(/(?:^|\/)data\/([\w-]+)(?:\/|$)/);
  return match?.[1] ?? null;
}

function extractNodeProperty(path: string) {
  // Split and drop empty parts to support "/data/..." and "data/..."
  const parts = path?.split("/").filter(Boolean) ?? [];
  // Find "data" segment and drop "data/<id>"
  const dataIdx = parts.indexOf("data");
  const afterId = dataIdx !== -1 ? parts.slice(dataIdx + 2) : parts.slice(2);
  // Exclude specific path segments
  const nodePath = afterId.filter((item) => !NODE_PATH_EXCLUDELIST.includes(item));
  const label = nodePath.reduce((acc, item) => (acc ? `${acc} > ${item}` : item), "");
  return label;
}

export const displayValue = (value: any) => {
  if (typeof value === "boolean") {
    return `${value}`;
  }

  if (value === "NULL") {
    return "-";
  }

  if (value && typeof value === "object" && "__typename" in value && "id" in value) {
    return getNodeLabel(value);
  }

  return value?.display_label || value || "-";
};

const getValueTooltip = (value: any) => {
  if (!value?.kind) {
    return null;
  }

  return (
    <div className="flex items-center">
      Kind: <Badge>{value.kind}</Badge>
    </div>
  );
};

// Display the values
// (only new one for "added", only old ones for "deleted", and previous + new for "updated")
export const diffContent: { [key: string]: any } = {
  added: (property: any) => {
    const { value } = property;

    const { new: newValue } = value;

    const newMesage = getValueTooltip(newValue);

    return (
      <div className="flex">
        {newMesage ? (
          <Tooltip enabled content={newMesage}>
            <Badge variant="green-outline">{displayValue(newValue)}</Badge>
          </Tooltip>
        ) : (
          <Badge variant="green-outline">{displayValue(newValue)}</Badge>
        )}
      </div>
    );
  },
  removed: (property: any) => {
    const { value } = property;

    const { previous: previousValue } = value;

    const previousMessage = getValueTooltip(previousValue);

    return (
      <div className="flex">
        {previousMessage ? (
          <Tooltip enabled content={previousMessage}>
            <Badge variant="red-outline">{displayValue(previousValue)}</Badge>
          </Tooltip>
        ) : (
          <Badge variant="red-outline">{displayValue(previousValue)}</Badge>
        )}
      </div>
    );
  },
  updated: (property: any) => {
    const { value } = property;

    const { new: newValue, previous: previousValue } = value;

    const previousMessage = getValueTooltip(previousValue);
    const newMessage = getValueTooltip(newValue);

    return (
      <div className="flex items-center">
        <div className="flex items-center">
          {previousMessage ? (
            <Tooltip enabled content={previousMessage}>
              <Badge variant="blue-outline">{displayValue(previousValue)}</Badge>
            </Tooltip>
          ) : (
            <Badge variant="blue-outline">{displayValue(previousValue)}</Badge>
          )}
        </div>

        <div className="flex items-center">
          <Icon icon={"mdi:chevron-right"} className="mx-2" aria-hidden="true" />
        </div>

        <div className="flex">
          {newMessage ? (
            <Tooltip enabled content={newMessage}>
              <Badge variant="blue-outline">{displayValue(newValue)}</Badge>
            </Tooltip>
          ) : (
            <Badge variant="blue-outline">{displayValue(newValue)}</Badge>
          )}
        </div>
      </div>
    );
  },
  conflict: (property: any) => {
    const { value } = property;

    const { new: newValue, previous: previousValue } = value;

    const previousMessage = getValueTooltip(previousValue);

    const newMesage = getValueTooltip(newValue);

    return (
      <div className="flex items-center">
        <div className="flex items-center">
          {previousMessage ? (
            <Tooltip enabled content={previousMessage}>
              <Badge variant="blue-outline">{displayValue(previousValue)}</Badge>
            </Tooltip>
          ) : (
            <Badge variant="blue-outline">{displayValue(previousValue)}</Badge>
          )}
        </div>

        <div className="flex items-center">
          <Icon icon={"mdi:chevron-right"} className="mx-2" aria-hidden="true" />
        </div>

        <div className="flex">
          {newMesage ? (
            <Tooltip enabled content={newMesage}>
              <Badge variant="blue-outline">{displayValue(newValue)}</Badge>
            </Tooltip>
          ) : (
            <Badge variant="blue-outline">{displayValue(newValue)}</Badge>
          )}
        </div>
      </div>
    );
  },
};

export const getThreadLabel = (node?: any, currentBranch?: string, path?: string) => {
  // Get main object name
  const objectName = node?.display_label && currentBranch && node?.display_label[currentBranch];

  const nodeLabel = extractNodeProperty(path);

  if (objectName) {
    return `${objectName} > ${nodeLabel}`;
  }

  return nodeLabel;
};

// Get thread title from the thread or a defined label
export const getThreadTitle = (thread?: any, label?: string) => {
  const pathname = typeof window !== "undefined" ? window.location.pathname : "";

  if (thread?.object_path?.value) {
    // should match the id in "data/185afbed-0447-a991-33a0-c51c1d4e20ef/description" or "data/185afbed-0447-a991-33a0-c51c1d4e20ef"
    const nodeId = extractNodeId(thread.object_path.value);
    const nodeProperty = extractNodeProperty(thread.object_path.value);

    if (!nodeId) {
      return null;
    }

    return (
      <div className="flex items-center gap-2 text-sm">
        <Badge variant={"gray-outline"}>Object</Badge>

        <LinkButton
          to={{
            pathname,
            search: `?${QSP.PROPOSED_CHANGES_TAB}=data`,
            hash: `#${nodeId}`,
          }}
          className="flex items-center gap-2 px-1"
          variant={"ghost"}
        >
          <NodeLabel id={nodeId} />

          {nodeProperty && (
            <>
              <Icon icon={"mdi:chevron-right"} />
              {nodeProperty}
            </>
          )}
        </LinkButton>
      </div>
    );
  }

  if (thread?.artifact_id?.value) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <Badge variant={"gray-outline"}>Artifact</Badge>
        <NodeLabel id={thread?.artifact_id.value} />
      </div>
    );
  }

  const string = thread?.label?.value ?? thread?.display_label ?? label;

  if (!string) {
    return "";
  }

  if (string === "Conversation") {
    return (
      <div className="flex">
        <Badge variant={"gray-outline"}>{string}</Badge>
      </div>
    );
  }

  return (
    <div className="flex">
      <Badge variant={"green"}>{string}</Badge>
    </div>
  );
};

const badgeTypes: { [key: string]: string } = {
  added: "green",
  updated: "blue",
  removed: "red",
};

export const getBadgeType = (action?: string) => {
  if (!action) return;

  return badgeTypes[action];
};
