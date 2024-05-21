import MultipleProgressBar, {
  MultipleProgressBarProps,
} from "../../../components/stats/multiple-progress-bar";
import { classNames } from "../../../utils/common";

interface ResourcePoolUtilizationProps extends Omit<MultipleProgressBarProps, "elements"> {
  utilizationOverall: number;
  utilizationDefaultBranch: number;
}

const ResourcePoolUtilization = ({
  utilizationDefaultBranch,
  utilizationOverall,
  className,
  ...props
}: ResourcePoolUtilizationProps) => {
  const utilizationOtherBranches = utilizationOverall - utilizationDefaultBranch;

  return (
    <MultipleProgressBar
      className={classNames("h-3", className)}
      elements={[
        {
          value: utilizationOverall,
          tooltip: (
            <ResourceUtilizationTooltipContent
              value={utilizationOverall}
              description="The overall utilization of the pool isolated to the default branch"
            />
          ),
        },
        {
          value: utilizationOtherBranches,
          tooltip: (
            <ResourceUtilizationTooltipContent
              value={utilizationOtherBranches}
              description="The utilization of the pool across all branches aside from the default one"
            />
          ),
        },
      ]}
      {...props}
    />
  );
};

const ResourceUtilizationTooltipContent = ({
  value,
  description,
}: {
  value: string | number;
  description: string;
}) => {
  return (
    <div>
      <p className="text-xs">value : {value}%</p>
      <p className="text-xxs">{description}</p>
    </div>
  );
};

export default ResourcePoolUtilization;
