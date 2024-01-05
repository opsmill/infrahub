import { Pill } from "../../components/display/pill";

type DiffPillProps = {
  added?: number;
  updated?: number;
  removed?: number;
  hidden?: boolean;
};

export const DiffPill = (props: DiffPillProps) => {
  const { added, updated, removed, hidden } = props;

  if (hidden) {
    return (
      <div className="lg:flex items-center text-gray-300 mr-2 w-[85px] text-sm font-normal hidden lg:visible" />
    );
  }

  return (
    <Pill className="flex items-center text-gray-300 mr-2 w-[85px] text-sm font-normal">
      <span className="text-green-600 mr-1">+{added ?? 0}</span>|
      <span className="text-yellow-500 mx-1">{updated ?? 0}</span>|
      <span className="text-red-600 ml-1">-{removed ?? 0}</span>
    </Pill>
  );
};
