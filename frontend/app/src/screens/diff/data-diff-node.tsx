import Accordion from "@/components/display/accordion";

import { Tooltip } from "@/components/ui/tooltip";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { classNames } from "@/utils/common";
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
import { Icon } from "@iconify-icon/react";

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
  identifier?: string;
  action: string;
  properties: { [key: string]: tDataDiffNodeProperty };
  peer?: tDataDiffNodePeerChange;
  peers?: tDataDiffNodePeerChange[];
};

export type tDataDiffNodeElement = {
  type?: string;
  name: string;
  path: string;
  change: tDataDiffNodeChange;
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
  elements: Map<string, tDataDiffNodeElement>;
  path: string;
};

export type tDataDiffNodeProps = {
  node: tDataDiffNode;
  commentsCount?: number;
  branch?: string;
};

export const DataDiffNode = (props: tDataDiffNodeProps) => {
  const { branchName } = useParams();
  const [proposedChangesDetails] = useAtom(proposedChangedState);

  // Branch from props is used to filter the changes to a specific branch
  const { node, branch, commentsCount } = props;

  const { display_label: nodeDisplayLabels, action: nodeActions, kind, elements, path } = node;

  const currentBranch =
    branch ?? branchName ?? proposedChangesDetails?.source_branch?.value ?? "main";

  const action = nodeActions[currentBranch] ?? nodeActions?.main;

  const display_label = nodeDisplayLabels[currentBranch] ?? nodeDisplayLabels?.main;

  const renderTitle = () => (
    <div className={"h-7 px-2 relative flex flex-col items-center lg:flex-row group"}>
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
            <div>
              <Badge variant={"dark-gray"} className="rounded-full mr-2">
                <Icon icon="mdi:message-fast-outline" className="mr-1" />
                {commentsCount}
              </Badge>
            </div>
          </Tooltip>
        </div>
      )}

      {!branchName && <DataDiffConflictInfo path={path} />}
    </div>
  );

  return (
    <div className={classNames("bg-custom-white rounded-lg shadow p-2 m-4")}>
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
