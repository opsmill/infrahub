import { Icon } from "@iconify-icon/react";

import type { TextAttribute } from "@/shared/api/graphql/generated/graphql";

export function UrlCell({ url }: { url: TextAttribute }) {
  if (!url.value) return "-";

  return (
    <a
      href={url.value}
      target="_blank"
      rel="noreferrer"
      className="inline-flex cursor-pointer items-center rounded-full px-2 py-1 text-blue-600 hover:underline dark:text-blue-400"
    >
      <span className="truncate">{url.value}</span>
      <Icon icon="mdi:open-in-new" className="ml-0.5" />
    </a>
  );
}
