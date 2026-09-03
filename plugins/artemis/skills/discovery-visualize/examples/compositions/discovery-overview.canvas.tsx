import {
  Callout,
  H1,
  H2,
  Link,
  Row,
  Stack,
  Stat,
  Text,
  UsageBar,
  useHostTheme,
} from "cursor/canvas";

// Complete composition example. Replace this inline synthetic snapshot slice
// with fields from collect_discovery.py; do not import component recipe files.
const snapshot = {
  metric: "latency_ms",
  unit: "ms",
  baselineSha: "abc1234",
  baseline: { mean: 10, count: 5 },
  versionCount: 4,
  versionBudget: 6,
  webUrl: "https://artemis.example/projects/project/discovery/run",
  collectedAt: "2026-09-03T10:00:00Z",
  source: "artemis discovery metrics --all --stats",
  rawWinner: {
    label: "v2",
    mean: 6,
    count: 5,
    pctBetter: 40,
    eligible: false,
  },
  eligibleWinner: { label: "v4", mean: 7, pctBetter: 30 },
  trajectory: [
    { label: "v1", mean: 8 },
    { label: "v2", mean: 6 },
    { label: "v3", mean: 9 },
    { label: "v4", mean: 7 },
  ],
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

function BaselineToWinner() {
  const theme = useHostTheme();
  const winner = snapshot.rawWinner;

  return (
    <Stack gap={8}>
      <H2>{snapshot.metric}: baseline vs best measured version</H2>
      <Row gap={18} align="center">
        <Stat
          value={`${snapshot.baseline.mean} ${snapshot.unit}`}
          label={`Baseline mean · n=${snapshot.baseline.count}`}
        />
        <Stack gap={2} style={{ minWidth: 110, textAlign: "center" }}>
          <Text
            weight="semibold"
            style={{ color: theme.category.green }}
          >
            +{winner.pctBetter.toFixed(1)}%
          </Text>
          <svg
            width="110"
            height="16"
            role="img"
            aria-label={`${snapshot.metric} improved ${winner.pctBetter}% from baseline to ${winner.label}`}
          >
            <line
              x1="4"
              y1="8"
              x2="102"
              y2="8"
              stroke={theme.accent.primary}
              strokeWidth="2"
            />
            <path
              d="M 96 3 L 104 8 L 96 13"
              fill="none"
              stroke={theme.accent.primary}
              strokeWidth="2"
            />
          </svg>
        </Stack>
        <Stat
          value={`${winner.mean} ${snapshot.unit}`}
          label={`${winner.label} mean · n=${winner.count}`}
          tone="success"
        />
      </Row>
    </Stack>
  );
}

function MetricTrajectory() {
  const theme = useHostTheme();
  const points = snapshot.trajectory;
  const winnerLabel = snapshot.rawWinner.label;
  const baselineMean = snapshot.baseline.mean;
  const width = 760;
  const height = 260;
  const margin = { top: 28, right: 20, bottom: 38, left: 58 };
  const values = [
    baselineMean,
    ...points
      .map((point) => point.mean)
      .filter((value): value is number => value != null),
  ];
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

  return (
    <Stack gap={8}>
      <H2>{snapshot.metric}: generation-order trajectory</H2>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={`${snapshot.metric} means by generated version, with baseline ${baselineMean} ${snapshot.unit} and best measured ${winnerLabel}`}
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
        {points.map((point, index) =>
          point.mean == null ? null : (
            <circle
              key={point.label}
              cx={x(index)}
              cy={y(point.mean)}
              r={point.label === winnerLabel ? 6 : 3}
              fill={
                point.label === winnerLabel
                  ? theme.category.green
                  : theme.accent.primary
              }
            />
          ),
        )}
        {points.map((point, index) =>
          point.label === winnerLabel && point.mean != null ? (
            <text
              key={`best-${point.label}`}
              x={x(index) + 10}
              y={y(point.mean) + 4}
              fill={theme.category.green}
              fontSize="11"
              fontWeight="590"
            >
              best
            </text>
          ) : null,
        )}
        <text
          x={margin.left - 10}
          y={margin.top + plotHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90 ${margin.left - 10} ${margin.top + plotHeight / 2})`}
          fill={theme.text.secondary}
          fontSize="11"
        >
          Mean ({snapshot.unit})
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
        {points.map((point, index) => (
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
        ))}
      </svg>
      <Text size="small" tone="tertiary">
        Observed mean in generation order. Green mark is the raw winner (
        {winnerLabel}), not a running-best overlay. Baseline{" "}
        {snapshot.baselineSha}. Source: {snapshot.source}.
      </Text>
    </Stack>
  );
}

export default function DiscoveryOverviewExample() {
  return (
    <Stack gap={20}>
      <Stack gap={5}>
        <H1>{snapshot.metric}: baseline vs best measured version</H1>
        <Text tone="secondary">
          Baseline {snapshot.baselineSha} · collected {snapshot.collectedAt}
        </Text>
        <Link href={snapshot.webUrl}>Open discovery in Artemis</Link>
      </Stack>

      <UsageBar
        total={snapshot.versionBudget}
        segments={[{ id: "generated", value: snapshot.versionCount }]}
        topLeftLabel="Version budget"
        topRightLabel={`${snapshot.versionCount} / ${snapshot.versionBudget}`}
      />

      <BaselineToWinner />

      {!snapshot.rawWinner.eligible ? (
        <Callout tone="warning" title="Raw winner failed the eligibility gate">
          <Text>
            {snapshot.rawWinner.label} remains the best measured result. The
            eligible alternative is {snapshot.eligibleWinner.label} at{" "}
            {snapshot.eligibleWinner.mean} {snapshot.unit} (
            +{snapshot.eligibleWinner.pctBetter}%).
          </Text>
        </Callout>
      ) : null}

      <MetricTrajectory />
    </Stack>
  );
}
