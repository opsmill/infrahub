import { classNames } from "@/utils/common";

const STYLES = [
  "bg-indigo-50 text-indigo-600",
  "bg-red-50 text-red-600",
  "bg-yellow-50 text-yellow-600",
];

export function ObjectAvatar({ name }: { name: string }) {
  const firstLetter = name[0];
  if (!firstLetter) {
    return <div className="w-6 h-6 rounded  flex items-center justify-center bg-gray-100" />;
  }

  const styleIndex = firstLetter.charCodeAt(0) % STYLES.length;
  return (
    <div
      className={classNames("w-6 h-6 rounded flex items-center justify-center", STYLES[styleIndex])}
    >
      {firstLetter.toUpperCase()}
    </div>
  );
}
