import Accordion from "@/components/display/accordion";

import { Pill } from "@/components/display/pill";
import { Tooltip } from "@/components/ui/tooltip";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { classNames } from "@/utils/common";
import { ChatBubbleLeftRightIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { DataDiffElement } from "./data-diff-element";
import { DataDiffConflictInfo } from "./diff-conflict-info";
import { DataDiffThread } from "./diff-thread";
import { capitalizeFirstLetter } from "@/utils/string";
import { Badge } from "@/components/ui/badge";
import { getBadgeIcon, getBadgeType } from "@/utils/diff";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/components/display/badge-circle";
import { CopyToClipboard } from "@/components/buttons/copy-to-clipboard";

export type tConflictChange = {
  id?: string;
  kind?: string;
  display_label?: string;
};

export type tDataDiffNodePropertyValue = {
  new: string | tConflictChange;
  previous: string | tConflictChange;
};

export type tDataDiffNodePropertyChange = {
  path: string;
  type?: string;
  changed_at?: number;
  action: string;
  value: tDataDiffNodePropertyValue;
  branch: string;
};

export type tDataDiffNodeProperty = {
  path: string;
  changes: tDataDiffNodePropertyChange[];
};

export type tDataDiffNodePeerValue = {
  // From relationship one
  new?: tDataDiffNodePeerValue;
  previous?: tDataDiffNodePeerValue;
  // From relationship many
  id?: string;
  kind?: string;
  display_label?: string;
};

export type tDataDiffNodePeerChange = {
  changed_at?: number;
  action: string;
  branches: string[];
  path: string;
  peer: tDataDiffNodePeerValue;
  properties: { [key: string]: tDataDiffNodeProperty };
  new?: tDataDiffNodePeerValue;
  previous?: tDataDiffNodePeerValue;
  branch?: string;
  changes: tDataDiffNodePeerChange[];
};

export type tDataDiffNodePeer = {
  path: string;
  changes: tDataDiffNodePropertyChange[];
};

export type tDataDiffNodeValueChange = {
  action: string;
  branch: string;
  changed_at: string;
  type: string;
  value: tDataDiffNodePropertyValue;
};

export type tDataDiffNodeValue = {
  path: string;
  changes: tDataDiffNodeValueChange[];
};

export type tDataDiffNodeChange = {
  value: tDataDiffNodeValue;
  branch?: string;
  changed_at?: number;
  identifier?: string;
  action: string;
  properties: { [key: string]: tDataDiffNodeProperty };
  peer?: tDataDiffNodePeerChange;
  peers?: tDataDiffNodePeerChange[];
  summary?: tDataDiffNodeSummary;
};

export type tDataDiffNodeElement = {
  type?: string;
  name: string;
  path: string;
  change: tDataDiffNodeChange;
};

export type tDataDiffNodeSummary = {
  added: number;
  updated: number;
  removed: number;
};

export type tDataDiffNodeDisplayLabel = {
  branch: string;
  display_label: string;
};

export type tDataDiffNodeAction = {
  branch: string;
  action: string;
};

export type tDataDiffNode = {
  display_label: { [key: string]: any };
  action: { [key: string]: any };
  id: string;
  kind: string;
  changed_at?: number;
  summary: tDataDiffNodeSummary;
  elements: Map<string, tDataDiffNodeElement>;
  path: string;
};

export type tDataDiffNodeProps = {
  node: tDataDiffNode;
  commentsCount?: number;
  branch?: string;
};

// Branch from QSP = branchName
// Multiple branches = branches array
// Related branch for the node update = branch
export const getNodeClassName = (
  branches: string[],
  branch: string | undefined,
  branchOnly?: string | null | undefined
) => {
  // Do not display a color if the node is related to mulitple branches or if we are on the branch details diff
  if (branches?.length > 1 || branchOnly === "true" || !branchOnly) {
    return "bg-custom-white";
  }

  if (branches?.length === 1) {
    return branches[0] === "main" ? "bg-custom-blue-10" : "bg-green-200";
  }

  return branch === "main" ? "bg-custom-blue-10" : "bg-green-200";
};

export const DataDiffNode = (props: tDataDiffNodeProps) => {
  const { branchName } = useParams();
  const [proposedChangesDetails] = useAtom(proposedChangedState);

  // Branch from props is used to filter the changes to a specific branch
  const { node, branch, commentsCount } = props;

  const { display_label: nodeDisplayLabels, action: nodeActions, kind, elements, path } = node;

  // Get all the related branches for this node
  const branches = Object.keys(nodeActions);

  const currentBranch =
    branch ?? branchName ?? proposedChangesDetails?.source_branch?.value ?? "main";

  const action = nodeActions[currentBranch] ?? nodeActions?.main;

  const display_label = nodeDisplayLabels[currentBranch] ?? nodeDisplayLabels?.main;

  const renderTitle = () => (
    <div className={"px-2 relative flex flex-col items-center lg:flex-row group"}>
      <div className="flex flex-1 items-center group">
        <Badge className="mr-2" variant={getBadgeType(action)}>
          <div className="mr-1 flex items-center">{getBadgeIcon(action)}</div>

          {capitalizeFirstLetter(action)}
        </Badge>

        <Badge className="mr-2" variant={"white"}>
          {kind}
        </Badge>

        <BadgeCircle type={CIRCLE_BADGE_TYPES.GHOST}>
          <span className="mr-2">{display_label}</span>
          <CopyToClipboard text={display_label} />
        </BadgeCircle>

        {/* Do not display comment button if we are on the branch details view */}
        {!branchName && <DataDiffThread path={path} />}
      </div>

      {commentsCount && (
        <div className="flex items-center" data-cy="comments-count" data-testid="comments-count">
          <Tooltip enabled content={"Total number of comments"}>
            <div className="flex">
              <ChatBubbleLeftRightIcon className="w-4 h-4 mr-2" />
              <Pill className="mr-2">{JSON.stringify(commentsCount)}</Pill>
            </div>
          </Tooltip>
        </div>
      )}

      {!branchName && <DataDiffConflictInfo path={path} />}
    </div>
  );

  return (
    <div
      className={classNames(
        "rounded-lg shadow p-2 m-4",
        getNodeClassName(branches, currentBranch)
      )}>
      <Accordion title={renderTitle()} className="bg-gray-100 rounded-md border">
        <div className="bg-custom-white">
          {Object.values(elements).map((element: tDataDiffNodeElement, index: number) => (
            <DataDiffElement key={index} element={element} />
          ))}
        </div>
      </Accordion>
    </div>
  );
};
