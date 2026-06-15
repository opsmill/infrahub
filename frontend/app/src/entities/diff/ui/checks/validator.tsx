import { Icon } from "@iconify-icon/react";
import { Popover, PopoverTrigger, Tooltip } from "@infrahub/ui";

import { InfoButton } from "@/shared/components/buttons/info-button";
import Accordion from "@/shared/components/display/accordion";
import { DateDisplay } from "@/shared/components/display/date-display";
import { DurationDisplay } from "@/shared/components/display/duration-display";
import { List } from "@/shared/components/table/list";
import { Link } from "@/shared/components/ui/link";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";

import { ValidatorDetails } from "./validator-details";

const ARTIFACT_VALIDATOR_KIND = "CoreArtifactValidator";

type tValidatorProps = {
  validator: any;
};

const getValidatorState = (state?: string, conclusion?: string) => {
  switch (state) {
    case "queued": {
      return (
        <Tooltip message="Queued" nonInteractiveTrigger>
          <Icon icon={"mdi:timer-sand-complete"} className="text-yellow-500" />
        </Tooltip>
      );
    }
    case "in_progress": {
      return (
        <Tooltip message="In progress" nonInteractiveTrigger>
          <Icon icon={"mdi:clock-time-four-outline"} className="text-yellow-500" />
        </Tooltip>
      );
    }
    case "completed": {
      if (conclusion === "success") {
        return (
          <Tooltip message="Success" nonInteractiveTrigger>
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
          <Tooltip message="Failure" nonInteractiveTrigger>
            <Icon icon={"mdi:warning"} className="text-red-500" />
          </Tooltip>
        );
      }

      return (
        <Tooltip message="Unknown" nonInteractiveTrigger>
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

  const artifactDefinition =
    validator.__typename === ARTIFACT_VALIDATOR_KIND ? validator.definition?.node : null;

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
    ...(artifactDefinition ? [{ name: "definition", label: "Definition" }] : []),
  ];

  const row = {
    values: {
      id,
      display_label,
      started_at: <DateDisplay date={started_at.value} />,
      completed_at: <DateDisplay date={completed_at.value} />,
      conclusion: conclusion.value,
      state: state.value,
      ...(artifactDefinition
        ? {
            definition: (
              <Link to={getObjectDetailsUrl("CoreArtifactDefinition", artifactDefinition.id)}>
                {artifactDefinition.display_label}
              </Link>
            ),
          }
        : {}),
    },
  };

  const title = (
    <div className="flex items-center gap-2">
      {getValidatorState(state?.value, conclusion?.value)}
      <span>{display_label}</span>
      <span className="font-normal">-</span>
      <DurationDisplay date={started_at.value} endDate={completed_at.value} />

      {artifactDefinition && (
        <Tooltip message={`Open Artifact Definition: ${artifactDefinition.display_label}`}>
          <Link
            to={getObjectDetailsUrl("CoreArtifactDefinition", artifactDefinition.id)}
            onClick={(e) => e.stopPropagation()}
            className="text-gray-500 hover:text-gray-700"
          >
            <Icon icon="mdi:open-in-new" />
          </Link>
        </Tooltip>
      )}

      <PopoverTrigger>
        <InfoButton className="ml-auto" />

        <Popover>
          <List columns={columns} row={row} />
        </Popover>
      </PopoverTrigger>
    </div>
  );

  return (
    <Accordion title={title} className="rounded-md bg-white p-2" data-testid="validator">
      <ValidatorDetails id={id} />
    </Accordion>
  );
};
