import { classNames } from "../utils/common";

// type BadgeProps = {}

export enum BADGE_TYPES {
  VALIDATE,
  CANCEL,
  WARNING,
}

const DEFAULT_CLASS = `
  text-sm font-medium mr-2 px-2.5 py-0.5 rounded
`;

const getClasseName = (type: BADGE_TYPES) => {
  switch(type) {
    case BADGE_TYPES.VALIDATE: {
      return "bg-green-600 text-gray-50";
    }
    case BADGE_TYPES.CANCEL: {
      return "bg-red-600 text-gray-50";
    }
    case BADGE_TYPES.WARNING: {
      return "bg-yellow-400 text-gray-800";
    }
    default: {
      return "bg-gray-100 text-gray-900";
    }
  }
};

export const Badge = (props: any) => {
  const customClassName = getClasseName(props.type);

  return (
    <span className={
      classNames(
        DEFAULT_CLASS,
        customClassName,
        props.className
      )
    }>{props.children}</span>
  );

};