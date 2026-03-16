import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { LinkButton } from "@/shared/components/ui/button";
import { NODE_PATH_EXCLUDELIST } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

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
