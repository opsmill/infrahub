import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { ReactNode } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import Accordion from "../../../components/accordion";
import { Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { QSP } from "../../../config/qsp";
import { classNames } from "../../../utils/common";
import { diffContent } from "../../../utils/diff";
import {
  getNodeClassName,
  tDataDiffNodeElement,
  tDataDiffNodePeerChange,
  tDataDiffNodeValueChange,
} from "./data-diff-node";
import { DataDiffPeer } from "./data-diff-peer";
import { DataDiffProperty } from "./data-diff-property";
import { DiffPill } from "./diff-pill";

export type tDataDiffNodeElementProps = {
  element: tDataDiffNodeElement;
};

export const DataDiffElement = (props: tDataDiffNodeElementProps) => {
  const { element } = props;

  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);

  const { name, change } = element;

  // value AND propertie || peer || peers
  const { value, changed_at, properties, summary, peer, peers } = change ?? {};

  const renderDiffDisplay = (diffValue: tDataDiffNodeValueChange) => {
    if (diffValue && diffValue?.action && diffContent[diffValue?.action]) {
      return diffContent[diffValue?.action](diffValue);
    }

    return null;
  };

  const renderTitleDisplay = (diffValue: tDataDiffNodeValueChange) => {
    return (
      <div className="p-1 pr-0 grid grid-cols-3 gap-4">
        <div className="flex">
          {!name && peer?.kind && <Badge>{peer?.kind}</Badge>}

          <span className="mr-2 font-semibold">{name}</span>
        </div>

        <div className="flex">
          <span className="font-semibold">{renderDiffDisplay(diffValue)}</span>
        </div>

        <div className="flex justify-end font-normal">
          <DiffPill {...summary} />

          <div className="w-[380px] flex justify-end">
            {changed_at && <DateDisplay date={changed_at} hideDefault />}
          </div>
        </div>
      </div>
    );
  };

  const propertiesChanges: ReactNode[] = Object.values(properties ?? {}).map(
    ({ changes }, index: number) =>
      changes?.map((change: any, index2: number) => (
        <DataDiffProperty key={`${index}-${index2}`} property={change} />
      ))
  );

  const peersChanges: ReactNode[] = Object.values(peers ?? {}).map(
    (peerChanges: tDataDiffNodePeerChange, index: number) => (
      <DataDiffPeer key={index} peerChanges={peerChanges} />
    )
  );

  if (value?.changes?.length) {
    return value?.changes?.map((change, index) => {
      return (
        <div
          key={index}
          className={classNames(
            "p-1 pr-0 flex flex-col rounded-md mb-1 last:mb-0",
            getNodeClassName([], change.branch, branchOnly)
          )}>
          {propertiesChanges?.length && (
            <Accordion title={renderTitleDisplay(change)}>
              <div className="rounded-md overflow-hidden">{propertiesChanges}</div>
            </Accordion>
          )}

          {!propertiesChanges?.length && !peersChanges?.length && (
            <div className="flex">
              {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
              <ChevronDownIcon className="h-5 w-5 mr-2 text-transparent" aria-hidden="true" />
              <div className="flex-1">{renderTitleDisplay(change)}</div>
            </div>
          )}
        </div>
      );
    });
  }

  if (peersChanges?.length) {
    return (
      <div className={"p-1 pr-0 flex flex-col rounded-md mb-1 last:mb-0"}>
        <div className="rounded-md overflow-hidden">{peersChanges}</div>
      </div>
    );
  }

  if (peer && peer?.changes) {
    return peer?.changes.map((peer, index) => <DataDiffPeer key={index} peerChanges={peer} />);
  }

  return null;
};
