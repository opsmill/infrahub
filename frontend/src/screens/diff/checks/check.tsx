import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { PopOver } from "../../../components/popover";
import { schemaKindNameState } from "../../../state/atoms/schemaKindName.atom";
import { classNames } from "../../../utils/common";

type tCheckProps = {
  check: any;
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
      const { paths } = check;
      return (
        <div className="">
          <span className="font-semibold">Paths:</span>
          <ul className="list-disc list-inside ">
            {paths?.value?.map((path: string) => (
              <li key={path}>{path}</li>
            ))}
          </ul>
        </div>
      );
    }
    default: {
      return null;
    }
  }
};

export const Check = (props: tCheckProps) => {
  const { check } = props;

  const [schemaKindName] = useAtom(schemaKindNameState);

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

  const MoreButton = (
    <div className="p-1 cursor-pointer">
      <QuestionMarkCircleIcon className="h-6 w-6 text-custom-blue-green" aria-hidden="true" />
    </div>
  );

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

  return (
    <div
      className={classNames(
        "flex flex-col rounded-md p-2 bg-custom-white border-l-4",
        getCheckBorderColor(severity?.value)
      )}>
      <div className="flex mb-2">
        <div className="flex flex-1 flex-col mr-2">
          <div className="flex">
            {getCheckIcon(conclusion?.value)}

            {name?.value || display_label}
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
