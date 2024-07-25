import Accordion from "@/components/display/accordion";
import { classNames } from "@/utils/common";
import { diffContent } from "@/utils/diff";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { ReactNode } from "react";
import { useParams } from "react-router-dom";
import {
  tDataDiffNodeElement,
  tDataDiffNodePeerChange,
  tDataDiffNodeValueChange,
} from "./data-diff-node";
import { DataDiffPeer } from "./data-diff-peer";
import { DataDiffProperty } from "./data-diff-property";
import { DataDiffConflictInfo } from "./diff-conflict-info";
import { DataDiffThread } from "./diff-thread";

export type tDataDiffNodeElementProps = {
  element: tDataDiffNodeElement;
};

export const DataDiffElement = (props: tDataDiffNodeElementProps) => {
  const { element } = props;

  const { branchName } = useParams();

  const { name, change, path } = element;

  // value AND properties || peer || peers
  const { value, properties, peer, peers } = change ?? {};

  const renderDiffDisplay = (diffValue: tDataDiffNodeValueChange) => {
    if (diffValue && diffValue?.action && diffContent[diffValue?.action]) {
      return diffContent[diffValue?.action](diffValue);
    }

    return null;
  };

  const renderTitleDisplay = (
    diffValue?: tDataDiffNodeValueChange,
    branchDiffValue?: tDataDiffNodeValueChange
  ) => {
    return (
      <div className="h-7 relative flex flex-col lg:flex-row ">
        <div className="flex flex-1 items-center">
          <div className="flex w-1/3 items-center group">
            <span className="mr-2 font-semibold">{name}</span>

            {/* Do not display comment button if we are on the branch details view */}
            {!branchName && <DataDiffThread path={path} />}
          </div>

          <div className="flex w-2/3 items-center">
            <span className="h-7 pl-2 flex items-center w-1/2 font-semibold bg-green-100">
              {diffValue && renderDiffDisplay(diffValue)}
            </span>
            <span className="h-7 pl-2 flex items-center w-1/2 font-semibold bg-custom-blue-10">
              {branchDiffValue && renderDiffDisplay(branchDiffValue)}
            </span>
          </div>
        </div>

        {!branchName && <DataDiffConflictInfo path={path} />}
      </div>
    );
  };

  const propertiesChanges: ReactNode[] = Object.values(properties ?? {}).map(
    ({ changes, path }, index: number) =>
      changes?.map((change: any, index2: number) => (
        <DataDiffProperty key={`${index}-${index2}`} property={change} path={path} />
      ))
  );

  const peersChanges: ReactNode[] = Object.values(peers ?? {}).map(
    (peerChanges: tDataDiffNodePeerChange, index: number) => (
      <DataDiffPeer key={index} peerChanges={peerChanges} />
    )
  );

  if (value?.changes?.length) {
    const mainDiff = value?.changes.find((change) => change.branch === "main");
    const branchDiff = value?.changes.find((change) => change.branch !== "main");

    return (
      <div
        className={classNames(
          "overflow-hidden border-l-4 border-transparent",
          // Conflict
          value.changes.length > 1 && " border-yellow-200 bg-yellow-50"
        )}>
        <div className={classNames("flex flex-col rounded-md divide-y")}>
          {propertiesChanges?.length > 0 && (
            <Accordion title={renderTitleDisplay(mainDiff, branchDiff)}>
              <div className="rounded-md">{propertiesChanges}</div>
            </Accordion>
          )}

          {!propertiesChanges?.length && !peersChanges?.length && (
            <div className="flex">
              {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
              <ChevronDownIcon className="w-4 h-4 mr-2 text-transparent" aria-hidden="true" />
              <div className="flex-1">{renderTitleDisplay(mainDiff, branchDiff)}</div>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (peersChanges?.length) {
    return peersChanges;
  }

  if (peer && peer?.changes?.length) {
    return (
      <div
        className={classNames(
          "mb-1",
          peer?.changes?.length > 1 && "border-yellow-200 bg-yellow-50"
        )}>
        {peer?.changes.map((peerChanges, index) => (
          <DataDiffPeer
            key={index}
            peerChanges={{ ...peerChanges, path: peer?.path }}
            peerProperties={properties}
            name={name}
          />
        ))}
      </div>
    );
  }

  return null;
};
