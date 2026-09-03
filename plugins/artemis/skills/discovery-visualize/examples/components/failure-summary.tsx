import { Callout, Link, Stack, Text } from "cursor/canvas";

/**
 * Answers: "Did failures or eligibility gates affect the result?"
 * Snapshot inputs: executionSummary and perMetricWinners[metric].
 * Omit this component when the run is healthy and raw/eligible winners match.
 * Eligibility explains report safety; it never replaces the raw measurement.
 */
export type WinnerRef = {
  label: string;
  webUrl?: string;
};

export type FailureSummaryProps = {
  rawWinner: WinnerRef | null;
  eligibleWinner: WinnerRef | null;
  generationFailed: number;
  executionFailed: number;
  scoringFailed: number;
  missingTargetMetricVersions: number;
};

function WinnerLink({ winner }: { winner: WinnerRef }) {
  return winner.webUrl ? (
    <Link href={winner.webUrl}>{winner.label}</Link>
  ) : (
    <>{winner.label}</>
  );
}

export function FailureSummary({
  rawWinner,
  eligibleWinner,
  generationFailed,
  executionFailed,
  scoringFailed,
  missingTargetMetricVersions,
}: FailureSummaryProps) {
  const failures =
    generationFailed +
    executionFailed +
    scoringFailed +
    missingTargetMetricVersions;
  const winnerDiffers =
    rawWinner != null &&
    rawWinner.label !== eligibleWinner?.label;

  if (!failures && !winnerDiffers) return null;

  return (
    <Callout tone="warning" title="Result qualification">
      <Stack gap={4}>
        {winnerDiffers && rawWinner ? (
          <Text>
            The best measured result is <WinnerLink winner={rawWinner} />, but
            it failed the eligibility gate.
            {eligibleWinner ? (
              <>
                {" "}
                The eligible alternative is{" "}
                <WinnerLink winner={eligibleWinner} />.
              </>
            ) : (
              " No eligible alternative was measured."
            )}
          </Text>
        ) : null}
        {failures ? (
          <Text size="small" tone="secondary">
            Generation failed: {generationFailed} · execution failed:{" "}
            {executionFailed} · scoring failed: {scoringFailed} · missing
            target metric: {missingTargetMetricVersions}
          </Text>
        ) : null}
      </Stack>
    </Callout>
  );
}
