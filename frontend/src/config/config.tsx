export const CONFIG = {
  BACKEND_URL: (branch: string = "main", time?: Date) => {
    return `http://localhost:8000/graphql/${branch}`;
  },
};