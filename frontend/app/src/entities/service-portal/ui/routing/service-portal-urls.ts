// Portal pages always read the default branch, so their URLs never carry the branch or time-travel
// params that `constructPath` forwards.
export const SERVICE_PORTAL_URL = "/service-portal";

export const getServiceEntryUrl = (entryId: string) => `${SERVICE_PORTAL_URL}/entries/${entryId}`;

export const getServiceRequestUrl = (requestId: string) =>
  `${SERVICE_PORTAL_URL}/requests/${requestId}`;
