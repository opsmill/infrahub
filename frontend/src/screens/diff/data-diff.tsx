import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import {
  createContext,
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { Button } from "../../components/buttons/button";
import { Checkbox } from "../../components/inputs/checkbox";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { CONFIG } from "../../config/config";
import { PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getThreadsAndChecks } from "../../graphql/queries/proposed-changes/getThreadsAndChecks";
import useQuery from "../../hooks/useQuery";
import { proposedChangedState } from "../../state/atoms/proposedChanges.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { fetchUrl, getUrlWithQsp } from "../../utils/fetch";
import LoadingScreen from "../loading-screen/loading-screen";
import { DataDiffNode, tDataDiffNode } from "./data-diff-node";

type tDiffContext = {
  refetch?: Function;
  node?: tDataDiffNode;
  currentBranch?: string;
  checksDictionnary?: any;
};

export const DiffContext = createContext<tDiffContext>({});

const constructChecksDictionnary = (checks: any[]) => {
  // Flatten all the checks from all validators
  const totalChecks = checks
    ?.map((validator: any) => validator?.edges?.map((edge: any) => edge?.node))
    .reduce((acc, elem) => [...acc, ...elem], []);

  // Construct with path as key and check as value
  const dictionnary = totalChecks?.reduce((acc: any, elem: any) => {
    // For each path, get { path1: [check1, check2], path2: [check3], ... }
    const paths = elem?.conflicts?.value?.reduce((acc2: any, conflict: any) => {
      return {
        ...acc2,
        [conflict.path]: [...(acc[conflict.path] || []), elem],
      };
    }, {});

    return {
      ...acc,
      ...paths,
    };
  }, {});

  return dictionnary;
};

export const DataDiff = forwardRef((props, ref) => {
  const { branchname, proposedchange } = useParams();

  const [branchOnly, setBranchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const [proposedChangesDetails] = useAtom(proposedChangedState);
  const [schemaList] = useAtom(schemaState);
  const [diff, setDiff] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const branch = branchname || proposedChangesDetails?.source_branch?.value;

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  const queryString = schemaData
    ? getThreadsAndChecks({
        id: proposedchange,
        kind: schemaData.kind,
        conflicts: branchOnly === "false",
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { data, refetch } = useQuery(query, { skip: !schemaData });

  // Get the comments count per object path like { [path]: [count] }, and include all sub path for each object
  const objectComments = data?.[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges
    .map((edge: any) => edge.node)
    .reduce((acc: any, node: any) => {
      const objectPathResult = node?.object_path?.value?.match(/^\w+\/(\w|-)+/g);

      const objectPath = objectPathResult && objectPathResult[0];

      if (!objectPath) {
        return;
      }

      return {
        ...acc,
        // Count all comments for this object (will include comments on sub nodes)
        [objectPath]: (acc[objectPath] ?? 0) + (node?.comments?.count ?? 0),
      };
    }, {});

  const checks = data?.CoreValidator?.edges?.map((edge: any) => edge?.node?.checks);

  const checksDictionnary = constructChecksDictionnary(checks);

  const fetchDiffDetails = useCallback(async () => {
    if (!branch) return;

    setIsLoading(true);

    const url = CONFIG.DATA_DIFF_URL(branch);

    const options: string[][] = [
      ["branch_only", branchOnly ?? "true"], // default will be branch only
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const urlWithQsp = getUrlWithQsp(url, options);

    try {
      const diffDetails = await fetchUrl(urlWithQsp);

      setDiff(diffDetails.diffs ?? []);
    } catch (err) {
      console.error("Error when fethcing branches: ", err);

      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading branch diff" />);
    }

    setIsLoading(false);
  }, [branchname, branchOnly, timeFrom, timeTo]);

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch: fetchDiffDetails }));

  useEffect(() => {
    fetchDiffDetails();
  }, [fetchDiffDetails]);

  const renderNode = (node: any, index: number) => {
    // Provide threads and comments counts to display in the top level node
    const commentsCount = objectComments && objectComments[node?.path];

    const currentBranch =
      branch ?? branchname ?? proposedChangesDetails?.source_branch?.value ?? "main";

    const context = {
      currentBranch,
      // Provides refetch function to update count on comment
      refetch,
      // Provides full node information
      node,
      // Provides all the checks results
      checksDictionnary,
    };

    return (
      <DiffContext.Provider key={index} value={context}>
        <DataDiffNode node={node} commentsCount={commentsCount} />
      </DiffContext.Provider>
    );
  };

  return (
    <>
      <div className="flex items-center p-4 bg-custom-white">
        <div className="mr-2">
          <Button onClick={() => setBranchOnly(branchOnly !== "false" ? "false" : "true")}>
            <span className="mr-2">Display main</span>

            <Checkbox enabled={branchOnly === "false"} readOnly />
          </Button>
        </div>

        {branchOnly === "false" && (
          <div className="flex items-center">
            <span className="mr-2">Branches colours:</span>
            <div className={"rounded-lg shadow px-2 mr-2 bg-custom-blue-10"}>main</div>
            <div className={"rounded-lg shadow px-2 bg-green-200"}>{branch}</div>
          </div>
        )}
      </div>

      {isLoading ? (
        <LoadingScreen />
      ) : (
        <div className="text-xs" data-cy="data-diff">
          {diff?.map(renderNode)}
        </div>
      )}
    </>
  );
});
