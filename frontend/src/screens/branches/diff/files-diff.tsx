import { useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { DataDiffNode } from "./data-diff-node";
import { CONFIG } from "../../../config/config";
import { fetchUrl } from "../../../utils/fetch";
import { QSP } from "../../../config/qsp";
import { StringParam, useQueryParam } from "use-query-params";
import LoadingScreen from "../../loading-screen/loading-screen";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../../components/alert";

export const FilesDiff = () => {
  const { branchname } = useParams();
  const [diff, setDiff] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [branchOnly] = useQueryParam(
    QSP.BRANCH_FILTER_BRANCH_ONLY,
    StringParam
  );
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);

  const fetchDiffDetails = useCallback(async () => {
    if (!branchname) return;

    setIsLoading(true);

    const url = CONFIG.FILES_DIFF_URL(branchname);

    const options: string[][] = [
      ["branch_only", branchOnly ?? ""],
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([k, v]) => v !== undefined && v !== "");

    const qsp = new URLSearchParams(options);

    const urlWithQsp = `${url}${options.length ? `&${qsp.toString()}` : ""}`;

    try {
      const diffDetails = await fetchUrl(urlWithQsp);

      setDiff(diffDetails[branchname] ?? []);
    } catch (err) {
      console.error("err: ", err);
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message="Error while loading branch diff"
        />
      );
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
