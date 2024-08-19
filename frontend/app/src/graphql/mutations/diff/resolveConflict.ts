export const resolveConflict = `
mutation ($uuid: ID, $conflict_selection: String) {
  ResolveDiffConflict(conflict_uuid: $uuid, conflict_selection: $conflict_selection){
    ok
  }
}
`;
