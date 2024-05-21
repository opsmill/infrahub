import MultipleProgressBar, {
  MultipleProgressBarProps,
} from "../../../components/stats/multiple-progress-bar";
import { classNames } from "../../../utils/common";
import { roundNumber } from "../../../utils/number";

interface ResourcePoolUtilizationProps extends Omit<MultipleProgressBarProps, "elements"> {
  utilizationOverall: number;
  utilizationDefaultBranch: number;
  utilizationOtherBranches: number;
}

const ResourcePoolUtilization = ({
  utilizationOverall,
  utilizationDefaultBranch,
  utilizationOtherBranches,
  className,
  ...props
}: ResourcePoolUtilizationProps) => {
  return (
    <div className="w-full flex gap-1 items-center">
      <MultipleProgressBar
        className={classNames("h-3", className)}
        elements={[
          {
            value: utilizationDefaultBranch,
            tooltip: (
              <ResourceUtilizationTooltipContent
                value={utilizationDefaultBranch}
                description="The overall utilization within the default branch"
              />
            ),
            color: "#0987a8",
          },
          {
            value: utilizationOtherBranches,
            tooltip: (
              <ResourceUtilizationTooltipContent
                value={utilizationOtherBranches}
                description="The utilization of pool within other branches"
              />
            ),
            color: "#54b6cf",
          },
        ]}
        {...props}
      />
      <span className="text-custom-blue-700 font-medium">
        {roundNumber(utilizationOverall, 0)}%
      </span>
    </div>
  );
};

type ResourceUtilizationTooltipContentProps = {
  value: number;
  description: string;
};
const ResourceUtilizationTooltipContent = ({
  value,
  description,
}: ResourceUtilizationTooltipContentProps) => {
  return (
    <div>
      <p className="text-xs">value : {roundNumber(value)}%</p>
      <p className="text-xxs">{description}</p>
    </div>
  );
};

export default ResourcePoolUtilization;
