import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Play, Loader2, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui/Table";
import { RevealSection, RevealItem } from "../components/landing/RevealSection";
import { useScanJobs, useSubmitScan } from "../hooks/useScans";
import { formatDateTime } from "../lib/utils";

const STATUS_TONE: Record<string, "neutral" | "primary" | "success" | "warning" | "danger"> = {
  queued: "neutral",
  running: "primary",
  completed: "success",
  failed: "danger",
  cancelled: "warning",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="size-3.5 text-emerald-400" />,
  failed: <XCircle className="size-3.5 text-red-400" />,
  running: <Loader2 className="size-3.5 text-primary animate-spin" />,
  queued: <AlertCircle className="size-3.5 text-muted-foreground" />,
  cancelled: <XCircle className="size-3.5 text-amber-400" />,
};

export default function ScanPage() {
  const { data, isLoading } = useScanJobs();
  const submitScan = useSubmitScan();
  const [repoUrl, setRepoUrl] = useState("");
  const navigate = useNavigate();
  
  const handleTriggerScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl) return;
    await submitScan.mutateAsync({ repo_url: repoUrl, priority: "high" });
    setRepoUrl("");
  };

  return (
    <div>
      <PageHeader
        title="Security Scan Pipeline"
        description="Trigger and monitor multi-stage repository security scans."
      />

      <RevealSection className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <RevealItem className="lg:col-span-1">
          <Card className="h-full">
            <CardHeader title="Trigger New Scan" description="Analyze a git repository" />
            <CardContent>
              <form onSubmit={handleTriggerScan} className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <label htmlFor="repoUrl" className="text-sm font-medium text-foreground">
                    Repository URL
                  </label>
                  <input
                    id="repoUrl"
                    type="url"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    placeholder="https://github.com/example/repo"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    disabled={submitScan.isPending}
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitScan.isPending || !repoUrl}
                  className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2 w-full"
                >
                  {submitScan.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  Start Scan
                </button>
              </form>
            </CardContent>
          </Card>
        </RevealItem>

        <RevealItem className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader title="Scan Queue" description="Recent and active scan jobs" />
            <Table>
              <TableHead>
                <tr>
                  <TableHeaderCell>Repository</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Progress</TableHeaderCell>
                  <TableHeaderCell>Findings</TableHeaderCell>
                  <TableHeaderCell>Risk Level</TableHeaderCell>
                  <TableHeaderCell>Started</TableHeaderCell>
                </tr>
              </TableHead>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground h-24">
                      <Loader2 className="mx-auto size-5 animate-spin mb-2" />
                      Loading scan queue...
                    </TableCell>
                  </TableRow>
                ) : data?.scan_jobs?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground h-24">
                      No scan jobs found.
                    </TableCell>
                  </TableRow>
                ) : (
                  data?.scan_jobs.map((job) => (
                    <TableRow 
                      key={job.scan_job_id} 
                      className="cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => navigate(`/scans/${job.scan_job_id}`)}
                    >
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <Shield className="size-4 text-primary shrink-0" />
                          <span className="truncate max-w-[200px]" title={job.repository_name}>
                            {job.repository_name}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          tone={STATUS_TONE[job.status] ?? "neutral"}
                          className="capitalize flex items-center gap-1 w-max"
                        >
                          {STATUS_ICON[job.status]}
                          {job.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-full bg-secondary rounded-full h-2">
                            <div
                              className="bg-primary h-2 rounded-full transition-all duration-500"
                              style={{ width: `${job.progress_percent}%` }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground tabular-nums min-w-[3ch]">
                            {job.progress_percent}%
                          </span>
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-1 uppercase truncate max-w-[120px]">
                          {job.current_stage || "QUEUED"}
                        </div>
                      </TableCell>
                      <TableCell className="tabular-nums font-mono text-xs">
                        {job.total_findings ?? "—"}
                      </TableCell>
                      <TableCell>
                        {job.brs_risk_level ? (
                          <Badge tone={
                            job.brs_risk_level === "CRITICAL" ? "danger" : 
                            job.brs_risk_level === "HIGH" ? "warning" : "primary"
                          } className="text-[10px]">
                            {job.brs_risk_level}
                          </Badge>
                        ) : "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs whitespace-nowrap">
                        {formatDateTime(job.started_at || job.queued_at)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </RevealItem>
      </RevealSection>
    </div>
  );
}
