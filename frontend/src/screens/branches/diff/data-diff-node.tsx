import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import Accordion from "../../../components/accordion";
import { BADGE_TYPES, Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { QSP } from "../../../config/qsp";
import { proposedChangedState } from "../../../state/atoms/proposedChanges.atom";
import { classNames } from "../../../utils/common";
import { DataDiffElement } from "./data-diff-element";
import { DiffPill } from "./diff-pill";

export type tDataDiffNodePropertyValue = {
  new: string;
  previous: string;
};

export type tDataDiffNodePeerData = {
  id: string;
  kind: string;
  display_label?: string;
};

export type tDataDiffNodePropertyChange = {
  type?: string;
  changed_at?: number;
  action: string;
  value: tDataDiffNodePropertyValue;
  branch: string;
};

export type tDataDiffNodePeerChange = {
  changed_at?: number;
  action: string;
  branches: string[];
  path: string;
  peer: tDataDiffNodePeerData;
  properties: tDataDiffNodeProperty;
  new?: tDataDiffNodePeerData;
  previous?: tDataDiffNodePeerData;
  summary?: tDataDiffNodeSummary;
  branch?: string;
  changes: tDataDiffNodePeerData[];
};

export type tDataDiffNodeProperty = {
  path: string;
  changes: tDataDiffNodePropertyChange[];
};

export type tDataDiffNodePeer = {
  // From relationship one
  new?: tDataDiffNodePeerData;
  previous?: tDataDiffNodePeerData;
  // From relationship many
  id?: string;
  kind?: string;
  display_label?: string;
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
  properties?: tDataDiffNodeProperty[];
  peer?: tDataDiffNodePeer;
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
};

export type tDataDiffNodeProps = {
  node: tDataDiffNode;
  branch?: string;
};

const badgeTypes: { [key: string]: BADGE_TYPES } = {
  added: BADGE_TYPES.VALIDATE,
  updated: BADGE_TYPES.WARNING,
  removed: BADGE_TYPES.CANCEL,
};

export const getBadgeType = (action?: string) => {
  if (!action) return null;

  return badgeTypes[action];
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
  if (branches.length > 1 || branchOnly === "true") {
    return "bg-custom-white";
  }

  return branch === "main" ? "bg-custom-blue-10" : "bg-green-200";
};

export const DataDiffNode = (props: tDataDiffNodeProps) => {
  const { branchname } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [proposedChangesDetails] = useAtom(proposedChangedState);

  // Branch from props is used to filter the changes to a specific branch
  const { node, branch } = props;

  const {
    display_label: nodeDisplayLabels,
    action: nodeActions,
    kind,
    changed_at,
    summary,
    elements,
  } = node;

  // Get all the related branches for this node
  const branches = Object.keys(nodeActions);

  const currentBranch =
    branch ?? branchname ?? proposedChangesDetails?.source_branch?.value ?? "main";

  const action = nodeActions[currentBranch] ?? nodeActions?.main;

  const display_label = nodeDisplayLabels[currentBranch] ?? nodeDisplayLabels?.main;

  const renderTitle = () => (
    <div className="p-1 pr-0 flex flex-1">
      <div className="flex flex-1">
        <Badge className="mr-2" type={getBadgeType(action)}>
          {action?.toUpperCase()}
        </Badge>

        <Badge className="mr-2">{kind}</Badge>

        <span className="mr-2">{display_label}</span>
      </div>

      <DiffPill {...summary} />

      <div className="w-[380px] flex justify-end">
        {changed_at && <DateDisplay date={changed_at} hideDefault />}
      </div>
    </div>
  );

  return (
    <div
      className={classNames(
        "rounded-lg shadow p-2 m-4 bg-custom-white",
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
