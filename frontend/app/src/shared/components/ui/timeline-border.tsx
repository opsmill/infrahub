export const TimelineBorder = () => {
  return (
    <div className="relative after:absolute after:start-2 after:-top-2 after:-bottom-2 after:w-px after:-translate-x-[0.5px] after:bg-custom-blue-500 last:after:hidden">
      <div className="relative flex size-4 items-center justify-center">
        <div className="absolute top-3 size-2 rounded-full bg-custom-blue-500"></div>
      </div>
    </div>
  );
};
