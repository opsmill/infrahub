interface GetRelationshipMutationParams {
  id: string;
  data: Record<string, Array<{ id: string }>>;
  mutation: string;
}

export const getRelationshipMutation = ({ id, data, mutation }: GetRelationshipMutationParams) => {
  return Object.entries(data).reduce((acc, [fieldName, fieldValue]) => {
    return {
      ...acc,
      [`${mutation}_${fieldName}`]: {
        __aliasFor: mutation,
        __args: {
          data: {
            id,
            name: fieldName,
            nodes: fieldValue,
          },
        },
        ok: true,
      },
    };
  }, {});
};
