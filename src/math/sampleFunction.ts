import { ComputeEngine } from "@cortex-js/compute-engine";

export type Point = {
  x: number;
  y: number;
};

const ce = new ComputeEngine();

export function sampleLatex(
  latex: string,
  minX = -10,
  maxX = 10,
  step = 0.05
): Point[] {
  if (!latex.trim()) {
    return [];
  }

  let expr;

  try {
    expr = ce.parse(latex);
  } catch {
    return [];
  }

  const points: Point[] = [];

  const count = Math.round(
    (maxX - minX) / step
  );

  for (let i = 0; i <= count; i++) {
    const x = minX + i * step;

    try {
      const result = expr
        .subs({
          x: ce.number(x),
        })
        .N();

      const value = result.valueOf();

      if (
        typeof value === "number" &&
        Number.isFinite(value)
      ) {
        points.push({
          x,
          y: value,
        });
      }
    } catch {
      // Undefined or non-real at this x.
    }
  }

  return points;
}
