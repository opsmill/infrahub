import DatetimeField from "@/components/form/fields/datetime.field";
import { Tabs } from "@/components/tabs";
import { Form, FormSubmit } from "@/components/ui/form";
import { DIFF_TABS } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { DateTimeParam, StringParam, useQueryParam } from "use-query-params";
import { ArtifactsDiff } from "../diff/artifact-diff/artifacts-diff";
import { FilesDiff } from "../diff/file-diff/files-diff";
import { NodeDiff } from "../diff/node-diff";

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
    case DIFF_TABS.ARTIFACTS:
      return <ArtifactsDiff />;
    case DIFF_TABS.SCHEMA:
      return <NodeDiff filters={{ namespace: { includes: ["Schema"], excludes: ["Profile"] } }} />;
    default:
      return <NodeDiff filters={{ namespace: { excludes: ["Schema", "Profile"] } }} />;
  }
};

export const Diff = () => {
  const [qspTab] = useQueryParam(QSP.BRANCH_DIFF_TAB, StringParam);

  return (
    <div>
      <div className="bg-custom-white p-2">
        <DateDiffForm />
      </div>

      <div>
        <Tabs tabs={tabs} qsp={QSP.BRANCH_DIFF_TAB} />
      </div>

      <div className="flex flex-col flex-1">{renderContent(qspTab)}</div>
    </div>
  );
};

const DateDiffForm = () => {
  const [timeFrom, setTimeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, DateTimeParam);
  const [timeTo, setTimeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, DateTimeParam);

  const handleSubmit = async (data: any) => {
    const { time_from, time_to } = data;

    if (time_from?.toString() !== timeFrom?.toString()) {
      setTimeFrom(time_from ?? undefined);
    }
    if (time_to?.toString() !== timeTo?.toString()) {
      setTimeTo(time_to ?? undefined);
    }
  };

  return (
    <Form onSubmit={handleSubmit}>
      <div className="flex space-x-4">
        <DatetimeField name="time_from" label="Time from" date={timeFrom} />
        <DatetimeField name="time_to" label="Time to" date={timeTo} />
      </div>
      <FormSubmit variant="outline">Validate</FormSubmit>
    </Form>
  );
};
