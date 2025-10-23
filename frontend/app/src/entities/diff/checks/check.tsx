import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";

import { InfoButton } from "@/shared/components/buttons/info-button";
import Accordion from "@/shared/components/display/accordion";
import { DateDisplay } from "@/shared/components/display/date-display";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { List } from "@/shared/components/table/list";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

import { DataIntegrityConflicts } from "@/entities/diff/checks/data-integrity-conflicts";
import { SchemaIntegrityConflicts } from "@/entities/diff/checks/schema-integrity-conflicts";
import { useGetCheckDetails } from "@/entities/diff/domain/get-check-details.query";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";

type tCheckProps = {
  id: string;
};

const getCheckIcon = (conclusion?: string) => {
  switch (conclusion) {
    case "success": {
      return (
        <Tooltip enabled content={"Success"}>
          <Icon icon={"mdi:check-circle-outline"} className="mr-2 text-green-500" />
        </Tooltip>
      );
    }
    case "failure": {
      return (
        <Tooltip enabled content={"Failure"}>
          <Icon icon={"mdi:warning"} className="mr-2 text-red-500" />
        </Tooltip>
      );
    }
    default: {
      return (
        <Tooltip enabled content={"In progress"}>
          <Icon icon={"mdi:warning-circle-outline"} className="mr-2 text-yellow-500" />
        </Tooltip>
      );
    }
  }
};

const getCheckBorderColor = (severity?: string) => {
  switch (severity) {
    case "success": {
      return "border-green-400";
    }
    case "info": {
      return "border-yellow-400";
    }
    case "warning": {
      return "border-orange-400";
    }
    case "error": {
      return "border-red-400";
    }
    case "critical": {
      return "border-red-600";
    }
    default: {
      return "border-yellow-400";
    }
  }
};

export const Check = ({ id }: tCheckProps) => {
  const schemaKindLabel = useAtomValue(schemaKindLabelState);

  const { isPending, error, data: check } = useGetCheckDetails({ checkId: id });

  if (error) {
    return (
      <div className={"flex flex-col rounded-md border-l-4 bg-white p-2"}>
        <ErrorScreen message="Something went wrong when fetching the check details" />
      </div>
    );
  }

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (!check) {
    return null;
  }

  const {
    __typename,
    kind,
    origin,
    created_at,
    display_label,
    name,
    message,
    severity,
    conclusion,
    conflicts,
  } = check;

  const columns = [
    {
      name: "type",
      label: "Type",
    },
    {
      name: "kind",
      label: "Kind",
    },
    {
      name: "origin",
      label: "Origin",
    },
  ];

  const row = {
    values: {
      type: schemaKindLabel[__typename],
      kind: kind?.value,
      origin: origin?.value,
    },
  };

  return (
    <div
      className={classNames(
        "flex flex-col rounded-md border border-l-4 bg-gray-50 p-2",
        getCheckBorderColor(severity?.value)
      )}
    >
      <div className="mb-2 flex">
        <div className="flex flex-1 flex-col">
          <div className="flex items-center">
            {getCheckIcon(conclusion?.value)}

            {name?.value || display_label}

            <div className="flex flex-1 items-center justify-end">
              {created_at?.value && <DateDisplay date={created_at?.value} />}

              <Popover>
                <PopoverTrigger asChild>
                  <InfoButton />
                </PopoverTrigger>

                <PopoverContent>
                  <List columns={columns} row={row} />
                </PopoverContent>
              </Popover>
            </div>
          </div>

          {message?.value && (
            <div className="mt-2">
              <Accordion title={"Message"}>
                <CodeViewer>{message?.value}</CodeViewer>
              </Accordion>
            </div>
          )}
        </div>
      </div>

      {__typename === "CoreDataCheck" && !!conflicts?.value?.length && (
        <DataIntegrityConflicts conflicts={conflicts} />
      )}

      {__typename === "CoreSchemaCheck" && !!conflicts?.value?.length && (
        <SchemaIntegrityConflicts conflicts={conflicts} />
      )}
    </div>
  );
};
