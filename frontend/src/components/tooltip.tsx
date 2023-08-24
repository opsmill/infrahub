type TooltipProps = {
  children: any;
  message: any;
};

const renderGroupId = (message: string) => message.replaceAll(/\W/g, "-");

export const Tooltip = (props: TooltipProps) => {
  return (
    <div className={`group/${renderGroupId(props.message)} relative flex cursor-pointer`}>
      {props.children}
      <span
        className={`absolute visible z-10 top-10 left-1/2 transform -translate-x-1/2 inline-block px-3 py-2 text-sm font-medium text-white transition-opacity delay-1000 duration-300 bg-gray-900 rounded-lg shadow-sm opacity-0 ${renderGroupId(
          props.message
        )} dark:bg-gray-700 group-hover/${renderGroupId(props.message)}:opacity-100 text-center`}>
        {props.message}
      </span>
    </div>
  );
};
