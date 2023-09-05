import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { CONFIG } from "../../config/config";
import { QSP } from "../../config/qsp";
import { fetchUrl } from "../../utils/fetch";
import LoadingScreen from "../loading-screen/loading-screen";
import { DataDiffNode } from "./data-diff-node";

export const SchemaDiff = () => {
  const { branchname } = useParams();
  const [diff, setDiff] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);

  const fetchDiffDetails = useCallback(async () => {
    if (!branchname) return;

    setIsLoading(true);

    const url = CONFIG.SCHEMA_DIFF_URL(branchname);

    const options: string[][] = [
      ["branch_only", branchOnly ?? ""],
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const qsp = new URLSearchParams(options);

    const urlWithQsp = `${url}${options.length ? `&${qsp.toString()}` : ""}`;

    try {
      const diffDetails = await fetchUrl(urlWithQsp);

      setDiff(diffDetails[branchname] ?? []);
    } catch (err) {
      console.error("err: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading branch diff" />);
    }

    setIsLoading(false);
  }, [branchname, branchOnly, timeFrom, timeTo]);

  useEffect(() => {
    fetchDiffDetails();
  }, [fetchDiffDetails]);

  return (
    <>
      {isLoading && <LoadingScreen />}

      {!isLoading && (
        <div>
          {diff?.map((node: any, index: number) => (
            <DataDiffNode key={index} node={node} />
          ))}
        </div>
      )}
    </>
  );
};
