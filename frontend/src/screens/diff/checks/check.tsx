import { BADGE_TYPES, Badge } from "../../../components/badge";

type tCheckProps = {
  check: any;
};

const getBadgeType = (value: string) => {
  switch (value) {
    // Severity
    case "success": {
      return BADGE_TYPES.VALIDATE;
    }
    case "warning":
    case "info": {
      return BADGE_TYPES.WARNING;
    }
    case "error":
    case "critical": {
      return BADGE_TYPES.CANCEL;
    }
    // Conclusion
    case "failure": {
      return BADGE_TYPES.CANCEL;
    }
    case "unknown":
    default: {
      return null;
    }
  }
};

export const Check = (props: tCheckProps) => {
  const { check } = props;

  const { name, message, severity, conclusion, paths } = check;
  console.log("paths: ", paths);

  return (
    <div className="flex rounded-md p-2 m-2 bg-custom-white">
      <div>
        <Badge type={getBadgeType(conclusion?.value)}>{conclusion?.value}</Badge>
      </div>

      <div>
        <Badge type={getBadgeType(severity?.value)}>{severity?.value}</Badge>
      </div>

      <div>{name?.value}</div>

      <div>{message?.value}</div>

      <div className="flex flex-col">{paths?.value}</div>
    </div>
  );
};
