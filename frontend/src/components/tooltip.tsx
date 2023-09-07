type TooltipProps = {
  children: any;
  message: any;
};

export const Tooltip = (props: TooltipProps) => {
  return (
    <div className={"group/tooltip relative flex cursor-pointer"}>
      {props.children}
      <span
        className={`absolute hidden z-10 top-8 left-1/2 transform -translate-x-1/2
          transition delay-1000 duration-300
          px-3 py-2
          text-sm font-medium text-white text-center
          bg-gray-600 rounded-lg shadow-sm opacity-0
          group-hover/tooltip:opacity-100 group-hover/tooltip:inline-block`}>
        {props.message}
      </span>
    </div>
  );
};
