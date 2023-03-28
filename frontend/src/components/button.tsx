// type ButtonProps = {};

import { classNames } from "../utils/common";

export enum BUTTON_TYPES {
  VALIDATE,
  CANCEL,
  WARNING,
}

const DEFAULT_CLASS = `
  py-1.5 px-2.5
  inline-flex items-center gap-x-1.5 rounded-md
  text-sm font-semibold
  focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
  shadow-sm ring-1 ring-inset ring-gray-300
`;

const getClasseName = (type: BUTTON_TYPES) => {
  switch(type) {
    case BUTTON_TYPES.VALIDATE: {
      return `
        bg-green-600 text-gray-50
        hover:bg-green-400
        disabled:cursor-not-allowed disabled:bg-green-400 disabled:text-gray-100 disabled:border-slate-200 disabled:shadow-none
      `;
    }
    case BUTTON_TYPES.CANCEL: {
      return `
        bg-red-600 text-gray-50
        hover:bg-red-400
        disabled:cursor-not-allowed disabled:bg-red-400 disabled:text-gray-100 disabled:border-slate-200 disabled:shadow-none
      `;
    }
    case BUTTON_TYPES.WARNING: {
      return `
        bg-yellow-400 text-gray-800
        hover:bg-yellow-300
        disabled:cursor-not-allowed disabled:bg-yellow-200 disabled:text-gray-600 disabled:border-slate-200 disabled:shadow-none
      `;
    }
    default: {
      return `
        bg-gray-100 text-gray-900
        hover:bg-gray-200
        disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 disabled:border-slate-200 disabled:shadow-none
      `;
    }
  }
};

export const Button = (props: any) => {
  const { type, className, ...propsToPass } = props;

  const customClassName = getClasseName(type);

  return (
    <button
      type="button"
      className={
        classNames(
          DEFAULT_CLASS,
          customClassName,
          className
        )
      }
      {...propsToPass}
    >
      {props.children}
    </button>
  );
};