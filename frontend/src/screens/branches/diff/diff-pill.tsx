import { Pill } from "../../../components/pill";

type DiffPillProps = {
  added?: number;
  updated?: number;
  removed?: number;
}

export const DiffPill = (props: DiffPillProps) => {
  const { added, updated, removed} = props;

  return (
    <Pill className="flex items-center text-gray-300 mr-2">
      <span className="text-green-600 mr-1">+{added ?? 0}</span>|<span className="text-yellow-500 mx-1">{updated ?? 0}</span>|<span className="text-red-600 ml-1">-{removed ?? 0}</span>
    </Pill>
  );
};