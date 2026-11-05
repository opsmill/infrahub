import { useEffect } from "react";

import { useConfig } from "@/entities/config/ui/config-provider";
import { formatDocumentTitle } from "@/entities/preferences/domain/rules/format-document-title";

const APPLICATION_TITLE = "Infrahub";

export const useTitle = (title: string) => {
  const { label } = useConfig().instance;
  const documentTitle = formatDocumentTitle(label, title);
  const fallbackTitle = formatDocumentTitle(label, APPLICATION_TITLE);

  useEffect(() => {
    document.title = documentTitle;

    // The fallback is recomputed per effect run so a label changed while the page was open never resurfaces stale.
    return () => {
      document.title = fallbackTitle;
    };
  }, [documentTitle, fallbackTitle]);
};
