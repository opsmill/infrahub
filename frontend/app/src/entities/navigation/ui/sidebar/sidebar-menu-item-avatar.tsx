import { classNames } from "@/shared/utils/common";

// A categorical ramp: the hue carries no meaning beyond telling two neighbouring entries apart, so
// no semantic token can stand in for it. The dark variants live here rather than in a token because
// this array is the ramp's only definition — the duplication a token would prevent cannot arise.
const STYLES = [
  "bg-green-50 text-green-700 dark:bg-green-400/15 dark:text-green-300",
  "bg-yellow-50 text-yellow-700 dark:bg-yellow-400/15 dark:text-yellow-300",
  "bg-indigo-50 text-indigo-700 dark:bg-indigo-400/15 dark:text-indigo-300",
  "bg-orange-50 text-orange-700 dark:bg-orange-400/15 dark:text-orange-300",
  "bg-pink-50 text-pink-700 dark:bg-pink-400/15 dark:text-pink-300",
  "bg-purple-50 text-purple-700 dark:bg-purple-400/15 dark:text-purple-300",
  "bg-blue-50 text-blue-700 dark:bg-blue-400/15 dark:text-blue-300",
];

export function SidebarMenuItemAvatar({ name }: { name: string }) {
  const firstLetter = name[0];
  if (!firstLetter) {
    return (
      <div className="flex h-6 w-6 items-center justify-center rounded-sm bg-content-strong" />
    );
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
