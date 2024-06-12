import { Filters } from "@/components/filters";
import { Tabs } from "@/components/tabs";
import { QSP } from "@/config/qsp";
import { DynamicFieldData } from "@/screens/edit-form-hook/dynamic-control-types";
import { formatISO, parseISO } from "date-fns";
import { StringParam, useQueryParam } from "use-query-params";
import { ArtifactsDiff } from "./artifact-diff/artifacts-diff";
import { DataDiff } from "./data-diff";
import { FilesDiff } from "./file-diff/files-diff";
import { SchemaDiff } from "./schema-diff";

export const DIFF_TABS = {
  CONVERSATIONS: "conversation",
  STATUS: "status",
  DATA: "data",
  FILES: "files",
  CHECKS: "checks",
  ARTIFACTS: "artifacts",
  SCHEMA: "schema",
};

const tabs = [
  {
    label: "Data",
    name: DIFF_TABS.DATA,
  },
  {
    label: "Files",
    name: DIFF_TABS.FILES,
  },
  {
    label: "Artifacts",
    name: DIFF_TABS.ARTIFACTS,
  },
  {
    label: "Schema",
    name: DIFF_TABS.SCHEMA,
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch (tab) {
    case DIFF_TABS.FILES:
      return <FilesDiff />;
    case DIFF_TABS.SCHEMA:
      return <SchemaDiff />;
    case DIFF_TABS.ARTIFACTS:
      return <ArtifactsDiff />;
    default:
      return <DataDiff />;
  }
};

export const Diff = () => {
  const [qspTab] = useQueryParam(QSP.BRANCH_DIFF_TAB, StringParam);
  const [timeFrom, setTimeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo, setTimeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);

  const fields: DynamicFieldData[] = [
    {
      name: "time_from",
      label: "Time from",
      type: "datepicker",
      value: timeFrom ? parseISO(timeFrom) : undefined,
    },
    {
      name: "time_to",
      label: "Time to",
      type: "datepicker",
      value: timeTo ? parseISO(timeTo) : undefined,
    },
  ];

  const handleSubmit = (data: any) => {
    const { time_from, time_to } = data;

    setTimeFrom(time_from ? formatISO(time_from) : undefined);

    setTimeTo(time_to ? formatISO(time_to) : undefined);
  };

  return (
    <div className="flex flex-col flex-1">
      <div className="bg-custom-white p-2 flex">
        <Filters fields={fields} onSubmit={handleSubmit} />
      </div>

      <div>
        <Tabs tabs={tabs} qsp={QSP.BRANCH_DIFF_TAB} />
      </div>

      <div className="flex flex-col flex-1">{renderContent(qspTab)}</div>
    </div>
  );
};
