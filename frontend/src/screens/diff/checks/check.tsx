import { gql } from "@apollo/client";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";
import { useAtomValue } from "jotai";
import { MoreButton } from "../../../components/buttons/more-button";
import Accordion from "../../../components/display/accordion";
import { DateDisplay } from "../../../components/display/date-display";
import { PopOver } from "../../../components/display/popover";
import { CodeEditor } from "../../../components/editor/code-editor";
import { List } from "../../../components/table/list";
import { getCheckDetails } from "../../../graphql/queries/diff/getCheckDetails";
import useQuery from "../../../hooks/useQuery";
import { schemaKindLabelState } from "../../../state/atoms/schemaKindLabel.atom";
import { classNames } from "../../../utils/common";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
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

const getCheckData = (check: any, refetch: Function) => {
  const { __typename } = check;

  switch (__typename) {
    case "CoreDataCheck": {
      const { id, conflicts } = check;

      return (
        <div>
          <div>
            {conflicts?.value?.map((conflict: any, index: number) => (
              <Conflict key={index} {...conflict} check={check} id={id} refetch={refetch} />
            ))}
          </div>
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

  const schemaKindLabel = useAtomValue(schemaKindLabelState);

  const queryString = getCheckDetails({
    id,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query);

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
  } = check;

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

  const content = getCheckData(check, refetch);

  const columns = [
    {
      name: "type",
      label: "Type",
    },
    {
      name: "kind",
      label: "Kind",
    },
    {
      name: "origin",
      label: "Origin",
    },
  ];

  const row = {
    values: {
      type: schemaKindLabel[__typename],
      kind: kind?.value,
      origin: origin?.value,
    },
  };

  return (
    <div
      className={classNames(
        "flex flex-col rounded-md p-2 bg-gray-50 border border-l-4",
        getCheckBorderColor(severity?.value)
      )}>
      <div className="flex mb-2">
        <div className="flex flex-1 flex-col">
          <div className="flex items-center">
            {getCheckIcon(conclusion?.value)}

            {name?.value || display_label}

            <div className="flex-1 flex justify-end">
              <DateDisplay date={created_at?.value} />

              <PopOver buttonComponent={MoreButton}>
                <List columns={columns} row={row} />
              </PopOver>
            </div>
          </div>

          {message?.value && (
            <div className="mt-2">
              <Accordion title={"Message"}>
                <CodeEditor value={message?.value} disabled dark />
              </Accordion>
            </div>
          )}
        </div>
      </div>

      {content && (
        <div>
          <div className="border-t-2 border-gray-100 mb-2 rounded-md" />

          {content}
        </div>
      )}
    </div>
  );
};
