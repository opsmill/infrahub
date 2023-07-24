import { StringParam, useQueryParam } from "use-query-params";
import { Tabs } from "../../components/tabs";
import { QSP } from "../../config/qsp";
import { DataDiff } from "../branches/diff/data-diff";
import { DIFF_TABS } from "../branches/diff/diff";
import { FilesDiff } from "../branches/diff/files-diff";
import { SchemaDiff } from "../branches/diff/schema-diff";
import { Conversations } from "./conversations";

export const PROPOSED_CHANGES_TABS = {
  CONVERSATIONS: "conversations",
};

const tabs = [
  {
    label: "Conversations",
    name: PROPOSED_CHANGES_TABS.CONVERSATIONS,
  },
  {
    label: "Data",
    name: DIFF_TABS.DATA,
  },
  {
    label: "Files",
    name: DIFF_TABS.FILES,
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
    case DIFF_TABS.DATA:
      return <DataDiff />;
    default: {
      return <Conversations />;
    }
  }
};

export const ProposedChangesDetails = () => {
  const [qspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);

  return (
    <div>
      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      {renderContent(qspTab)}
    </div>
  );
};
