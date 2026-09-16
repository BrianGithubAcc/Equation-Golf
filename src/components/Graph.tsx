import type { Point } from "../math/sampleFunction";

type Props = {
  target: Point[];
  player: Point[];
  domain?: {
    min: number;
    max: number;
  };
  range?: {
    min: number;
    max: number;
  };
};

type PointPair = {
  target: Point;
  player: Point;
};

const WIDTH = 900;
const HEIGHT = 520;

const PAD_LEFT = 44;
const PAD_RIGHT = 18;
const PAD_TOP = 16;
const PAD_BOTTOM = 34;

const PLOT_X = PAD_LEFT;
const PLOT_Y = PAD_TOP;
const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT;
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM;

export default function Graph({
  target,
  player,
  domain = { min: -10, max: 10 },
  range = { min: -5, max: 5 },
}: Props) {
  const MIN_X = domain.min;
  const MAX_X = domain.max;
  const MIN_Y = range.min;
  const MAX_Y = range.max;

  const ySpan = MAX_Y - MIN_Y;

  function sx(x: number) {
    return (
      PLOT_X +
      ((x - MIN_X) / (MAX_X - MIN_X)) *
        PLOT_W
    );
  }

  function sy(y: number) {
    return (
      PLOT_Y +
      PLOT_H -
      ((y - MIN_Y) / (MAX_Y - MIN_Y)) *
        PLOT_H
    );
  }

  function pointIsDrawable(point: Point) {
    return (
      Number.isFinite(point.x) &&
      Number.isFinite(point.y) &&
      point.y >= MIN_Y - 2 &&
      point.y <= MAX_Y + 2
    );
  }

  function makePath(points: Point[]) {
    let path = "";
    let drawing = false;
    let previous: Point | null = null;

    for (const point of points) {
      if (!pointIsDrawable(point)) {
        drawing = false;
        previous = null;
        continue;
      }

      const jump =
        previous !== null &&
        Math.abs(point.y - previous.y) >
          ySpan * 0.6;

      if (!drawing || jump) {
        path +=
          `M ${sx(point.x)} ${sy(point.y)} `;
        drawing = true;
      } else {
        path +=
          `L ${sx(point.x)} ${sy(point.y)} `;
      }

      previous = point;
    }

    return path;
  }

  function pairToPath(segment: PointPair[]) {
    if (segment.length < 2) {
      return "";
    }

    let path =
      `M ${sx(segment[0].target.x)} ` +
      `${sy(segment[0].target.y)} `;

    for (let i = 1; i < segment.length; i++) {
      const point = segment[i].target;
      path +=
        `L ${sx(point.x)} ${sy(point.y)} `;
    }

    for (
      let i = segment.length - 1;
      i >= 0;
      i--
    ) {
      const point = segment[i].player;
      path +=
        `L ${sx(point.x)} ${sy(point.y)} `;
    }

    path += "Z";
    return path;
  }

  function makeErrorAreas(
    targetPoints: Point[],
    playerPoints: Point[]
  ) {
    const playerByX = new Map<string, Point>();

    for (const point of playerPoints) {
      if (Number.isFinite(point.x)) {
        playerByX.set(
          point.x.toFixed(6),
          point
        );
      }
    }

    const segments: PointPair[][] = [];
    let current: PointPair[] = [];

    function finishSegment() {
      if (current.length >= 2) {
        segments.push(current);
      }
      current = [];
    }

    for (const targetPoint of targetPoints) {
      const playerPoint = playerByX.get(
        targetPoint.x.toFixed(6)
      );

      if (
        !playerPoint ||
        !pointIsDrawable(targetPoint) ||
        !pointIsDrawable(playerPoint)
      ) {
        finishSegment();
        continue;
      }

      const previous =
        current.length > 0
          ? current[current.length - 1]
          : null;

      if (previous) {
        const xGap =
          targetPoint.x -
          previous.target.x;

        const targetJump =
          Math.abs(
            targetPoint.y -
              previous.target.y
          );

        const playerJump =
          Math.abs(
            playerPoint.y -
              previous.player.y
          );

        if (
          xGap > 0.075 ||
          targetJump > ySpan * 0.6 ||
          playerJump > ySpan * 0.6
        ) {
          finishSegment();
        }
      }

      current.push({
        target: targetPoint,
        player: playerPoint,
      });
    }

    finishSegment();

    return segments
      .map(pairToPath)
      .filter(Boolean);
  }

  const errorAreas = makeErrorAreas(
    target,
    player
  );

  const xValues = Array.from(
    {
      length:
        Math.floor(MAX_X - MIN_X) + 1,
    },
    (_, index) =>
      Math.ceil(MIN_X) + index
  ).filter((x) => x <= MAX_X);

  const yValues = Array.from(
    {
      length:
        Math.floor(MAX_Y - MIN_Y) + 1,
    },
    (_, index) =>
      Math.ceil(MIN_Y) + index
  ).filter((y) => y <= MAX_Y);

  const zeroX = sx(0);
  const zeroY = sy(0);

  const xLabelY = Math.min(
    PLOT_Y + PLOT_H - 8,
    Math.max(PLOT_Y + 16, zeroY + 16)
  );

  return (
    <svg
      className="graph"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label="Equation graph"
    >
      <defs>
        <clipPath id="plot-clip">
          <rect
            x={PLOT_X}
            y={PLOT_Y}
            width={PLOT_W}
            height={PLOT_H}
          />
        </clipPath>
      </defs>

      <rect
        width={WIDTH}
        height={HEIGHT}
        className="graph-bg"
      />

      <rect
        x={PLOT_X}
        y={PLOT_Y}
        width={PLOT_W}
        height={PLOT_H}
        className="plot-bg"
      />

      {xValues.map((x) => (
        <line
          key={`x-grid-${x}`}
          x1={sx(x)}
          y1={PLOT_Y}
          x2={sx(x)}
          y2={PLOT_Y + PLOT_H}
          className="grid-line"
        />
      ))}

      {yValues.map((y) => (
        <line
          key={`y-grid-${y}`}
          x1={PLOT_X}
          y1={sy(y)}
          x2={PLOT_X + PLOT_W}
          y2={sy(y)}
          className="grid-line"
        />
      ))}

      <g clipPath="url(#plot-clip)">
        {errorAreas.map((path, index) => (
          <path
            key={`error-area-${index}`}
            d={path}
            className="error-area"
          />
        ))}

        <path
          d={makePath(target)}
          className="target-curve"
        />

        <path
          d={makePath(player)}
          className="player-curve"
        />
      </g>

      {MIN_X <= 0 && MAX_X >= 0 && (
        <line
          x1={zeroX}
          y1={PLOT_Y}
          x2={zeroX}
          y2={PLOT_Y + PLOT_H}
          className="axis-line"
        />
      )}

      {MIN_Y <= 0 && MAX_Y >= 0 && (
        <line
          x1={PLOT_X}
          y1={zeroY}
          x2={PLOT_X + PLOT_W}
          y2={zeroY}
          className="axis-line"
        />
      )}

      <rect
        x={PLOT_X}
        y={PLOT_Y}
        width={PLOT_W}
        height={PLOT_H}
        className="plot-border"
      />

      {xValues.map((x) =>
        x === 0 ? null : (
          <text
            key={`x-label-${x}`}
            x={sx(x)}
            y={xLabelY}
            textAnchor="middle"
            className="graph-number"
          >
            {x}
          </text>
        )
      )}

      {yValues.map((y) =>
        y === 0 ? null : (
          <text
            key={`y-label-${y}`}
            x={zeroX - 10}
            y={sy(y) + 4}
            textAnchor="end"
            className="graph-number"
          >
            {y}
          </text>
        )
      )}
    </svg>
  );
}
