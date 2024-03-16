import { getChecksStats } from "../../../utils/checks";

type tValidatorChecksCounterProps = {
  checks: any[];
};

export const ValidatorChecksCounter = (props: tValidatorChecksCounterProps) => {
  const { checks } = props;

  const checksStats = getChecksStats(checks);

  const isEmpty = !Object.values(checksStats).filter(Boolean).length;

  if (isEmpty) {
    return (
      <div className="flex flex-1 items-center">
        <div className="flex-1 text-xs text-center text-custom-white bg-gray-200">0</div>
      </div>
    );
  }

  return <div className="flex flex-1 items-center">ok</div>;
};
