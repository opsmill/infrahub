import { ArrowPathIcon, CheckCircleIcon, ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { Badge } from "../../../components/badge";
import { Retry } from "../../../components/retry";
import { PROPOSED_CHANGES_VALIDATOR_OBJECT } from "../../../config/constants";
import { genericsState } from "../../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../../state/atoms/schemaKindName.atom";
import { getValidatorsStats } from "../../../utils/checks";

type tChecksSummaryProps = {
  validators: any[];
};

export const ChecksSummary = (props: tChecksSummaryProps) => {
  const { validators } = props;

  const [schemaKindName] = useAtom(schemaKindNameState);
  const [schemaList] = useAtom(genericsState);

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_VALIDATOR_OBJECT);

  const validatorKinds = schemaData?.used_by ?? [];

  const validatorsCount = validatorKinds.reduce((acc, kind) => {
    const relatedValidators = validators.filter((validator: any) => validator.__typename === kind);

    return { ...acc, [schemaKindName[kind]]: getValidatorsStats(relatedValidators) };
  }, {});

  return (
    <div className="flex p-4 pb-0">
      <div className="flex items-center justify-between p-2 mr-2 rounded-md bg-custom-white">
        Retry all: <Retry />
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-4 gap-2 items-center justify-between">
        {Object.entries(validatorsCount).map(([kind, stats]: [string, any]) => (
          <div
            key={kind}
            className="flex flex-1 items-center justify-between p-2 rounded-md bg-custom-white">
            <Badge>{kind}</Badge>

            <div className="flex items-center mr-2">
              <div className="flex items-center mr-2">
                {!!stats.failure && <ExclamationCircleIcon className="mr-2 h-4 w-4 text-red-500" />}

                {!!stats.inProgress && (
                  <ArrowPathIcon className="mr-2 h-4 w-4 text-orange-500 animate-spin" />
                )}

                {!stats.failure && !stats.inProgress && (
                  <CheckCircleIcon className="mr-2 h-4 w-4 text-green-500" />
                )}

                <span>
                  {JSON.stringify(stats.success)}/{JSON.stringify(stats.total)}
                </span>
              </div>
            </div>

            <Retry />
          </div>
        ))}
      </div>
    </div>
  );
};
