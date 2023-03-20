export const API_SERVER_URL = process.env.API_SERVER_URL || "http://localhost:8000"

export const CONFIG = {
  BACKEND_URL: (branch: string = "main", time?: Date | null) => {
    if(!time) {
      return `${API_SERVER_URL}/graphql/${branch}`;
    } else {
      return `${API_SERVER_URL}/graphql/${branch}?at=${time.toISOString()}`;
    }
  },
};