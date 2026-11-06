import { useAtomValue } from "jotai";
import { useEffect } from "react";

import { pageTitleAtom } from "@/shared/stores/page-title.atom";

import { useConfig } from "@/entities/config/ui/config-provider";
import { formatDocumentTitle } from "@/entities/preferences/domain/rules/format-document-title";

export const APPLICATION_TITLE = "Infrahub";

export function DocumentTitle() {
  const { label } = useConfig().instance;
  const pageTitle = useAtomValue(pageTitleAtom);
  const documentTitle = formatDocumentTitle(label, pageTitle ?? APPLICATION_TITLE);

  useEffect(() => {
    document.title = documentTitle;
  }, [documentTitle]);

  return null;
}
