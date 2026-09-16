import type { Point } from "./sampleFunction";

export function rmse(target: Point[], player: Point[]) {
  const length = Math.min(target.length, player.length);

  if (length === 0) {
    return Infinity;
  }

  let total = 0;

  for (let i = 0; i < length; i++) {
    const diff = target[i].y - player[i].y;
    total += diff * diff;
  }

  return Math.sqrt(total / length);
}
