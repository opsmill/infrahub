export const servicePortalQueryKeys = {
  all: ["service-portal"] as const,
  catalog: () => [...servicePortalQueryKeys.all, "catalog"] as const,
  request: (params: { requestId: string; branchName?: string }) =>
    [...servicePortalQueryKeys.all, "request", params] as const,
};
