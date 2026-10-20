import * as z from "zod";

export const ThemeSchema = z.enum(["system", "light", "dark"]);

export type Theme = z.infer<typeof ThemeSchema>;

/** The palette actually painted: a theme with "system" resolved against the desktop. */
export type ResolvedTheme = Exclude<Theme, "system">;
