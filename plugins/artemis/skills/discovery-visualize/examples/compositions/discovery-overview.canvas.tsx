import {
  Callout,
  H1,
  H2,
  LineChart,
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
    { label: "v1", mean: 8, best: 8 },
    { label: "v2", mean: 6, best: 6 },
    { label: "v3", mean: 9, best: 6 },
    { label: "v4", mean: 7, best: 6 },
  ],
};

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

      <Stack gap={8}>
        <H2>{snapshot.metric}: generation-order trajectory</H2>
        <LineChart
          categories={snapshot.trajectory.map((point) => point.label)}
          series={[
            {
              name: `${snapshot.metric} mean`,
              data: snapshot.trajectory.map((point) => point.mean),
            },
            {
              name: "running best",
              data: snapshot.trajectory.map((point) => point.best),
              tone: "success",
            },
          ]}
          valueSuffix={` ${snapshot.unit}`}
          beginAtZero={false}
          referenceLines={[
            {
              value: snapshot.baseline.mean,
              label: `baseline ${snapshot.baseline.mean}`,
            },
          ]}
          height={280}
        />
        <Text size="small" tone="tertiary">
          Means in generation order; running best is collector-provided.
          Baseline {snapshot.baselineSha}. Source: {snapshot.source}. If the
          snapshot contains null observations, use the gap-preserving metric
          trajectory recipe instead of LineChart.
        </Text>
      </Stack>
    </Stack>
  );
}
