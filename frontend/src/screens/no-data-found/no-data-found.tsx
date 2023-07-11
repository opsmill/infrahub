type tNoData = {
  message?: string;
};

const DEFAULT_MESSAGE = "Sorry, no data found.";

export default function NoDataFound(props: tNoData) {
  const { message } = props;

  return (
    <div className="p-12 flex flex-col flex-1 items-center justify-center">
      <img
        alt="No data"
        className="h-28 w-auto"
        src="https://thesuccessfinder.com/images/data-not-found-icon.png"
      />
      <div className="pt-2">{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
