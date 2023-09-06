import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { BADGE_TYPES, Badge } from "../components/badge";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "../components/badge-circle";
import { Tooltip } from "../components/tooltip";
import { NODE_PATH_EXCLUDELIST } from "../config/constants";
import {
  tDataDiffNode,
  tDataDiffNodePeerValue,
  tDataDiffNodePropertyChange,
} from "../screens/diff/data-diff-node";

export const displayValue = (value: any) => {
  if (typeof value === "boolean") {
    return `${value}`;
  }

  if (value === "NULL") {
    return "-";
  }

  return value || "-";
};

// Display the values
// (only new one for "added", only old ones for "deleted", and previous + new for "updated")
export const diffContent: { [key: string]: any } = {
  added: (property: tDataDiffNodePropertyChange) => {
    const { value } = property;

    const { new: newValue } = value;

    return (
      <div className="flex">
        <Badge type={BADGE_TYPES.VALIDATE}>{displayValue(newValue)}</Badge>
      </div>
    );
  },
  removed: (property: tDataDiffNodePropertyChange) => {
    const { value } = property;

    const { previous: previousValue } = value;

    return (
      <div className="flex">
        <Badge type={BADGE_TYPES.CANCEL}>{displayValue(previousValue)}</Badge>
      </div>
    );
  },
  updated: (property: tDataDiffNodePropertyChange) => {
    const { value } = property;

    const { new: newValue, previous: previousValue } = value;

    return (
      <div className="flex items-center">
        <div className="flex">
          <Tooltip message="Previous value">
            <Badge type={BADGE_TYPES.CANCEL}>{displayValue(previousValue)}</Badge>
          </Tooltip>
        </div>

        <div>
          <ChevronRightIcon className="h-5 w-5 mr-2" aria-hidden="true" />
        </div>

        <div className="flex">
          <Tooltip message="New value">
            <Badge type={BADGE_TYPES.VALIDATE}>{displayValue(newValue)}</Badge>
          </Tooltip>
        </div>
      </div>
    );
  },
};

// Display the values
// (only new one for "added", only old ones for "deleted", and previous + new for "updated")
export const diffPeerContent = (
  peer: tDataDiffNodePeerValue,
  action?: string,
  onClick?: Function,
  branch: string = "main"
) => {
  const { new: newPeer, previous: previousPeer, kind, display_label } = peer;

  // From relationship one
  if (newPeer && !previousPeer) {
    return (
      <div className="flex">
        <Badge type={BADGE_TYPES.VALIDATE}>{displayValue(newPeer?.display_label)}</Badge>
      </div>
    );
  }

  // From relationship one
  if (!newPeer && previousPeer) {
    return (
      <div className="flex">
        <Badge type={BADGE_TYPES.CANCEL}>{displayValue(previousPeer?.display_label)}</Badge>
      </div>
    );
  }

  // From relationship one
  if (newPeer && previousPeer) {
    return (
      <div className="flex items-center">
        <div className="flex">
          <Tooltip message="Previous value">
            <Badge type={BADGE_TYPES.CANCEL}>{displayValue(previousPeer?.display_label)}</Badge>
          </Tooltip>
        </div>

        <div>
          <ChevronRightIcon className="h-5 w-5 mr-2" aria-hidden="true" />
        </div>

        <div className="flex">
          <Tooltip message="New value">
            <Badge type={BADGE_TYPES.VALIDATE}>{displayValue(newPeer?.display_label)}</Badge>
          </Tooltip>
        </div>
      </div>
    );
  }

  // From relationship many
  if (kind && display_label && onClick) {
    return (
      <div className="flex">
        <Tooltip message={`Link to ${display_label} ${branch && `(${branch})`}`}>
          <Badge
            type={action === "added" ? BADGE_TYPES.VALIDATE : BADGE_TYPES.CANCEL}
            onClick={onClick}>
            {displayValue(display_label)}
          </Badge>
        </Tooltip>
      </div>
    );
  }
};

export const getThreadLabel = (node?: tDataDiffNode, currentBranch?: string, path?: string) => {
  // Get main object name
  const objectName = node?.display_label && currentBranch && node?.display_label[currentBranch];

  const nodePath = path
    ?.split("/")
    // Get the path without the beginning "data/xxxx-xxxx-xxxx-xxxx"
    .slice(2)
    // Do not include some values from the path
    .filter((item) => !NODE_PATH_EXCLUDELIST.includes(item));

  // Construct path like "item1 > item2 > item3"
  const nodeLabel = nodePath?.reduce((acc, item) => (acc ? `${acc} > ${item}` : item), "").trim();

  if (objectName) {
    return `${objectName} > ${nodeLabel}`;
  }

  return nodeLabel;
};

// Get thread title from the thread or a defined label
export const getThreadTitle = (thread?: any, label?: string) => {
  const string = thread?.label?.value ?? thread?.display_label ?? label;

  if (!string) {
    return "";
  }

  return (
    <div className="flex mb-2">
      {string && (
        <BadgeCircle type={string === "Conversation" ? null : CIRCLE_BADGE_TYPES.VALIDATE}>
          {string}
        </BadgeCircle>
      )}
    </div>
  );
};
