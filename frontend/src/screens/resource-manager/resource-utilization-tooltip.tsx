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

export default ResourceUtilizationTooltipContent;
