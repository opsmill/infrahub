export const TimelineBorder = () => {
  return (
    <div className="relative last:after:hidden after:absolute after:top-8 after:bottom-0 after:start-3.5 after:w-px after:-translate-x-[0.5px] after:bg-custom-blue-500">
      <div className="relative z-10 size-7 flex justify-center items-center">
        <div className="size-2 rounded-full bg-custom-blue-500"></div>
      </div>
    </div>
  );
};
