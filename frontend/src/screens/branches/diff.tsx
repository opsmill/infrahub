import { useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import getDiff from "../../graphql/queries/branches/getDiff";
import { Tabs } from "../../components/tabs";

const tabs = [
  {
    label: "Conversation",
    name: "conversation"
  },
  {
    label: "Status",
    name: "status"
  },
  {
    label: "Data",
    name: "data"
  },
  {
    label: "Files",
    name: "files"
  },
  {
    label: "Checks",
    name: "checks"
  },
  {
    label: "Artifacts",
    name: "artifacts"
  },
  {
    label: "Schema",
    name: "schema"
  },
];

export const Diff = () => {
  const { branchName } = useParams();

  const [diff, setDiff] = useState({} as any);
  console.log("diff: ", diff);

  const fetchDiffDetails = useCallback(
    async () => {
      if (!branchName) return;

      try {
        const options = {
          branch: branchName
        };

        const diffDetails = await getDiff(options);

        setDiff(diffDetails);
      } catch(err) {
        console.error("err: ", err);
      }
    }, [branchName]
  );

  useEffect(
    () => {
      fetchDiffDetails();
    },
    [fetchDiffDetails]
  );

  return (
    <div>
      <div>
        <Tabs tabs={tabs} />
      </div>
    </div>
  );
};