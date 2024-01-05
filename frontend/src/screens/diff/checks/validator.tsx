import {
  ArrowPathIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";
import { StringParam, useQueryParam } from "use-query-params";
import { DateDisplay } from "../../../components/display/date-display";
import { QSP } from "../../../config/qsp";
import { ValidatorChecksProgress } from "./validator-checks-progress";

type tValidatorProps = {
  validator: any;
};

const getValidatorState = (state?: string, conclusion?: string) => {
  switch (state) {
    case "queued": {
      return <ClockIcon className="h-6 w-6" />;
    }
    case "in_progress": {
      return <ArrowPathIcon className="h-6 w-6 text-orange-500 animate-spin" />;
    }
    case "completed": {
      if (conclusion === "success") {
        return <CheckCircleIcon className="h-6 w-6 text-green-500" />;
      }

      if (conclusion === "failure") {
        return <ExclamationCircleIcon className="h-6 w-6 text-red-500" />;
      }

      return <ExclamationTriangleIcon className="h-6 w-6 text-yellow-500" />;
    }
    default: {
      return null;
    }
  }
};

export const Validator = (props: tValidatorProps) => {
  const { validator } = props;

  const [, setQsp] = useQueryParam(QSP.VALIDATOR_DETAILS, StringParam);

  const { display_label, started_at, completed_at, conclusion, checks, state } = validator;

  const checksData = checks?.edges?.map((edge: any) => edge?.node);

  return (
    <div
      onClick={() => setQsp(validator.id)}
      className={"flex flex-col rounded-lg shadow p-2 cursor-pointer bg-custom-white"}>
      <div className="flex items-center mt-2">
        <div className="mr-2">{getValidatorState(state?.value, conclusion?.value)}</div>

        <span>{display_label}</span>
      </div>

      <div className="mt-2 flex-1 flex justify-between">
        <span className="mr-1 font-semibold">Started:</span>
        <DateDisplay date={started_at.value} hideDefault />
      </div>

      <div className="mt-2 flex-1 flex justify-between">
        <span className="mr-1 font-semibold">Completed:</span>
        <DateDisplay date={completed_at.value} hideDefault />
      </div>

      <div className="mt-2 flex-1 flex justify-between items-center">
        <span className="flex-1 font-semibold">Checks: </span>
        <ValidatorChecksProgress checks={checksData} />
      </div>
    </div>
  );
};
