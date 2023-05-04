import { Tabs } from "../../../components/tabs";
import { StringParam, useQueryParam } from "use-query-params";
import { DataDiff } from "./data-diff";
import { QSP } from "../../../config/qsp";
import { SchemaDiff } from "./schema-diff";

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
  // {
  //   label: "Conversation",
  //   name: DIFF_TABS.CONVERSATIONS
  // },
  // {
  //   label: "Status",
  //   name: DIFF_TABS.STATUS
  // },
  {
    label: "Data",
    name: DIFF_TABS.DATA
  },
  {
    label: "Files",
    name: DIFF_TABS.FILES
  },
  // {
  //   label: "Checks",
  //   name: DIFF_TABS.CHECKS
  // },
  // {
  //   label: "Artifacts",
  //   name: DIFF_TABS.ARTIFACTS
  // },
  {
    label: "Schema",
    name: DIFF_TABS.SCHEMA
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch(tab) {
    case DIFF_TABS.FILES:
      // return <FilesDiff />;
      return null;
    case DIFF_TABS.SCHEMA:
      return <SchemaDiff />;
    default:
      return <DataDiff />;
  }
};

export const Diff = () => {
  const [qspTab] = useQueryParam(QSP.BRANCH_DIFF_TAB, StringParam);

  return (
    <div>
      <div>
        <Tabs tabs={tabs} qsp={QSP.BRANCH_DIFF_TAB}/>
      </div>

      <div>
        {
          renderContent(qspTab)
        }
      </div>
    </div>
  );
};