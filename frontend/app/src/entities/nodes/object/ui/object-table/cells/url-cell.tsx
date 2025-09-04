import { Icon } from "@iconify-icon/react";

import { TextAttribute } from "@/shared/api/graphql/generated/graphql";

export function UrlCell({ url }: { url: TextAttribute }) {
  if (!url.value) return "-";

  return (
    <a
      href={url.value}
      target="_blank"
      rel="noreferrer"
      className="cursor-pointer text-blue-600 py-1 px-2 rounded-full inline-flex items-center hover:underline"
    >
      <span className="truncate">{url.value}</span>
      <Icon icon="mdi:open-in-new" className="ml-0.5" />
    </a>
  );
}
