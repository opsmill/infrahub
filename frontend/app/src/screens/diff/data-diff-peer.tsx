import Accordion from "@/components/display/accordion";
import { Badge } from "@/components/display/badge";
import { classNames } from "@/utils/common";
import { diffPeerContent } from "@/utils/diff";
import { constructPath } from "@/utils/fetch";
import { getObjectDetailsUrl } from "@/utils/objects";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import React, { ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  tDataDiffNodePeerChange,
  tDataDiffNodePeerValue,
  tDataDiffNodeProperty,
} from "./data-diff-node";
import { DataDiffProperty } from "./data-diff-property";
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

  const { branchName } = useParams();
  const navigate = useNavigate();

  // Relationship mayny: action, changed_at, branches, branches, peer, properties, summary
  // Relationship one: changes > branch, new, previous
  const {
    path,
    action,
    branches,
    peer: peerChange,
    properties, // For relationship many
    branch: peerBranch,
    new: newPeer,
    previous: previousPeer,
  } = peerChanges;

  const renderDiffDisplay = (peer: tDataDiffNodePeerValue, branch: any) => {
    if (peer?.kind && peer?.id) {
      const onClick = (event: React.MouseEvent) => {
        event.stopPropagation();

        getPeerRedirection(peer, branch, navigate);
      };

      return diffPeerContent(peer, action[branch], onClick, branch);
    }

    return diffPeerContent(peer, undefined, undefined, branch);
  };

  const renderTitleDisplay = () => {
    if (branches?.length) {
      return branches.map((branch: string, index: number) => {
        return (
          <div className="h-7 relative flex flex-col lg:flex-row " key={index}>
            <div className="flex flex-1 items-center">
              <div className="flex w-1/3 items-center group">
                {peerChange?.kind && <Badge>{peerChange?.kind}</Badge>}

                <span className="mr-2 font-semibold">{peerChange?.display_label}</span>

                {/* Do not display comment button if we are on the branch details view */}
                {!branchName && <DataDiffThread path={path} />}
              </div>

              <div className="flex w-2/3 items-center">
                <span className="h-7 pl-2 flex items-center w-1/2 font-semibold bg-green-100">
                  {branch === "main" && (
                    <span className="font-semibold">{renderDiffDisplay(peerChange, branch)}</span>
                  )}
                </span>
                <span className="h-7 pl-2 flex items-center w-1/2 font-semibold bg-custom-blue-10">
                  {branch !== "main" && (
                    <span className="font-semibold">{renderDiffDisplay(peerChange, branch)}</span>
                  )}
                </span>
              </div>
            </div>
          </div>
        );
      });
    }

    if (peerBranch) {
      return (
        <div className="h-7 relative flex flex-col lg:flex-row ">
          <div className="flex flex-1 items-center">
            <div className="flex w-1/3 items-center group">
              {newPeer?.kind && <Badge>{newPeer?.kind}</Badge>}

              <span className="mr-2 font-semibold">{name}</span>

              {/* Do not display comment button if we are on the branch details view */}
              {!branchName && <DataDiffThread path={path} />}
            </div>

            <div className="flex w-2/3 items-center">
              <span className="h-7 pl-2 flex items-center w-1/2 font-semibold bg-green-100">
                {peerBranch === "main" && (
                  <span className="font-semibold">
                    {renderDiffDisplay({ new: newPeer, previous: previousPeer }, null)}
                  </span>
                )}
              </span>
              <span className="h-7 pl-2 flex items-center w-1/2 font-semibold bg-custom-blue-10">
                {peerBranch !== "main" && (
                  <span className="font-semibold">
                    {renderDiffDisplay(null, { new: newPeer, previous: previousPeer })}
                  </span>
                )}
              </span>
            </div>
          </div>
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
      <div className="border-l-4 border-transparent">
        <Accordion title={renderTitleDisplay()}>{propertiesChanges}</Accordion>
      </div>
    );
  }

  return (
    <div className={classNames("flex flex-col border-l-4 border-transparent ")}>
      {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
      <ChevronDownIcon className="w-4 h-4 mx-2 text-transparent" aria-hidden="true" />
      <div className="flex-1">{renderTitleDisplay()}</div>
    </div>
  );
};
