// type InputProps = {}

import { classNames } from "../utils/common";

export const Input = (props: any) => {
  const { className, ...propsToPass } = props;

  return (
    <input
      className={
        classNames(
          `block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400
          border-gray-300 bg-white  focus:border-indigo-500 focus:outline-none
          sm:text-sm sm:leading-6 px-2
          focus:ring-2 focus:ring-inset focus:ring-indigo-600
          disabled:cursor-not-allowed disabled:bg-gray-100
          `,
          className
        )
      }
      {...propsToPass}
    />
  );
};
