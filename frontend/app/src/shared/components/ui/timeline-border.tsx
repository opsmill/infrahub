export const TimelineBorder = () => {
  return (
    <div className="relative last:after:hidden after:absolute after:-top-2 after:-bottom-2 after:start-2 after:w-px after:-translate-x-[0.5px] after:bg-custom-blue-500">
      <div className="relative size-4 flex justify-center items-center">
        <div className="absolute top-3 rounded-full size-2 bg-custom-blue-500"></div>
      </div>
    </div>
  );
};
