import { useEffect, useId, useRef, useState } from "react";

import type { Point } from "../math/sampleFunction";

type Props = {
  target: Point[];
  player: Point[];
  playerGraph: Point[];
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

const MIN_ZOOM_FACTOR = 1;
const MAX_ZOOM_FACTOR = 32;
const BUTTON_ZOOM_STEP = 1.12;

function formatZoomFactor(factor: number) {
  return Number.isInteger(factor) ? String(factor) : factor.toFixed(2);
}

function makeTicks(min: number, max: number, targetCount = 10) {
  const span = max - min;
  if (!Number.isFinite(span) || span <= 0) {
    return [];
  }

  const rawStep = span / targetCount;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalizedStep = rawStep / magnitude;
  const stepMultiplier =
    normalizedStep <= 1
      ? 1
      : normalizedStep <= 2
        ? 2
        : normalizedStep <= 5
          ? 5
          : 10;
  const step = stepMultiplier * magnitude;
  const ticks: number[] = [];

  for (
    let value = Math.ceil(min / step) * step;
    value <= max && ticks.length <= targetCount + 1;
    value += step
  ) {
    const tick = Number(value.toPrecision(12));
    ticks.push(Math.abs(tick) < step * 1e-10 ? 0 : tick);
  }

  return ticks;
}

export default function Graph({
  target,
  player,
  playerGraph,
  domain = { min: -10, max: 10 },
  range = { min: -5, max: 5 },
}: Props) {
  const graphViewRef = useRef<HTMLDivElement>(null);
  const [zoomState, setZoomState] = useState({
    domainMin: domain.min,
    domainMax: domain.max,
    factor: MIN_ZOOM_FACTOR,
  });
  const zoomFactor =
    zoomState.domainMin === domain.min &&
    zoomState.domainMax === domain.max
      ? zoomState.factor
      : MIN_ZOOM_FACTOR;
  const isZoomedOut = zoomFactor > MIN_ZOOM_FACTOR;
  const graphId = useId().replace(/:/g, "");
  const domainCenter = (domain.min + domain.max) / 2;
  const domainHalfSpan = Math.max(
    (domain.max - domain.min) / 2,
    Number.EPSILON,
  );
  const MIN_X = domainCenter - domainHalfSpan * zoomFactor;
  const MAX_X = domainCenter + domainHalfSpan * zoomFactor;
  const rangeCenter = (range.min + range.max) / 2;
  const rangeHalfSpan = Math.max((range.max - range.min) / 2, Number.EPSILON);
  const MIN_Y = rangeCenter - rangeHalfSpan * zoomFactor;
  const MAX_Y = rangeCenter + rangeHalfSpan * zoomFactor;

  const ySpan = MAX_Y - MIN_Y;
  const challengeYSpan = range.max - range.min;

  useEffect(() => {
    const graphView = graphViewRef.current;
    if (!graphView) {
      return;
    }

    function onWheel(event: WheelEvent) {
      if (!event.ctrlKey && !event.metaKey) {
        return;
      }

      event.preventDefault();
      setZoomState((current) => {
        const currentFactor =
          current.domainMin === domain.min &&
          current.domainMax === domain.max
            ? current.factor
            : MIN_ZOOM_FACTOR;

        return {
          domainMin: domain.min,
          domainMax: domain.max,
          factor: Math.min(
            MAX_ZOOM_FACTOR,
            Math.max(
              MIN_ZOOM_FACTOR,
              currentFactor * Math.exp(event.deltaY * 0.003),
            ),
          ),
        };
      });
    }

    graphView.addEventListener("wheel", onWheel, { passive: false });
    return () => graphView.removeEventListener("wheel", onWheel);
  }, [domain.min, domain.max]);

  function updateZoomFactor(update: (factor: number) => number) {
    setZoomState((current) => {
      const currentFactor =
        current.domainMin === domain.min &&
        current.domainMax === domain.max
          ? current.factor
          : MIN_ZOOM_FACTOR;
      return {
        domainMin: domain.min,
        domainMax: domain.max,
        factor: Math.min(
          MAX_ZOOM_FACTOR,
          Math.max(MIN_ZOOM_FACTOR, update(currentFactor)),
        ),
      };
    });
  }

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
      point.y >= range.min - 2 &&
      point.y <= range.max + 2
    );
  }

  function makePath(points: Point[]) {
    let path = "";
    let drawing = false;
    let previous: Point | null = null;

    for (const point of points) {
      if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) {
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
          targetJump > challengeYSpan * 0.6 ||
          playerJump > challengeYSpan * 0.6
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

  const xValues = makeTicks(MIN_X, MAX_X);
  const yValues = makeTicks(MIN_Y, MAX_Y);

  const zeroX = sx(0);
  const zeroY = sy(0);
  const domainStartX = sx(domain.min);
  const domainEndX = sx(domain.max);
  const challengeRangeTopY = sy(range.max);
  const challengeRangeBottomY = sy(range.min);
  const challengeRegionX = Math.max(PLOT_X, domainStartX);
  const challengeRegionRight = Math.min(PLOT_X + PLOT_W, domainEndX);
  const challengeRegionTop = Math.max(PLOT_Y, challengeRangeTopY);
  const challengeRegionBottom = Math.min(
    PLOT_Y + PLOT_H,
    challengeRangeBottomY,
  );

  const xLabelY = Math.min(
    PLOT_Y + PLOT_H - 8,
    Math.max(PLOT_Y + 16, zeroY + 16)
  );

  return (
    <div className="graph-view" ref={graphViewRef}>
      <div
        className="graph-controls"
        role="group"
        aria-label="Graph zoom controls"
      >
        <span className="graph-controls-label">Zoom</span>
        <button
          type="button"
          className="graph-zoom-button"
          aria-label="Zoom out"
          onClick={() => updateZoomFactor((factor) => factor * BUTTON_ZOOM_STEP)}
          disabled={zoomFactor >= MAX_ZOOM_FACTOR}
        >
          −
        </button>
        <span
          className="graph-zoom-level"
          aria-live="polite"
          aria-label={`Viewing ${formatZoomFactor(zoomFactor)} times the challenge-domain width`}
        >
          {formatZoomFactor(zoomFactor)}× wider
        </span>
        <button
          type="button"
          className="graph-zoom-button"
          aria-label="Zoom in"
          onClick={() => updateZoomFactor((factor) => factor / BUTTON_ZOOM_STEP)}
          disabled={zoomFactor <= MIN_ZOOM_FACTOR}
        >
          +
        </button>
        <button
          type="button"
          className="graph-reset-button"
          onClick={() => updateZoomFactor(() => MIN_ZOOM_FACTOR)}
          disabled={!isZoomedOut}
        >
          Reset
        </button>
        <span className="graph-zoom-hint">
          Ctrl/⌘ + pinch to zoom
        </span>
        {isZoomedOut && (
          <span className="graph-domain-hint">
            Shaded band: challenge domain
          </span>
        )}
      </div>

      <svg
        className="graph"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Equation graph. Viewing x from ${MIN_X} to ${MAX_X} and y from ${MIN_Y} to ${MAX_Y}; challenge region is x from ${domain.min} to ${domain.max} and y from ${range.min} to ${range.max}.`}
      >
        <defs>
          <clipPath id={`plot-clip-${graphId}`}>
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

        {isZoomedOut && (
          <>
            <rect
              x={PLOT_X}
              y={PLOT_Y}
              width={Math.max(0, domainStartX - PLOT_X)}
              height={PLOT_H}
              className="outside-domain-shade"
            />
            <rect
              x={domainEndX}
              y={PLOT_Y}
              width={Math.max(0, PLOT_X + PLOT_W - domainEndX)}
              height={PLOT_H}
              className="outside-domain-shade"
            />
            <rect
              x={Math.max(PLOT_X, domainStartX)}
              y={PLOT_Y}
              width={Math.max(
                0,
                Math.min(PLOT_X + PLOT_W, domainEndX) -
                  Math.max(PLOT_X, domainStartX),
              )}
              height={PLOT_H}
              className="challenge-domain-band"
            />
          </>
        )}

        {xValues.map((x) => {
          if (
            isZoomedOut &&
            (Math.abs(x - domain.min) < 1e-9 ||
              Math.abs(x - domain.max) < 1e-9)
          ) {
            return null;
          }

          return (
            <line
              key={`x-grid-${x}`}
              x1={sx(x)}
              y1={PLOT_Y}
              x2={sx(x)}
              y2={PLOT_Y + PLOT_H}
              className="grid-line"
            />
          );
        })}

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

        <g clipPath={`url(#plot-clip-${graphId})`}>
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
            d={makePath(playerGraph)}
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

        {isZoomedOut && (
          <rect
            x={challengeRegionX}
            y={challengeRegionTop}
            width={Math.max(0, challengeRegionRight - challengeRegionX)}
            height={Math.max(0, challengeRegionBottom - challengeRegionTop)}
            className="challenge-region-outline"
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
    </div>
  );
}
