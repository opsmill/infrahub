import { Icon } from "@iconify-icon/react";
import { MoreButton } from "../../../components/buttons/more-button";
import Accordion from "../../../components/display/accordion";
import { DateDisplay } from "../../../components/display/date-display";
import { DurationDisplay } from "../../../components/display/duration-display";
import { PopOver } from "../../../components/display/popover";
import { List } from "../../../components/table/list";
import { Tooltip } from "../../../components/utils/tooltip";
import { ValidatorDetails } from "./validator-details";

type tValidatorProps = {
  validator: any;
};

const getValidatorState = (state?: string, conclusion?: string) => {
  switch (state) {
    case "queued": {
      return (
        <Tooltip message={"Queued"}>
          <Icon icon={"mdi:timer-sand-complete"} className="text-yellow-500 mr-2" />
        </Tooltip>
      );
    }
    case "in_progress": {
      return (
        <Tooltip message={"In progress"}>
          <Icon icon={"mdi:clock-time-four-outline"} className="text-yellow-500 mr-2" />
        </Tooltip>
      );
    }
    case "completed": {
      if (conclusion === "success") {
        return (
          <Tooltip message={"Success"}>
            <Icon icon={"mdi:check-circle-outline"} className="text-green-500 mr-2" />
          </Tooltip>
        );
      }

      if (conclusion === "failure") {
        return (
          <Tooltip message={"Failure"}>
            <Icon icon={"mdi:warning"} className="text-red-500 mr-2" />
          </Tooltip>
        );
      }

      return (
        <Tooltip message={"Unkown"}>
          <Icon icon={"mdi:warning-circle-outline"} className="text-yellow-500 mr-2" />
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
    <div className="flex items-center">
      {getValidatorState(state?.value, conclusion?.value)}

      <span>{display_label}</span>

      <span className="mx-2 font-normal">-</span>

      <DurationDisplay date={started_at.value} endDate={completed_at.value} />

      <div className="flex flex-1 justify-end">
        <PopOver buttonComponent={MoreButton}>
          <List columns={columns} row={row} />
        </PopOver>
      </div>
    </div>
  );

  return (
    <Accordion title={title} className="bg-custom-white rounded-md p-2">
      <ValidatorDetails id={id} />
    </Accordion>
  );
};
