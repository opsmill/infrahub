export interface ScopeCandidate {
  name: string;
  label: string;
  type: "attribute" | "relationship";
  detail: string;
  unavailableReason?: string;
}
