export type InputMode = "basic" | "latex";

export function normalizeInput(
  input: string,
  mode: InputMode
): string {
  if (mode === "latex") {
    return input;
  }

  let value = input.trim();

  value = value
    .replace(/\bsin\s*\(/g, "\\sin(")
    .replace(/\bcos\s*\(/g, "\\cos(")
    .replace(/\btan\s*\(/g, "\\tan(")
    .replace(/\bexp\s*\(/g, "\\exp(")
    .replace(/\blog\s*\(/g, "\\log(");

  value = value.replace(
    /sqrt\(([^()]*)\)/g,
    "\\sqrt{$1}"
  );

  return value;
}
