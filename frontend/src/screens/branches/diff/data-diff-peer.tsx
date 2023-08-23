import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import Accordion from "../../../components/accordion";
import { Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { iSchemaKindNameMap, schemaKindNameState } from "../../../state/atoms/schemaKindName.atom";
import { classNames } from "../../../utils/common";
import { diffPeerContent } from "../../../utils/diff";
import { constructPath } from "../../../utils/fetch";
import { getObjectDetailsUrl } from "../../../utils/objects";
import {
  tDataDiffNodePeer,
  tDataDiffNodePeerChange,
  tDataDiffNodePeerData,
} from "./data-diff-node";
import { DataDiffProperty } from "./data-diff-property";
import { DiffPill } from "./diff-pill";

export type tDataDiffNodePeerProps = {
  peerChanges: tDataDiffNodePeerChange;
};

export const getPeerRedirection = (
  peer: tDataDiffNodePeerData | tDataDiffNodePeer,
  branch: string,
  schemaKindName: iSchemaKindNameMap,
  navigate: Function
) => {
  if (!peer.id || !peer.kind) {
    return;
  }

  const objectUrl = getObjectDetailsUrl(peer.id, peer.kind, schemaKindName);

  const url = branch ? constructPath(`${objectUrl}?branch=${branch}`) : constructPath(objectUrl);

  return () => {
    navigate(url);
  };
};

export const DataDiffPeer = (props: tDataDiffNodePeerProps) => {
  const { peerChanges } = props;

  const [schemaKindName] = useAtom(schemaKindNameState);
  const navigate = useNavigate();

  // Relationship mayny: action, changed_at, branches, branches, peer, properties, summary
  // Relationship one: changes > branch, new, previous
  const {
    action,
    changed_at,
    branches,
    peer: peerChange,
    properties,
    summary,
    branch: peerBranch,
    new: newPeer,
    previous: previousPeer,
  } = peerChanges;

  const renderDiffDisplay = (peer: tDataDiffNodePeerData | tDataDiffNodePeer, branch: string) => {
    if (peer?.kind && peer?.id) {
      const onClick = getPeerRedirection(peer, branch, schemaKindName, navigate);

      return diffPeerContent(peer, action[branch], onClick, branch);
    }

    return diffPeerContent(peer, undefined, undefined, branch);
  };

  const renderTitleDisplay = () => {
    if (branches?.length) {
      return branches.map((branch: string, index: number) => {
        return (
          <div className="p-1 pr-0 grid grid-cols-3 gap-4 mr-2 last:mr-0" key={index}>
            <div className="flex">
              {peerChange?.kind && <Badge>{peerChange?.kind}</Badge>}

              <span className="mr-2 font-semibold">{peerChange?.display_label}</span>
            </div>

            <div className="flex">
              <span className="font-semibold">{renderDiffDisplay(peerChange, branch)}</span>
            </div>

            <div className="flex justify-end font-normal">
              <DiffPill {...summary} />

              <div className="w-[380px] flex justify-end">
                {changed_at && <DateDisplay date={changed_at} hideDefault />}
              </div>
            </div>
          </div>
        );
      });
    }

    if (peerBranch) {
      return (
        <div className="p-1 pr-0 grid grid-cols-3 gap-4 mr-2 last:mr-0">
          <div className="flex">
            {newPeer?.kind && <Badge>{newPeer?.kind}</Badge>}
            {previousPeer?.kind && <Badge>{previousPeer?.kind}</Badge>}

            <span className="mr-2 font-semibold">{newPeer?.display_label}</span>
            <span className="mr-2 font-semibold">{previousPeer?.display_label}</span>
          </div>

          <div className="flex">
            <span className="font-semibold">
              {renderDiffDisplay({ new: newPeer, previous: previousPeer }, peerBranch)}
            </span>
          </div>

          <div className="flex justify-end font-normal">
            <DiffPill {...summary} />

            <div className="w-[380px] flex justify-end">
              {changed_at && <DateDisplay date={changed_at} hideDefault />}
            </div>
          </div>
        </div>
      );
    }

    return null;
  };

  const propertiesChanges: ReactNode[] = Object.values(properties ?? {}).map(
    (property, index: number) =>
      property.changes?.map((change: any, index2: number) => (
        <DataDiffProperty key={`${index}-${index2}`} property={change} />
      ))
  );

  // If there are some properties, then display the accordion
  if (propertiesChanges?.length) {
    return <Accordion title={renderTitleDisplay()}>{propertiesChanges}</Accordion>;
  }

  return (
    <div
      className={classNames(
        "p-1 pr-0 flex flex-col rounded-md mb-1 last:mb-0",
        peerBranch === "main" ? "bg-custom-blue-10" : "bg-green-200"
      )}>
      <div className="flex">
        {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
        <ChevronDownIcon className="h-5 w-5 mr-2 text-transparent" aria-hidden="true" />
        <div className="flex-1">{renderTitleDisplay()}</div>
      </div>
    </div>
  );
};
