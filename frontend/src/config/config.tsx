export const CONFIG = {
  BACKEND_URL: (branch: string = "main", time?: Date | null) => {
    let endpoint: string;
    if(!time) {
      endpoint = `http://localhost:8000/graphql/${branch}`;
    } else {
      endpoint = `http://localhost:8000/graphql/${branch}?at=${time.toISOString()}`;
    }
    return endpoint;
  },
};