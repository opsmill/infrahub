import { useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import getDataDiff from "../../../graphql/queries/branches/getDataDiff";
import { DataDiffNode } from "./data-diff-node";

export const DataDiff = () => {
  const { branchname } = useParams();
  const [diff, setDiff] = useState({} as any);
  console.log("diff: ", diff);

  const fetchDiffDetails = useCallback(
    async () => {
      if (!branchname) return;

      try {
        const options = {
          branch: branchname
        };

        const diffDetails = await getDataDiff(options);

        setDiff(diffDetails);
      } catch(err) {
        console.error("err: ", err);
      }
    }, [branchname]
  );

  useEffect(
    () => {
      fetchDiffDetails();
    },
    [fetchDiffDetails]
  );

  return (
    <div>
      {
        diff?.nodes?.map((node: any, index: number) => <DataDiffNode key={index} node={node} />)
      }
    </div>
  );
};