export const resolveConflict = `
mutation RESOLVE_CONFLICT ($id: String, $selection: ConflictSelection) {
  ResolveDiffConflict(data:{conflict_id: $id, selected_branch: $selection}){
    ok
  }
}
`;
