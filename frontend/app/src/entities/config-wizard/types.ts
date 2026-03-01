export type WizardStep = "welcome" | "credentials" | "repository" | "schemas" | "confirm";

export interface WizardState {
  currentStep: WizardStep;
  credentialId: string | null;
  repositoryId: string | null;
  repositoryName: string | null;
  branchName: string;
  selectedSchemaRefs: string[];
  selectedCollectionRefs: string[];
}

export const INITIAL_WIZARD_STATE: WizardState = {
  currentStep: "welcome",
  credentialId: null,
  repositoryId: null,
  repositoryName: null,
  branchName: "main",
  selectedSchemaRefs: [],
  selectedCollectionRefs: [],
};
