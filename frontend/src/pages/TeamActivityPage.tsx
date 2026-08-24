import { Activity, Users, Database, Brain } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { StatTile } from "../components/ui/StatTile";
import { Card, CardHeader } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { SkeletonStatTiles, SkeletonTable } from "../components/ui/Skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../components/ui/Table";
import { RevealSection, RevealItem } from "../components/landing/RevealSection";
import { useTeamActivity } from "../hooks/useAnalytics";

export default function TeamActivityPage() {
  const { data, isLoading } = useTeamActivity();

  if (isLoading) {
    return (
      <div>
        <PageHeader
          title="Team Knowledge Activity"
          description="Org-wide knowledge ingestion and AI usage, broken down per contributor."
        />
        <SkeletonStatTiles count={3} className="mb-6 sm:grid-cols-3 lg:grid-cols-3" />
        <SkeletonTable rows={6} columns={5} />
      </div>
    );
  }

  if (!data || data.members.length === 0) {
    return (
      <div>
        <PageHeader
          title="Team Knowledge Activity"
          description="Org-wide knowledge ingestion and AI usage, broken down per contributor."
        />
        <EmptyState
          icon={<Users className="size-10" />}
          title="No team activity yet"
          description="Knowledge ingestion and assistant usage will appear here once team members begin contributing."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Team Knowledge Activity"
        description="Org-wide knowledge ingestion and AI usage, broken down per contributor."
      />

      <RevealSection className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <RevealItem>
          <StatTile
            label="Knowledge Operations"
            value={data.total_scans}
            icon={<Activity className="size-5" />}
          />
        </RevealItem>
        <RevealItem>
          <StatTile
            label="Documents Indexed"
            value={data.total_findings}
            icon={<Database className="size-5" />}
          />
        </RevealItem>
        <RevealItem>
          <StatTile
            label="Contributors"
            value={data.members.length}
            icon={<Users className="size-5" />}
          />
        </RevealItem>
      </RevealSection>

      <RevealSection>
        <RevealItem>
          <Card>
            <CardHeader
              title="Contributor Knowledge Activity"
              description="Per-member ingestion and AI usage metrics"
            />
            <Table>
              <TableHead>
                <tr>
                  <TableHeaderCell>Contributor</TableHeaderCell>
                  <TableHeaderCell>Knowledge Operations</TableHeaderCell>
                  <TableHeaderCell>Documents Processed</TableHeaderCell>
                  <TableHeaderCell>Avg BRS Score</TableHeaderCell>
                </tr>
              </TableHead>
              <TableBody>
                {data.members.map((member) => (
                  <TableRow key={member.user_id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="flex size-8 items-center justify-center rounded-full bg-primary/20 text-primary text-xs font-bold shrink-0">
                          {(member.full_name ?? member.email ?? "?")[0].toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-foreground">
                            {member.full_name || member.email}
                          </p>
                          {member.full_name && (
                            <p className="text-xs text-muted-foreground">
                              {member.email}
                            </p>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {member.total_scans}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {member.total_findings}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      <div className="flex items-center gap-1.5">
                        <Brain className="size-3.5 text-primary" />
                        {member.average_brs_score != null
                          ? `${member.average_brs_score.toFixed(1)}%`
                          : "—"}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </RevealItem>
      </RevealSection>
    </div>
  );
}
