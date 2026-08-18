// The vocabulary of the planned account-level theme preference; nothing persists these values yet.
// SYSTEM is a stored choice, not an absence: null means "nothing set at this layer", so conflating
// the two would leave a user unable to return to system-following once they had picked anything.

export type ThemeChoice = "LIGHT" | "DARK" | "SYSTEM";
