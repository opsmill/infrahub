import type { NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { Icon } from "@iconify-icon/react";

export const EventAttributes = ({ attributes }: Pick<NodeMutatedEvent, "attributes">) => {
  return (
    <div className="flex flex-col gap-2 text-xs">
      {attributes.map(({ action, name, value, value_previous }) => {
        return (
          <div className="grid grid-cols-2 gap-2 items-center" key={`${action}_${name}`}>
            <div className="font-medium text-gray-500 flex items-center h-8">{name}</div>

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
