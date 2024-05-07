// type ButtonProps = {};

import { classNames } from "../../utils/common";
import { forwardRef } from "react";
import { ButtonProps } from "./button";

export enum BUTTON_TYPES {
  DEFAULT,
  VALIDATE,
  CANCEL,
  WARNING,
}

const DEFAULT_CLASS = (className?: string) => `
  ${className?.includes("p-") ? "" : "p-2"}
  inline-flex items-center gap-x-1.5 rounded-full
  text-sm font-semibold
  focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
  shadow-sm ring-1 ring-inset ring-gray-300
`;

const getClassName = (type: BUTTON_TYPES) => {
  switch (type) {
    case BUTTON_TYPES.VALIDATE: {
      return `
        bg-green-500 text-gray-50
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
    case BUTTON_TYPES.DEFAULT: {
      return `
      bg-gray-100 text-gray-900
      hover:bg-gray-200
      disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 disabled:border-slate-200 disabled:shadow-none
    `;
    }
    default: {
      return "disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 disabled:border-slate-200 disabled:shadow-none";
    }
  }
};

export const RoundedButton = forwardRef<HTMLButtonElement, ButtonProps>((props: any, ref) => {
  const { type, className, onClick, ...propsToPass } = props;

  const customClassName = getClassName(type);

  return (
    <button
      ref={ref}
      type="button"
      className={classNames(DEFAULT_CLASS(className), customClassName, className)}
      onClick={onClick}
      {...propsToPass}>
      {props.children}
    </button>
  );
});
