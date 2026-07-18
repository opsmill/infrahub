/**
 * Maximum value for the "Max Depth" control in both path-traversal modes.
 * Mirrors the backend cap (`MAX_DEPTH` in the graph-traversal planner); the backend
 * rejects anything above it, so keep the two in sync.
 */
export const MAX_TRAVERSAL_DEPTH = 30;
