import { ChatBubbleLeftRightIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import Accordion from "../../components/display/accordion";
import { Badge } from "../../components/display/badge";
import { DateDisplay } from "../../components/display/date-display";
import { Pill } from "../../components/display/pill";
import { Tooltip } from "../../components/utils/tooltip";
import { QSP } from "../../config/qsp";
import { proposedChangedState } from "../../state/atoms/proposedChanges.atom";
import { classNames } from "../../utils/common";
import { getBadgeType } from "../../utils/diff";
import { DataDiffElement } from "./data-diff-element";
import { DataDiffConflictInfo } from "./diff-conflict-info";
import { DiffPill } from "./diff-pill";
import { DataDiffThread } from "./diff-thread";

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
  summary?: tDataDiffNodeSummary;
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

// Branch from QSP = branchname
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
  const { branchname } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [proposedChangesDetails] = useAtom(proposedChangedState);

  // Branch from props is used to filter the changes to a specific branch
  const { node, branch, commentsCount } = props;

  const {
    display_label: nodeDisplayLabels,
    action: nodeActions,
    kind,
    changed_at,
    summary,
    elements,
    path,
  } = node;

  // Get all the related branches for this node
  const branches = Object.keys(nodeActions);

  const currentBranch =
    branch ?? branchname ?? proposedChangesDetails?.source_branch?.value ?? "main";

  const action = nodeActions[currentBranch] ?? nodeActions?.main;

  const display_label = nodeDisplayLabels[currentBranch] ?? nodeDisplayLabels?.main;

  const renderTitle = () => (
    <div className={"p-1 pr-0 relative flex flex-col items-center lg:flex-row group"}>
      <div className="flex flex-1 items-center group">
        <Badge className="mr-2" type={getBadgeType(action)}>
          {action?.toUpperCase()}
        </Badge>

        <Badge className="mr-2">{kind}</Badge>

        <span className="mr-2">{display_label}</span>

        {/* Do not display comment button if we are on the branch details view */}
        {!branchname && <DataDiffThread path={path} />}
      </div>

      {commentsCount && (
        <div className="flex items-center" data-cy="comments-count" data-testid="comments-count">
          <Tooltip message={"Total number of comments"}>
            <ChatBubbleLeftRightIcon className="w-4 h-4 mr-2" />
            <Pill className="mr-2">{JSON.stringify(commentsCount)}</Pill>
          </Tooltip>
        </div>
      )}

      <div className="flex items-center mt-2 lg:mt-0">
        <DiffPill {...summary} />

        <div className="flex lg:w-[200px]">
          {changed_at && <DateDisplay date={changed_at} hideDefault />}
        </div>
      </div>

      {!branchname && <DataDiffConflictInfo path={path} />}
    </div>
  );

  return (
    <div
      className={classNames(
        "rounded-lg shadow p-2 m-4",
        getNodeClassName(branches, currentBranch, branchOnly)
      )}>
      <Accordion title={renderTitle()}>
        <div className="">
          {Object.values(elements).map((element: tDataDiffNodeElement, index: number) => (
            <DataDiffElement key={index} element={element} />
          ))}
        </div>
      </Accordion>
    </div>
  );
};
