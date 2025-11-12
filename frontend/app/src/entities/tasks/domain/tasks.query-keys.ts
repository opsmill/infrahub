export const tasksQueryKeys = {
  all: ["tasks"] as const,
  states: (states?: string[]) => [...(states ?? [])],
};
