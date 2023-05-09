import Accordion from "../../../components/accordion";
import { BADGE_TYPES, Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffElement } from "./data-diff-element";
import { DiffPill } from "./diff-pill";

export type tDataDiffNodePropertyValue = {
  new: string;
  previous: string;
};

export type tDataDiffNodeProperty = {
  type?: string;
  changed_at?: number;
  action: string;
  value: tDataDiffNodePropertyValue;
};

export type tDataDiffNodePeerData = {
  id: string;
  kind: string;
  display_label?: string;
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

export type tDataDiffNodeValue = {
  action: string;
  branch: string;
  changed_at: string;
  type: string;
  value: tDataDiffNodePropertyValue;
};

export type tDataDiffNodeElement = {
  value: tDataDiffNodeValue;
  branch?: string;
  name: string;
  changed_at?: number;
  type?: string;
  identifier?: string;
  action: string;
  properties?: tDataDiffNodeProperty[];
  peer?: tDataDiffNodePeer;
  peers?: tDataDiffNodeElement[];
  summary?: tDataDiffNodeSummary;
};

export type tDataDiffNodeSummary = {
  added: number;
  updated: number;
  removed: number;
};

export type tDataDiffNode = {
  display_label: string;
  id: string;
  action: string;
  kind: string;
  changed_at?: number;
  summary: tDataDiffNodeSummary;
  elements: Map<string, tDataDiffNodeElement>;
};

export type tDataDiffNodeProps = {
  node: tDataDiffNode;
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

export const DataDiffNode = (props: tDataDiffNodeProps) => {
  const { node } = props;

  const { display_label, action, kind, changed_at, summary, elements } = node;

  const title = (
    <div className="p-2 pr-0 flex flex-1 hover:bg-gray-50">
      <div className="flex flex-1">
        <Badge className="mr-2" type={getBadgeType(action)}>
          {action?.toUpperCase()}
        </Badge>

        <Badge className="mr-2">{kind}</Badge>

        <span className="mr-2">{display_label}</span>
      </div>

      <DiffPill {...summary} />

      <div className="w-[160px] flex justify-end">
        {changed_at && <DateDisplay date={changed_at} hideDefault />}
      </div>
    </div>
  );

  return (
    <div className={"rounded-lg shadow p-4 m-4 bg-white"}>
      <Accordion title={title}>
        <div className="">
          {Object.values(elements).map((element: tDataDiffNodeElement, index: number) => (
            <DataDiffElement key={index} element={element} />
          ))}
        </div>
      </Accordion>
    </div>
  );
};
