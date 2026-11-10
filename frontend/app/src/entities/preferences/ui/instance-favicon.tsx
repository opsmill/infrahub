import { useEffect } from "react";

import infrahubMarkSvg from "@/assets/infrahub-mark.svg?raw";

import { useConfig } from "@/entities/config/ui/config-provider";
import { instanceFaviconColor } from "@/entities/preferences/domain/rules/instance-color";
import { recolorInfrahubMark } from "@/entities/preferences/domain/rules/recolor-infrahub-mark";

export function InstanceFavicon() {
  const faviconColor = instanceFaviconColor(useConfig().instance.color);

  useEffect(() => {
    const favicon = document.head.querySelector<HTMLLinkElement>('link[rel="icon"]');
    const originalHref = favicon?.getAttribute("href");
    if (!favicon || !originalHref || !faviconColor) {
      return;
    }

    const svg = recolorInfrahubMark(infrahubMarkSvg, faviconColor);
    favicon.setAttribute("href", `data:image/svg+xml,${encodeURIComponent(svg)}`);
    return () => {
      favicon.setAttribute("href", originalHref);
    };
  }, [faviconColor]);

  return null;
}
