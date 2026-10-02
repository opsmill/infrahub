declare module "unidiff" {
  interface DiffAsTextOptions {
    context?: number;
  }

  /** Returns the unified diff of two texts, or an empty string when they are identical. */
  export function diffAsText(previous: string, next: string, options?: DiffAsTextOptions): string;
}
