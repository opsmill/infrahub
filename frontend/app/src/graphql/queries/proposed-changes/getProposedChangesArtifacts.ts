export const getProposedChangesArtifacts = `
query GET_PROPOSED_CHANGES_ARTIFACTS($id: ID) {
  CoreArtifact(object__ids: [$id]) {
    count
  }
}
`;
