import { Tabs } from "../../../components/tabs";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../../config/constants";
import { DataDiff } from "./data-diff";

const DIFF_TABS = {
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
    label: "Conversation",
    name: DIFF_TABS.CONVERSATIONS
  },
  {
    label: "Status",
    name: DIFF_TABS.STATUS
  },
  {
    label: "Data",
    name: DIFF_TABS.DATA
  },
  {
    label: "Files",
    name: DIFF_TABS.FILES
  },
  {
    label: "Checks",
    name: DIFF_TABS.CHECKS
  },
  {
    label: "Artifacts",
    name: DIFF_TABS.ARTIFACTS
  },
  {
    label: "Schema",
    name: DIFF_TABS.SCHEMA
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch(tab) {
    case DIFF_TABS.DATA: {
      return <DataDiff />;
    }
    default: {
      return null;
    }
  }
};

export const Diff = () => {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  return (
    <div>
      <div>
        <Tabs tabs={tabs} />
      </div>

      <div>
        {
          renderContent(qspTab)
        }
      </div>
    </div>
  );
};