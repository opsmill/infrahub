type tProgressBar = {
  value: number;
};

const getCleanedValue = (value: number) => {
  if (isNaN(value)) return 0;

  if (value > 100) return 100;

  return value;
};

export default function ProgressBar(props: tProgressBar) {
  const { value } = props;

  const cleanedValue = getCleanedValue(value);

  return (
    <div className="h-2 w-full bg-gray-300 rounded-full">
      <div
        style={{ width: `${cleanedValue}%` }}
        className={"h-full bg-custom-blue-500 rounded-full"}></div>
    </div>
  );
}
