export const getProposedChangesTasks = `
query GET_PROPOSED_CHANGES_TASKS($id: String) {
  InfrahubTask(related_node__ids: [$id]) {
    count
  }
}
`;
