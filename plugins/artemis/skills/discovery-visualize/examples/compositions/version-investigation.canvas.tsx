import {
  Card,
  CardBody,
  CardHeader,
  H1,
  Link,
  Stack,
  Text,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

// Complete composition example for "What did each version try, and did it
// improve the target metric?" Replace with best-first rankings and experiment
// rationale from the normalized snapshot.
const discoveryUrl =
  "https://artemis.example/projects/project/discovery/run";
const versions = [
  {
    label: "v3",
    title: "Stream candidates directly",
    id: "version-3",
    pctBetter: 86.4,
    beforeParent: "Build on ",
    parent: { label: "v2", id: "version-2" },
    afterParent:
      "'s ordered candidate merge and stream indices directly into force evaluation.",
  },
  {
    label: "v2",
    title: "Ordered candidate merge",
    id: "version-2",
    pctBetter: 52.1,
    beforeParent:
      "Replace candidate sorting with a bounded merge over naturally ordered cell lists.",
  },
  {
    label: "v1",
    title: "Axis-first rejection",
    id: "version-1",
    pctBetter: -2.7,
    beforeParent:
      "Reject distant x-axis pairs before wrapped-y and squared-distance calculations.",
  },
];

function versionUrl(id: string) {
  return `${discoveryUrl}/versions/${id}`;
}

export default function VersionInvestigationExample() {
  const theme = useHostTheme();
  const [openLabel, setOpenLabel] = useCanvasState(
    "version-investigation-focus",
    versions[0].label,
  );

  return (
    <Stack gap={18}>
      <Stack gap={5}>
        <H1>Versions ranked by simulation_fps improvement</H1>
        <Text tone="secondary">
          Open a version to read its intent and lineage.
        </Text>
        <Link href={discoveryUrl}>Open discovery in Artemis</Link>
      </Stack>

      <Stack gap={8}>
        {versions.map((version) => (
          <div key={version.label}>
            <Card
              collapsible
              open={openLabel === version.label}
              onOpenChange={(open) =>
                setOpenLabel(open ? version.label : "")
              }
            >
              <CardHeader
                trailing={
                  <Text
                    as="span"
                    weight="semibold"
                    style={{
                      color:
                        version.pctBetter >= 0
                          ? theme.category.green
                          : theme.category.red,
                    }}
                  >
                    {version.pctBetter > 0 ? "+" : ""}
                    {version.pctBetter.toFixed(1)}%
                  </Text>
                }
              >
                <Link
                  href={versionUrl(version.id)}
                  style={{ color: theme.text.link, fontWeight: 590 }}
                >
                  {version.label}
                </Link>{" "}
                · {version.title}
              </CardHeader>
              <CardBody>
                <Text>
                  {version.beforeParent}
                  {version.parent ? (
                    <Link href={versionUrl(version.parent.id)}>
                      {version.parent.label}
                    </Link>
                  ) : null}
                  {version.afterParent}
                </Text>
              </CardBody>
            </Card>
          </div>
        ))}
      </Stack>

      <Text size="small" tone="tertiary">
        Best first by simulation_fps mean vs baseline. Green/red shows measured
        improvement/regression, not experiment status. Blue version numbers
        open Artemis.
      </Text>
    </Stack>
  );
}
