type TooltipProps = {
  children: any;
  message: string;
}

export const Tooltip = (props: TooltipProps) => {
  return (
    <div className="group relative flex cursor-pointer">
      {props.children}
      <span className="absolute z-10 top-5 left-1/2 transform -translate-x-1/2 scale-0 transition-all rounded bg-gray-800 p-2 text-xs text-white group-hover:scale-100 text-center">{props.message}</span>
    </div>
  );
};