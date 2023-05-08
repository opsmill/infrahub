import { classNames } from "../utils/common";

// type BadgeProps = {}

export enum PILL_TYPES {
  VALIDATE,
  CANCEL,
  WARNING,
}

const DEFAULT_CLASS = `
  flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium
  text-gray-80
`;

const getClasseName = (type: PILL_TYPES) => {
  switch (type) {
    case PILL_TYPES.VALIDATE: {
      return "bg-green-100 ";
    }
    case PILL_TYPES.CANCEL: {
      return "bg-red-100";
    }
    case PILL_TYPES.WARNING: {
      return "bg-yellow-100";
    }
    default: {
      return "bg-gray-100";
    }
  }
};

export const Pill = (props: any) => {
  const customClassName = getClasseName(props.type);

  return (
    <span
      className={classNames(DEFAULT_CLASS, customClassName, props.className)}
    >
      {props.children}
    </span>
  );
};
