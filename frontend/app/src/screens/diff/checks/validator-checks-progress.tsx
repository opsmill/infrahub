import { getChecksStats } from "@/utils/checks";

type tValidatorChecksProgressProps = {
  checks: any[];
};

const getCheckBar = (type: string, amount: number, total: number, index: number) => {
  const precentage = Math.floor((amount / total) * 100);

  switch (type) {
    case "total": {
      return null;
    }
    case "success": {
      return (
        <div
          key={index}
          className="text-xs text-center text-custom-white flex-initial bg-green-500"
          style={{ width: `${precentage}%` }}>
          {amount}
        </div>
      );
    }
    case "info": {
      return (
        <div
          key={index}
          className="text-xs text-center text-custom-white flex-initial bg-yellow-500"
          style={{ width: `${precentage}%` }}>
          {amount}
        </div>
      );
    }
    case "warning": {
      return (
        <div
          key={index}
          className="text-xs text-center text-custom-white flex-initial bg-orange-500"
          style={{ width: `${precentage}%` }}>
          {amount}
        </div>
      );
    }
    case "error": {
      return (
        <div
          key={index}
          className="text-xs text-center text-custom-white flex-initial bg-red-300"
          style={{ width: `${precentage}%` }}>
          {amount}
        </div>
      );
    }
    case "critical": {
      return (
        <div
          key={index}
          className="text-xs text-center text-custom-white flex-initial bg-red-500"
          style={{ width: `${precentage}%` }}>
          {amount}
        </div>
      );
    }
    default: {
      return (
        <div
          key={index}
          className="text-xs text-center text-custom-white flex-initial bg-gray-200"
          style={{ width: `${precentage}%` }}>
          {amount}
        </div>
      );
    }
  }
};

export const ValidatorChecksProgress = (props: tValidatorChecksProgressProps) => {
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

  return (
    <div className="flex flex-1 items-center">
      {Object.entries(checksStats).map(([type, amount], index) =>
        getCheckBar(type, amount, checksStats.total, index)
      )}
    </div>
  );
};
