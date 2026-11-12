const DOCUMENT_TITLE_SEPARATOR = " · ";

export function formatDocumentTitle(label: string | null, pageTitle: string): string {
  return label ? `${label}${DOCUMENT_TITLE_SEPARATOR}${pageTitle}` : pageTitle;
}
