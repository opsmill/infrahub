import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/components/display/badge-circle";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { NODE_PATH_EXCLUDELIST } from "@/config/constants";
import {
  tDataDiffNode,
  tDataDiffNodePeerValue,
  tDataDiffNodePropertyChange,
} from "@/screens/diff/data-diff-node";
import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";

export const displayValue = (value: any) => {
  if (typeof value === "boolean") {
    return `${value}`;
  }

  if (value === "NULL") {
    return "-";
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
  added: (property: tDataDiffNodePropertyChange) => {
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
  removed: (property: tDataDiffNodePropertyChange) => {
    const { value } = property;

    const { previous: previousValue } = value;

    const previousMesage = getValueTooltip(previousValue);

    return (
      <div className="flex">
        {previousMesage ? (
          <Tooltip enabled content={previousMesage}>
            <Badge variant="red-outline">{displayValue(previousValue)}</Badge>
          </Tooltip>
        ) : (
          <Badge variant="red-outline">{displayValue(previousValue)}</Badge>
        )}
      </div>
    );
  },
  updated: (property: tDataDiffNodePropertyChange) => {
    const { value } = property;

    const { new: newValue, previous: previousValue } = value;

    const previousMesage = getValueTooltip(previousValue);

    const newMesage = getValueTooltip(newValue);

    return (
      <div className="flex items-center">
        <div className="flex items-center">
          {previousMesage ? (
            <Tooltip enabled content={previousMesage}>
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
  conflict: (property: tDataDiffNodePropertyChange) => {
    const { value } = property;

    const { new: newValue, previous: previousValue } = value;

    const previousMesage = getValueTooltip(previousValue);

    const newMesage = getValueTooltip(newValue);

    return (
      <div className="flex items-center">
        <div className="flex items-center">
          {previousMesage ? (
            <Tooltip enabled content={previousMesage}>
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
        <Badge>{displayValue(newPeer?.display_label)}</Badge>
      </div>
    );
  }

  // From relationship one
  if (!newPeer && previousPeer) {
    return (
      <div className="flex">
        <Badge>{displayValue(previousPeer?.display_label)}</Badge>
      </div>
    );
  }

  // From relationship one
  if (newPeer && previousPeer) {
    return (
      <div className="flex items-center">
        <div className="flex">
          <Tooltip enabled content="Previous value">
            <Badge>{displayValue(previousPeer?.display_label)}</Badge>
          </Tooltip>
        </div>

        <div>
          <ChevronRightIcon className="w-4 h-4 mr-2" aria-hidden="true" />
        </div>

        <div className="flex">
          <Tooltip enabled content="New value">
            <Badge>{displayValue(newPeer?.display_label)}</Badge>
          </Tooltip>
        </div>
      </div>
    );
  }

  // From relationship many
  if (kind && display_label && onClick) {
    return (
      <div className="flex">
        <Tooltip enabled content={`Link to ${display_label} ${branch && `(${branch})`}`}>
          <Badge variant={action === "added" ? "green-outline" : "red-outline"} onClick={onClick}>
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

const badgeTypes: { [key: string]: string } = {
  added: "green",
  updated: "blue",
  removed: "red",
};

export const getBadgeType = (action?: string) => {
  if (!action) return undefined;

  return badgeTypes[action];
};

const badgeIcons: { [key: string]: string } = {
  added: "mdi:plus-circle-outline",
  updated: "mdi:circle-arrows",
  removed: "mdi:minus-circle-outline",
};

export const getBadgeIcon = (action?: string) => {
  if (!action) return undefined;

  return <Icon icon={badgeIcons[action]} />;
};
