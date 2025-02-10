import { EventNodeInterface, NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { DateDisplay } from "@/shared/components/display/date-display";

import { DisplayLabel } from "@/entities/nodes/object/ui/display-label";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { PropertyRow } from "@/entities/schema/ui/styled";
import { constructPath } from "@/shared/api/rest/fetch";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Link } from "@/shared/components/ui/link";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { TimelineBorder } from "@/shared/components/ui/timeline-border";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { ReactElement } from "react";
import {
  BRANCH_CREATED_EVENT,
  BRANCH_DELETED_EVENT,
  BRANCH_EVENTS,
  BRANCH_REBASEDED_EVENT,
  NODE_MUTATED_EVENT,
} from "../utils/constants";

export type BranchActivityType = EventNodeInterface & {
  __typename:
    | typeof BRANCH_DELETED_EVENT
    | typeof BRANCH_CREATED_EVENT
    | typeof BRANCH_REBASEDED_EVENT;
};

export type NodeActivityType = NodeMutatedEvent & {
  __typename: typeof NODE_MUTATED_EVENT;
};

export type ActivityType = BranchActivityType | NodeActivityType;

export const NODE_EVENTS_MAPPING: Record<string, string> = {
  "infrahub.node.created": "created",
  "infrahub.node.updated": "updated",
  "infrahub.node.deleted": "deleted",
};

export const BRANCH_EVENTS_MAPPING: Record<string, (param: string) => ReactElement> = {
  "infrahub.branch.created": (branch) => (
    <div>
      Branch <span className="text-black font-semibold">{branch}</span> created
    </div>
  ),
  "infrahub.branch.rebased": (branch) => (
    <div>
      Branch <span className="text-black font-semibold">{branch}</span> rebased
    </div>
  ),
  "infrahub.branch.deleted": (branch) => (
    <div>
      Branch <span className="text-black font-semibold">{branch}</span> deleted
    </div>
  ),
};

const AcitivityAttributes = ({ attributes }: Pick<NodeMutatedEvent, "attributes">) => {
  return (
    <div className="pl-8 text-sm">
      {attributes.map(({ action, name, value, value_previous }) => {
        return (
          <div className="grid grid-cols-2 gap-2" key={`${action}_${name}`}>
            <div>{name}</div>

            <div className="flex items-center gap-4">
              <div className="text-gray-400">{value_previous ?? "Ø"}</div>

              <Icon icon={"mdi:chevron-right"} className="text-custom-blue-500" />

              <div>{value ?? "Ø"}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

const ActivityDetails = ({ id, event, occurred_at, account_id, ...props }: ActivityType) => {
  return (
    <div className="divide-y">
      <PropertyRow
        title="ID"
        value={
          <div className="flex items-center gap-2">
            {id} <CopyToClipboard text={id} />
          </div>
        }
      />
      <PropertyRow title="Event" value={event} />
      <PropertyRow title="Occured at" value={<DateDisplay date={occurred_at} />} />
      {account_id && <PropertyRow title="Account" value={<DisplayLabel id={account_id} />} />}
      {"attributes" in props && (
        <PropertyRow
          title="Changes"
          value={<AcitivityAttributes attributes={props.attributes} />}
        />
      )}
    </div>
  );
};

const NodeActivity = (props: NodeMutatedEvent) => {
  const { event, occurred_at, account_id } = props;
  const schemaLabels = useAtomValue(schemaKindLabelState);

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          {account_id && (
            <div className="font-semibold">
              <DisplayLabel id={account_id} />
            </div>
          )}

          <div className="text-gray-500">{NODE_EVENTS_MAPPING[event] ?? "-"}</div>

          <div className="font-semibold">{schemaLabels[props.payload.data.node_kind] ?? "-"}</div>

          <Link
            to={constructPath(
              `/objects/${props.payload.data.node_kind}/${props.payload.data.node_id}`
            )}
          >
            <DisplayLabel id={props.payload.data.node_id} />
          </Link>
        </div>
        <div className="text-xs font-medium text-gray-500 dark:text-neutral-400">
          <DateDisplay date={occurred_at} />
        </div>
      </div>

      <AcitivityAttributes attributes={props.attributes} />
    </>
  );
};

const BranchActivity = (props: EventNodeInterface) => {
  console.log("props: ", props);
  const { event, occurred_at, branch } = props;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <div className="text-gray-500">
            {branch && BRANCH_EVENTS_MAPPING[event] && BRANCH_EVENTS_MAPPING[event](branch)}
          </div>
        </div>
        <div className="text-xs font-medium text-gray-500 dark:text-neutral-400">
          <DateDisplay date={occurred_at} />
        </div>
      </div>
    </>
  );
};

export const Activity = ({ __typename, ...props }: ActivityType) => {
  return (
    <div className="flex gap-2">
      <TimelineBorder />

      <div className="flex flex-grow gap-3 p-2 rounded-md shadow-sm border">
        <div className="flex flex-col gap-2 grow">
          {__typename === NODE_MUTATED_EVENT && <NodeActivity {...props} />}

          {BRANCH_EVENTS.includes(__typename) && <BranchActivity {...props} />}

          <div>
            <Popover>
              <PopoverTrigger>
                <div className="flex flex-grow justify-end">
                  <p className="text-sm underline text-gray-600 dark:text-neutral-400 mb-1">
                    View more.
                  </p>
                </div>
              </PopoverTrigger>
              <PopoverContent className="w-full">
                <ActivityDetails {...props} />
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>
    </div>
  );
};
