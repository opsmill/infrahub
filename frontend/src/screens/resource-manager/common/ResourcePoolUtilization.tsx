import MultipleProgressBar, {
  MultipleProgressBarProps,
} from "../../../components/stats/multiple-progress-bar";
import { classNames } from "../../../utils/common";

interface ResourcePoolUtilizationProps extends Omit<MultipleProgressBarProps, "elements"> {
  utilizationDefaultBranch: number;
  utilizationOtherBranches: number;
}

const ResourcePoolUtilization = ({
  utilizationDefaultBranch,
  utilizationOtherBranches,
  className,
  ...props
}: ResourcePoolUtilizationProps) => {
  return (
    <MultipleProgressBar
      className={classNames("h-3", className)}
      elements={[
        {
          value: utilizationDefaultBranch,
          tooltip: (
            <ResourceUtilizationTooltipContent
              value={utilizationDefaultBranch}
              description="The overall utilization of the pool isolated to the default branch"
            />
          ),
          color: "#0987a8",
        },
        {
          value: utilizationOtherBranches,
          tooltip: (
            <ResourceUtilizationTooltipContent
              value={utilizationOtherBranches}
              description="The utilization of the pool across all branches aside from the default one"
            />
          ),
          color: "#54b6cf",
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
