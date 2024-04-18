type tProgressBar = {
  value: number;
};

export default function ProgressBar(props: tProgressBar) {
  const { value } = props;

  return (
    <div className="h-2 w-full bg-gray-300 rounded-full">
      <div
        style={{ width: `${value}%` }}
        className={"h-full bg-custom-blue-500 rounded-full"}></div>
    </div>
  );
}
