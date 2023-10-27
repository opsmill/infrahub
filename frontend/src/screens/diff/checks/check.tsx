import { gql } from "@apollo/client";
import {
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { Link } from "../../../components/link";
import { PopOver } from "../../../components/popover";
import { Tooltip } from "../../../components/tooltip";
import { QSP } from "../../../config/qsp";
import { getCheckDetails } from "../../../graphql/queries/diff/getCheckDetails";
import useQuery from "../../../hooks/useQuery";
import { schemaKindNameState } from "../../../state/atoms/schemaKindName.atom";
import { classNames } from "../../../utils/common";
import { constructPath } from "../../../utils/fetch";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { DIFF_TABS } from "../diff";
import { Conflict } from "./conflict";

type tCheckProps = {
  id: string;
};

const getCheckIcon = (conclusion?: string) => {
  switch (conclusion) {
    case "success": {
      return <CheckCircleIcon className="mr-2 h-6 w-6 text-green-500" />;
    }
    case "failure": {
      return <ExclamationCircleIcon className="mr-2 h-6 w-6 text-red-500" />;
    }
    default: {
      return <ExclamationTriangleIcon className="mr-2 h-6 w-6 text-yellow-500" />;
    }
  }
};

const getCheckBorderColor = (severity?: string) => {
  switch (severity) {
    case "success": {
      return "border-green-400";
    }
    case "info": {
      return "border-yellow-500";
    }
    case "warning": {
      return "border-orange-500";
    }
    case "error": {
      return "border-red-300";
    }
    case "critical": {
      return "border-red-600";
    }
    default: {
      return "border-yellow-400";
    }
  }
};

const getCheckData = (check: any) => {
  const { __typename } = check;

  switch (__typename) {
    case "CoreDataCheck": {
      const { conflicts } = check;

      return (
        <div>
          <div>
            {conflicts?.value?.map((conflict: any, index: number) => (
              <Conflict key={index} {...conflict} />
            ))}
          </div>

          {/* <div className="mt-2 flex flex-1">
            <Button className="mr-2">Keep data from main</Button>

            <Button>Keep data from branch</Button>
          </div> */}
        </div>
      );
    }
    default: {
      return null;
    }
  }
};

export const Check = (props: tCheckProps) => {
  const { id } = props;

  const [schemaKindName] = useAtom(schemaKindNameState);
  const { proposedchange } = useParams();
  const [qspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);

  const queryString = getCheckDetails({
    id,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query);

  const check = data?.CoreCheck?.edges?.[0]?.node ?? {};

  const {
    __typename,
    kind,
    origin,
    created_at,
    display_label,
    name,
    message,
    severity,
    conclusion,
    validator,
  } = check;

  const MoreButton = (
    <div className="p-1 cursor-pointer">
      <QuestionMarkCircleIcon className="h-6 w-6 text-custom-blue-green" aria-hidden="true" />
    </div>
  );

  // Redirection to access the checks in the validator details view
  const checkParams: [string, string][] = [
    [QSP.PROPOSED_CHANGES_TAB, DIFF_TABS.CHECKS],
    [QSP.VALIDATOR_DETAILS, validator?.node?.id],
  ];

  // Redirection to access the data diff view, with both branches
  const dataParams: [string, string][] = [
    [QSP.PROPOSED_CHANGES_TAB, DIFF_TABS.DATA],
    [QSP.BRANCH_FILTER_BRANCH_ONLY, "false"],
  ];

  const newParams: [string, string][] =
    qspTab !== DIFF_TABS.CHECKS && validator?.node?.id ? checkParams : dataParams;

  const url = constructPath(`/proposed-changes/${proposedchange}`, newParams);

  const tooltipMessage =
    qspTab !== DIFF_TABS.CHECKS ? "Open validator in checks view" : "Open diff view";

  const renderContent = () => {
    return (
      <div>
        <div className="flex mb-1">
          <span className="flex-1">Type:</span>

          <Badge className="flex-1">{schemaKindName[__typename]}</Badge>
        </div>

        <div className="flex mb-1">
          <span className="flex-1">Kind:</span>

          <Badge className="flex-1">{kind?.value}</Badge>
        </div>

        <div className="flex">
          <span className="flex-1">Origin:</span>

          <Badge className="flex-1">{origin?.value}</Badge>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className={"flex flex-col rounded-md p-2 bg-custom-white border-l-4"}>
        <LoadingScreen />
      </div>
    );
  }

  if (error) {
    return (
      <div className={"flex flex-col rounded-md p-2 bg-custom-white border-l-4"}>
        <ErrorScreen message="Something went wrong when fetching the check details" />
      </div>
    );
  }

  return (
    <div
      className={classNames(
        "flex flex-col rounded-md p-2 bg-custom-white border-l-4",
        getCheckBorderColor(severity?.value)
      )}>
      <div className="flex mb-2">
        <div className="flex flex-1 flex-col mr-2">
          <div className="flex items-center">
            {getCheckIcon(conclusion?.value)}

            {name?.value || display_label}

            <div className="ml-2">
              <Tooltip message={tooltipMessage}>
                <Link to={url} target="_blank">
                  <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                </Link>
              </Tooltip>
            </div>
          </div>

          <div className="flex items-center justify-center min-h-[50px]">
            {message?.value}

            {!message?.value && <span className="italic text-gray-400">Empty message</span>}
          </div>
        </div>

        <div className="flex flex-col justify-start">
          <div className="flex items-center">
            <DateDisplay date={created_at?.value} />

            <PopOver buttonComponent={MoreButton}>{renderContent}</PopOver>
          </div>
        </div>
      </div>

      <div>
        <div className="border-t-2 border-gray-100 mb-2 rounded-md" />

        {getCheckData(check)}
      </div>
    </div>
  );
};
