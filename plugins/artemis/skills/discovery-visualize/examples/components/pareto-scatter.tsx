import { H2, Stack, Text, useHostTheme } from "cursor/canvas";

/**
 * Answers: "What are the measured trade-offs between two named metrics?"
 * Snapshot input: the collector's opt-in pareto field. Use its dominated flag;
 * do not recompute the front in the renderer. Label only non-dominated points
 * and state that this analytical view is not an Artemis verdict.
 */
export type ParetoPoint = {
  label: string;
  x: number;
  y: number;
  dominated: boolean;
};

export type ParetoScatterProps = {
  xMetric: string;
  xUnit: string;
  yMetric: string;
  yUnit: string;
  points: ParetoPoint[];
  source: string;
};

export function ParetoScatter({
  xMetric,
  xUnit,
  yMetric,
  yUnit,
  points,
  source,
}: ParetoScatterProps) {
  const theme = useHostTheme();
  const width = 720;
  const height = 360;
  const margin = { top: 20, right: 24, bottom: 50, left: 62 };

  if (!points.length) return null;

  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xPad = Math.max((xMax - xMin) * 0.08, Math.abs(xMax || 1) * 0.02);
  const yPad = Math.max((yMax - yMin) * 0.08, Math.abs(yMax || 1) * 0.02);
  const x = (value: number) =>
    margin.left +
    ((value - (xMin - xPad)) * (width - margin.left - margin.right)) /
      (xMax - xMin + 2 * xPad || 1);
  const y = (value: number) =>
    height -
    margin.bottom -
    ((value - (yMin - yPad)) * (height - margin.top - margin.bottom)) /
      (yMax - yMin + 2 * yPad || 1);

  return (
    <Stack gap={8}>
      <H2>
        {xMetric} vs {yMetric}: Pareto view
      </H2>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={`Pareto scatter comparing ${xMetric} and ${yMetric}; non-dominated versions are labelled`}
      >
        <line
          x1={margin.left}
          x2={width - margin.right}
          y1={height - margin.bottom}
          y2={height - margin.bottom}
          stroke={theme.stroke.primary}
        />
        <line
          x1={margin.left}
          x2={margin.left}
          y1={margin.top}
          y2={height - margin.bottom}
          stroke={theme.stroke.primary}
        />
        {points.map((point) => (
          <g key={point.label}>
            <circle
              cx={x(point.x)}
              cy={y(point.y)}
              r={point.dominated ? 4 : 6}
              fill={
                point.dominated
                  ? theme.fill.primary
                  : theme.accent.primary
              }
              stroke={theme.stroke.secondary}
            />
            {!point.dominated ? (
              <text
                x={x(point.x) + 8}
                y={y(point.y) - 8}
                fill={theme.text.primary}
                fontSize="11"
              >
                {point.label}
              </text>
            ) : null}
          </g>
        ))}
        <text
          x={margin.left + (width - margin.left - margin.right) / 2}
          y={height - 10}
          textAnchor="middle"
          fill={theme.text.secondary}
          fontSize="11"
        >
          {xMetric} {xUnit ? `(${xUnit})` : ""}
        </text>
        <text
          x="15"
          y={margin.top + (height - margin.top - margin.bottom) / 2}
          textAnchor="middle"
          transform={`rotate(-90 15 ${margin.top + (height - margin.top - margin.bottom) / 2})`}
          fill={theme.text.secondary}
          fontSize="11"
        >
          {yMetric} {yUnit ? `(${yUnit})` : ""}
        </text>
      </svg>
      <Text size="small" tone="tertiary">
        Labels mark the collector-provided non-dominated points. This is an
        analytical view over {xMetric} and {yMetric}, not an Artemis verdict.
        Source: {source}.
      </Text>
    </Stack>
  );
}
