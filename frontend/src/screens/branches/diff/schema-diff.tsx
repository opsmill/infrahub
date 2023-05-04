import { useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { DataDiffNode } from "./data-diff-node";
import { CONFIG } from "../../../config/config";
import { fetchUrl } from "../../../utils/fetch";
import { DynamicFieldData } from "../../edit-form-hook/dynamic-control-types";
import { Filters } from "../../../components/filters";
import { QSP } from "../../../config/qsp";
import { StringParam, useQueryParam } from "use-query-params";
import LoadingScreen from "../../loading-screen/loading-screen";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../../components/alert";
import { formatISO, parseISO } from "date-fns";

export const SchemaDiff = () => {
  const { branchname } = useParams();
  const [diff, setDiff] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [branchOnly, setBranchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom, setTimeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo, setTimeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);

  const fields: DynamicFieldData[] = [
    {
      name: "branch_only",
      label: "Branch only",
      type: "switch",
      value: branchOnly === "true",
    },
    {
      name: "time_from",
      label: "Time from",
      type: "datepicker",
      value: timeFrom ? parseISO(timeFrom) : undefined,
    },
    {
      name: "time_to",
      label: "Time to",
      type: "datepicker",
      value: timeTo ? parseISO(timeTo) : undefined,
    },
  ];

  const fetchDiffDetails = useCallback(
    async () => {
      if (!branchname) return;

      setIsLoading(true);

      const url = CONFIG.DATA_DIFF_URL(branchname);

      const options: string[][] = [
        ["branch_only", branchOnly ?? ""],
        ["time_from", timeFrom ?? ""],
        ["time_to", timeTo ?? ""],
      ]
      .filter(
        ([k, v]) => v !== undefined && v !== ""
      );

      const qsp = new URLSearchParams(options);

      const urlWithQsp = `${url}${options.length ? `&${qsp.toString()}` : ""}`;

      try {
        const diffDetails = await fetchUrl(urlWithQsp);

        setDiff(diffDetails[branchname] ?? []);
      } catch(err) {
        console.error("err: ", err);
        toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading branch diff" />);
      }

      setIsLoading(false);
    },
    [branchname, branchOnly, timeFrom, timeTo]
  );

  useEffect(
    () => {
      fetchDiffDetails();
    },
    [fetchDiffDetails]
  );

  const handleSubmit = (data:any) => {
    const { branch_only, time_from, time_to } = data;

    if (branch_only !== undefined) {
      setBranchOnly(branch_only);
    }

    setTimeFrom(time_from ? formatISO(time_from) : undefined);

    setTimeTo(time_to ? formatISO(time_to) : undefined);
  };

  return (
    <>
      {
        isLoading
        && (
          <LoadingScreen />
        )
      }

      {
        !isLoading
        && (
          <>

            <div className="bg-white p-6 flex">
              <Filters fields={fields} onSubmit={handleSubmit} />
            </div>

            <div>

              {
                diff?.map(
                  (node: any, index: number) => <DataDiffNode key={index} node={node} />
                )
              }
            </div>
          </>
        )
      }

    </>
  );
};