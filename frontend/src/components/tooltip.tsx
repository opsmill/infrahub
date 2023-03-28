export const Tooltip = (props: any) => {
  return (
    <div className="group relative flex">
      {props.children}
      <span className="absolute top-5 left-1/2 transform -translate-x-1/2 scale-0 transition-all rounded bg-gray-800 p-2 text-xs text-white group-hover:scale-100">{props.message}</span>
    </div>
  );
};