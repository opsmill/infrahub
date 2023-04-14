import { useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { DataDiffNode } from "./data-diff-node";
import { CONFIG } from "../../../config/config";
import { fetchUrl } from "../../../utils/fetch";

export const DataDiff = () => {
  const { branchname } = useParams();
  const [diff, setDiff] = useState([]);

  const fetchDiffDetails = useCallback(
    async () => {
      if (!branchname) return;

      try {
        const diffDetails = await fetchUrl(CONFIG.DIFF_URL(branchname));

        setDiff(diffDetails[branchname] ?? []);
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
        diff?.map((node: any, index: number) => <DataDiffNode key={index} node={node} />)
      }
    </div>
  );
};