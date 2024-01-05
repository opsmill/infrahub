import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import Accordion from "../../components/display/accordion";
import { Badge } from "../../components/display/badge";
import { DateDisplay } from "../../components/display/date-display";
import { QSP } from "../../config/qsp";
import { classNames } from "../../utils/common";
import { diffPeerContent } from "../../utils/diff";
import { constructPath } from "../../utils/fetch";
import { getObjectDetailsUrl } from "../../utils/objects";
import {
  getNodeClassName,
  tDataDiffNodePeerChange,
  tDataDiffNodePeerValue,
  tDataDiffNodeProperty,
} from "./data-diff-node";
import { DataDiffProperty } from "./data-diff-property";
import { DataDiffConflictInfo } from "./diff-conflict-info";
import { DiffPill } from "./diff-pill";
import { DataDiffThread } from "./diff-thread";

export type tDataDiffNodePeerProps = {
  peerChanges: tDataDiffNodePeerChange;
  peerProperties?: { [key: string]: tDataDiffNodeProperty };
  name?: string;
};

const getPeerRedirection = (peer: tDataDiffNodePeerValue, branch: string, navigate: Function) => {
  if (!peer.id || !peer.kind) {
    return;
  }

  const objectUrl = getObjectDetailsUrl(peer.id, peer.kind);

  const url = branch ? constructPath(`${objectUrl}?branch=${branch}`) : constructPath(objectUrl);

  return () => {
    navigate(url);
  };
};

export const DataDiffPeer = (props: tDataDiffNodePeerProps) => {
  const {
    peerChanges,
    peerProperties, // For relationship one
    name,
  } = props;

  const { branchname } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const navigate = useNavigate();

  // Relationship mayny: action, changed_at, branches, branches, peer, properties, summary
  // Relationship one: changes > branch, new, previous
  const {
    path,
    action,
    changed_at,
    branches,
    peer: peerChange,
    properties, // For relationship many
    summary,
    branch: peerBranch,
    new: newPeer,
    previous: previousPeer,
  } = peerChanges;

  const renderDiffDisplay = (peer: tDataDiffNodePeerValue, branch: any) => {
    if (peer?.kind && peer?.id) {
      const onClick = getPeerRedirection(peer, branch, navigate);

      return diffPeerContent(peer, action[branch], onClick, branch);
    }

    return diffPeerContent(peer, undefined, undefined, branch);
  };

  const renderTitleDisplay = () => {
    if (branches?.length) {
      return branches.map((branch: string, index: number) => {
        return (
          <div className="group relative p-1 pr-0 flex flex-col lg:flex-row last:mr-0" key={index}>
            <div className="flex flex-1 items-center">
              {peerChange?.kind && <Badge>{peerChange?.kind}</Badge>}

              <span className="mr-2 font-semibold">{peerChange?.display_label}</span>
            </div>

            {/* Do not display comment button if we are on the branch details view */}
            {!branchname && <DataDiffThread path={path} />}

            <div className="flex flex-1 items-center">
              <span className="font-semibold">{renderDiffDisplay(peerChange, branch)}</span>
            </div>

            <div className="flex flex-1 items-center lg:justify-end mt-2 lg:mt-0">
              <DiffPill {...summary} />

              <div className="flex w-[200px] justify-end">
                {changed_at && <DateDisplay date={changed_at} hideDefault />}
              </div>
            </div>

            {!branchname && <DataDiffConflictInfo path={path} />}
          </div>
        );
      });
    }

    if (peerBranch) {
      return (
        <div className="group p-1 pr-0 flex flex-col lg:flex-row last:mr-0">
          <div className="flex flex-1 items-center relative">
            <div className="flex flex-1 items-center">
              <div className="flex items-center">
                {newPeer?.kind && <Badge>{newPeer?.kind}</Badge>}

                <span className="mr-2 font-semibold">{name}</span>
              </div>

              {/* Do not display comment button if we are on the branch details view */}
              {!branchname && <DataDiffThread path={path} />}
            </div>

            <div className="flex flex-1 items-center">
              <span className="font-semibold">
                {renderDiffDisplay({ new: newPeer, previous: previousPeer }, peerBranch)}
              </span>
            </div>
          </div>

          <div className="flex flex-1 lg:justify-end items-center mt-2 lg:mt-0">
            <DiffPill {...summary} />

            <div className="flex w-[200px] justify-end">
              {changed_at && <DateDisplay date={changed_at} hideDefault />}
            </div>
          </div>

          {!branchname && <DataDiffConflictInfo path={path} />}
        </div>
      );
    }

    return null;
  };

  const propertiesChanges: ReactNode[] = Object.values(properties || peerProperties || {}).map(
    (property, index: number) =>
      property.changes?.map((change: any, index2: number) => (
        <DataDiffProperty key={`${index}-${index2}`} property={change} path={property.path} />
      ))
  );

  // If there are some properties, then display the accordion
  if (propertiesChanges?.length) {
    return (
      <div
        className={classNames(
          "mb-1 rounded-md last:mb-0",
          getNodeClassName([], peerChanges.branch, branchOnly)
        )}>
        <Accordion title={renderTitleDisplay()}>{propertiesChanges}</Accordion>
      </div>
    );
  }

  return (
    <div
      className={classNames(
        "flex flex-col rounded-md mb-1 last:mb-0",
        getNodeClassName(branches, peerBranch, branchOnly)
      )}>
      <div className="flex">
        {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
        <ChevronDownIcon className="w-4 h-4 mr-2 text-transparent" aria-hidden="true" />
        <div className="flex-1">{renderTitleDisplay()}</div>
      </div>
    </div>
  );
};
