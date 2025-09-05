import { Icon } from "@iconify-icon/react";

import { InfoButton } from "@/shared/components/buttons/info-button";
import Accordion from "@/shared/components/display/accordion";
import { DateDisplay } from "@/shared/components/display/date-display";
import { DurationDisplay } from "@/shared/components/display/duration-display";
import { List } from "@/shared/components/table/list";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { ValidatorDetails } from "./validator-details";

type tValidatorProps = {
  validator: any;
};

const getValidatorState = (state?: string, conclusion?: string) => {
  switch (state) {
    case "queued": {
      return (
        <Tooltip content="Queued" enabled>
          <Icon icon={"mdi:timer-sand-complete"} className="text-yellow-500" />
        </Tooltip>
      );
    }
    case "in_progress": {
      return (
        <Tooltip content="In progress" enabled>
          <Icon icon={"mdi:clock-time-four-outline"} className="text-yellow-500" />
        </Tooltip>
      );
    }
    case "completed": {
      if (conclusion === "success") {
        return (
          <Tooltip content="Success" enabled>
            <Icon
              icon={"mdi:check-circle-outline"}
              className="text-green-500"
              data-testid="validator-success"
            />
          </Tooltip>
        );
      }

      if (conclusion === "failure") {
        return (
          <Tooltip content="Failure" enabled>
            <Icon icon={"mdi:warning"} className="text-red-500" />
          </Tooltip>
        );
      }

      return (
        <Tooltip content="Unknown" enabled>
          <Icon icon={"mdi:warning-circle-outline"} className="text-yellow-500" />
        </Tooltip>
      );
    }
    default: {
      return null;
    }
  }
};

export const Validator = ({ validator }: tValidatorProps) => {
  const { id, display_label, started_at, completed_at, conclusion, state } = validator;

  const columns = [
    {
      name: "id",
      label: "ID",
    },
    {
      name: "display_label",
      label: "Name",
    },
    {
      name: "started_at",
      label: "Started at",
    },
    {
      name: "completed_at",
      label: "Completed at",
    },
    {
      name: "conclusion",
      label: "Conclusion",
    },
    {
      name: "state",
      label: "State",
    },
  ];

  const row = {
    values: {
      id: id.value,
      display_label: display_label.value,
      started_at: <DateDisplay date={started_at.value} />,
      completed_at: <DateDisplay date={completed_at.value} />,
      conclusion: conclusion.value,
      state: state.value,
    },
  };

  const title = (
    <div className="flex items-center gap-2">
      {getValidatorState(state?.value, conclusion?.value)}
      <span>{display_label}</span>
      <span className="font-normal">-</span>
      <DurationDisplay date={started_at.value} endDate={completed_at.value} />

      <div className="flex grow justify-end">
        <Popover>
          <PopoverTrigger onClick={(e) => e.stopPropagation()} asChild>
            <InfoButton />
          </PopoverTrigger>

          <PopoverContent>
            <List columns={columns} row={row} />
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );

  return (
    <Accordion title={title} className="rounded-md bg-white p-2">
      <ValidatorDetails id={id} />
    </Accordion>
  );
};
