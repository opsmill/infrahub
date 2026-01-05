export const TimelineBorder = () => {
  return (
    <div className="after:-top-2 after:-bottom-2 after:-translate-x-[0.5px] relative after:absolute after:start-2 after:w-px after:bg-custom-blue-500 last:after:hidden">
      <div className="relative flex size-4 items-center justify-center">
        <div className="absolute top-3 size-2 rounded-full bg-custom-blue-500"></div>
      </div>
    </div>
  );
};
