import { classNames } from "@/shared/utils/common";

const STYLES = [
  "bg-green-50 text-green-600",
  "bg-yellow-50 text-yellow-600",
  "bg-indigo-50 text-indigo-600",
  "bg-orange-50 text-orange-600",
  "bg-pink-50 text-pink-600",
  "bg-purple-50 text-purple-600",
  "bg-blue-50 text-blue-600",
];

export function MenuItemAvatar({ name = "" }: { name: string }) {
  const firstLetter = name[0];
  if (!firstLetter) {
    return <div className="flex h-6 w-6 items-center justify-center rounded-sm bg-gray-100" />;
  }

  const styleIndex = firstLetter.charCodeAt(0) % STYLES.length;
  return (
    <div
      className={classNames(
        "flex h-6 w-6 items-center justify-center rounded-sm",
        STYLES[styleIndex]
      )}
    >
      {firstLetter.toUpperCase()}
    </div>
  );
}
