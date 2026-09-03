import { H2, Stack, Text, useHostTheme } from "cursor/canvas";

/**
 * Answers: "How did the metric evolve through the run?"
 * Snapshot input: runningBest[metric] plus baseline.metrics[metric].mean.
 * Null means are rendered as gaps. Do not replace them with zero or connect
 * across them. The running-best series may carry forward through those gaps.
 */
export type TrajectoryPoint = {
  label: string;
  mean: number | null;
  bestMean: number | null;
};

export type MetricTrajectoryProps = {
  metric: string;
  unit: string;
  baselineMean: number;
  baselineSha: string;
  points: TrajectoryPoint[];
  source: string;
};

function pathSegments(
  values: Array<number | null>,
  x: (index: number) => number,
  y: (value: number) => number,
) {
  const segments: string[] = [];
  let current = "";

  values.forEach((value, index) => {
    if (value == null) {
      if (current) segments.push(current);
      current = "";
      return;
    }
    current += `${current ? " L" : "M"} ${x(index)} ${y(value)}`;
  });
  if (current) segments.push(current);
  return segments;
}

export function MetricTrajectory({
  metric,
  unit,
  baselineMean,
  baselineSha,
  points,
  source,
}: MetricTrajectoryProps) {
  const theme = useHostTheme();
  const width = 760;
  const height = 260;
  const margin = { top: 18, right: 20, bottom: 38, left: 58 };
  const values = [
    baselineMean,
    ...points.flatMap((point) =>
      [point.mean, point.bestMean].filter(
        (value): value is number => value != null,
      ),
    ),
  ];

  if (!points.length || values.length === 1) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = Math.max((max - min) * 0.1, Math.abs(max || 1) * 0.02);
  const yMin = min - padding;
  const yMax = max + padding;
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const x = (index: number) =>
    margin.left + (index * plotWidth) / Math.max(points.length - 1, 1);
  const y = (value: number) =>
    margin.top + ((yMax - value) * plotHeight) / (yMax - yMin || 1);
  const observedPaths = pathSegments(
    points.map((point) => point.mean),
    x,
    y,
  );
  const bestPaths = pathSegments(
    points.map((point) => point.bestMean),
    x,
    y,
  );

  return (
    <Stack gap={8}>
      <H2>{metric}: generation-order trajectory</H2>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={`${metric} means and running best by generated version, with baseline ${baselineMean} ${unit}`}
      >
        <line
          x1={margin.left}
          x2={width - margin.right}
          y1={y(baselineMean)}
          y2={y(baselineMean)}
          stroke={theme.stroke.primary}
          strokeDasharray="4 4"
        />
        <text
          x={width - margin.right}
          y={y(baselineMean) - 5}
          textAnchor="end"
          fill={theme.text.tertiary}
          fontSize="11"
        >
          baseline
        </text>
        {observedPaths.map((path, index) => (
          <path
            key={`observed-${index}`}
            d={path}
            fill="none"
            stroke={theme.accent.primary}
            strokeWidth="2"
          />
        ))}
        {bestPaths.map((path, index) => (
          <path
            key={`best-${index}`}
            d={path}
            fill="none"
            stroke={theme.category.green}
            strokeWidth="2"
            strokeDasharray="6 3"
          />
        ))}
        {points.map((point, index) =>
          point.mean == null ? null : (
            <circle
              key={point.label}
              cx={x(index)}
              cy={y(point.mean)}
              r="3"
              fill={theme.accent.primary}
            />
          ),
        )}
        <text
          x={margin.left - 10}
          y={margin.top + plotHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90 ${margin.left - 10} ${margin.top + plotHeight / 2})`}
          fill={theme.text.secondary}
          fontSize="11"
        >
          Mean {unit ? `(${unit})` : ""}
        </text>
        <text
          x={margin.left + plotWidth / 2}
          y={height - 5}
          textAnchor="middle"
          fill={theme.text.secondary}
          fontSize="11"
        >
          Generated version
        </text>
        {points.map((point, index) =>
          points.length <= 12 || index === 0 || index === points.length - 1 ? (
            <text
              key={`label-${point.label}`}
              x={x(index)}
              y={height - 20}
              textAnchor="middle"
              fill={theme.text.tertiary}
              fontSize="10"
            >
              {point.label}
            </text>
          ) : null,
        )}
      </svg>
      <Text size="small" tone="tertiary">
        Solid blue: observed mean. Dashed green: running best. Missing
        observations remain gaps. Baseline {baselineSha}. Source: {source}.
      </Text>
    </Stack>
  );
}
