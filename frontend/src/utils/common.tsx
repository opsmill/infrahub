export function classNames(...classes: string[]) {
  // Replcaa tabs and spaces to have multiline in code, but one ligne in output
  return classes.filter(Boolean).join(" ").replaceAll(/(\t|\s)+/g, " ").trim();
}