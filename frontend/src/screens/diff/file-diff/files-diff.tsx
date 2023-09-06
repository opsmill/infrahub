import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import "react-diff-view/style/index.css";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../../components/alert";
import { CONFIG } from "../../../config/config";
import { QSP } from "../../../config/qsp";
import { proposedChangedState } from "../../../state/atoms/proposedChanges.atom";
import { fetchUrl } from "../../../utils/fetch";
import LoadingScreen from "../../loading-screen/loading-screen";
import NoDataFound from "../../no-data-found/no-data-found";
import { FileRepoDiff } from "./file-repo-diff";

export const FilesDiff = () => {
  const [filesDiff, setFilesDiff] = useState({});
  const { branchname } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const [isLoading, setIsLoading] = useState(false);
  const [proposedChangesDetails] = useAtom(proposedChangedState);

  const fetchFiles = useCallback(async () => {
    const branch = branchname || proposedChangesDetails?.source_branch?.value;

    if (!branch) return;

    setIsLoading(true);

    const url = CONFIG.FILES_DIFF_URL(branch);

    const options: string[][] = [
      ["branch_only", branchOnly ?? ""],
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const qsp = new URLSearchParams(options);

    const urlWithQsp = `${url}${options.length ? `&${qsp.toString()}` : ""}`;

    try {
      const filesResult = await fetchUrl(urlWithQsp);

      if (filesResult[branch]) {
        setFilesDiff(filesResult[branch]);
      }
    } catch (err) {
      console.error("err: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading filesDiff diff" />);
    }

    setIsLoading(false);
  }, [branchname, branchOnly, timeFrom, timeTo, proposedChangesDetails?.source_branch?.value]);

  const setFilesInState = useCallback(async () => {
    await fetchFiles();
  }, []);

  useEffect(() => {
    setFilesInState();
  }, []);

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!Object.values(filesDiff).length) {
    return <NoDataFound />;
  }

  // const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};

  return (
    <div className="text-sm">
      {Object.values(filesDiff).map((diff, index) => (
        <FileRepoDiff key={index} diff={diff} />
      ))}
    </div>
  );
};
