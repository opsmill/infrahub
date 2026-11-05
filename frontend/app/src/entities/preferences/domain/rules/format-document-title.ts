import { DOCUMENT_TITLE_SEPARATOR } from "@/entities/preferences/domain/model/instance-identity";
import { normalizeInstanceLabel } from "@/entities/preferences/domain/rules/validate-instance-label";

export function formatDocumentTitle(label: string | null | undefined, pageTitle: string): string {
  const instanceLabel = normalizeInstanceLabel(label ?? "");
  return instanceLabel ? `${instanceLabel}${DOCUMENT_TITLE_SEPARATOR}${pageTitle}` : pageTitle;
}
