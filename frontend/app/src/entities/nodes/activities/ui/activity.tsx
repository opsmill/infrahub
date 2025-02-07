import { EventNodeInterface, NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { DateDisplay } from "@/shared/components/display/date-display";
import { Badge } from "@/shared/components/ui/badge";

import { DisplayLabel } from "@/entities/nodes/object/ui/display-label";
import { PropertyRow } from "@/entities/schema/ui/styled";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { Icon } from "@iconify-icon/react";

export type ActivityType = EventNodeInterface | NodeMutatedEvent;

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
      <PropertyRow title="Account" value={<DisplayLabel id={account_id} />} />
      {"attributes" in props && (
        <PropertyRow
          title="Changes"
          value={<AcitivityAttributes attributes={props.attributes} />}
        />
      )}
    </div>
  );
};

export const Activity = (props: ActivityType) => {
  const { event, occurred_at, account_id } = props;

  return (
    <div className="flex gap-3 bg-slate-50/50 p-2 rounded-md shadow-sm">
      {/* <TimelineBorder /> */}

      <div className="flex flex-col gap-2 grow">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {account_id && (
              <Badge>
                <DisplayLabel id={account_id} />
              </Badge>
            )}

            <div className="flex gap-x-1.5 font-semibold text-gray-800">{event}</div>
          </div>
          <div className="text-xs font-medium text-gray-500 dark:text-neutral-400">
            <DateDisplay date={occurred_at} />
          </div>
        </div>

        {"attributes" in props && <AcitivityAttributes attributes={props.attributes} />}

        <div>
          <Popover>
            <PopoverTrigger>
              <p className="text-sm underline text-gray-600 dark:text-neutral-400 mb-1">
                View more.
              </p>
            </PopoverTrigger>
            <PopoverContent className="w-full">
              <ActivityDetails {...props} />
            </PopoverContent>
          </Popover>
        </div>
      </div>
    </div>
  );
};
