import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { ReactNode } from "react";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import Accordion from "../../components/display/accordion";
import { DateDisplay } from "../../components/display/date-display";
import { QSP } from "../../config/qsp";
import { classNames } from "../../utils/common";
import { diffContent } from "../../utils/diff";
import {
  getNodeClassName,
  tDataDiffNodeElement,
  tDataDiffNodePeerChange,
  tDataDiffNodeValueChange,
} from "./data-diff-node";
import { DataDiffPeer } from "./data-diff-peer";
import { DataDiffProperty } from "./data-diff-property";
import { DataDiffConflictInfo } from "./diff-conflict-info";
import { DiffPill } from "./diff-pill";
import { DataDiffThread } from "./diff-thread";

export type tDataDiffNodeElementProps = {
  element: tDataDiffNodeElement;
};

export const DataDiffElement = (props: tDataDiffNodeElementProps) => {
  const { element } = props;

  const { branchname } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);

  const { name, change, path } = element;

  // value AND properties || peer || peers
  const { value, changed_at, properties, summary, peer, peers } = change ?? {};

  const renderDiffDisplay = (diffValue: tDataDiffNodeValueChange) => {
    if (diffValue && diffValue?.action && diffContent[diffValue?.action]) {
      return diffContent[diffValue?.action](diffValue);
    }

    return null;
  };

  const renderTitleDisplay = (diffValue: tDataDiffNodeValueChange) => {
    return (
      <div className="relative p-1 pr-0 flex flex-col lg:flex-row ">
        <div className="flex flex-1 items-center">
          <div className="flex flex-1 items-center group">
            <span className="mr-2 font-semibold">{name}</span>

            {/* Do not display comment button if we are on the branch details view */}
            {!branchname && <DataDiffThread path={path} />}
          </div>

          <div className="flex flex-1">
            <span className="font-semibold">{renderDiffDisplay(diffValue)}</span>
          </div>
        </div>

        <div className="flex flex-1 lg:justify-end items-center mt-2 lg:mt-0">
          <DiffPill {...summary} />

          <div className="flex lg:w-[200px]">
            {changed_at && <DateDisplay date={changed_at} hideDefault />}
          </div>
        </div>

        {!branchname && <DataDiffConflictInfo path={path} />}
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
    return (
      <div className={value?.changes?.length > 1 ? "rounded-md bg-red-400 p-1 mb-1" : "mb-1"}>
        {value?.changes?.map((change, index) => {
          return (
            <div
              key={index}
              className={classNames(
                "flex flex-col rounded-md mb-1 last:mb-0",
                getNodeClassName([], change.branch, branchOnly)
              )}>
              {propertiesChanges?.length > 0 && (
                <Accordion title={renderTitleDisplay(change)}>
                  <div className="rounded-md">{propertiesChanges}</div>
                </Accordion>
              )}

              {!propertiesChanges?.length && !peersChanges?.length && (
                <div className="flex">
                  {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
                  <ChevronDownIcon className="w-4 h-4 mr-2 text-transparent" aria-hidden="true" />
                  <div className="flex-1">{renderTitleDisplay(change)}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  if (peersChanges?.length) {
    return <>{peersChanges}</>;
  }

  if (peer && peer?.changes?.length) {
    return (
      <div className={peer?.changes?.length > 1 ? "rounded-md bg-red-400 p-1 mb-1" : "mb-1"}>
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
