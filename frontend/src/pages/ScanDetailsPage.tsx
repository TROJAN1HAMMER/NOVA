import { useState } from "react";
import type { ReactNode } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Shield, AlertTriangle, Activity, Info, CheckCircle, XCircle } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui/Table";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/Button";
import { StatTile } from "../components/ui/StatTile";
import { FullPageSpinner } from "../components/ui/Spinner";
import { useScanStatus, useScanFindings, useScanCompliance } from "../hooks/useScans";
import type { FindingResponse } from "../lib/api/scan";
import { cn } from "../lib/utils";

export default function ScanDetailsPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"overview" | "findings" | "compliance">("overview");
  const [selectedFinding, setSelectedFinding] = useState<FindingResponse | null>(null);

  const { data: status, isLoading: statusLoading } = useScanStatus(scanId!);
  const { data: findingsData, isLoading: findingsLoading } = useScanFindings(scanId!);
  const { data: complianceData, isLoading: complianceLoading } = useScanCompliance(scanId!);

  if (statusLoading) return <FullPageSpinner />;
  if (!status) return <div>Scan not found</div>;

  const renderFindingModalContent = (finding: FindingResponse): ReactNode => (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Badge tone="danger">{finding.severity}</Badge>
        <Badge tone="neutral">CVSS: {finding.cvss.toFixed(1)}</Badge>
        {finding.cwe_id && <Badge tone="neutral">{finding.cwe_id}</Badge>}
      </div>
      
      <div>
        <h4 className="text-sm font-semibold mb-1">Description</h4>
        <p className="text-sm text-muted-foreground whitespace-pre-wrap">{finding.description}</p>
      </div>

      {finding.ai_explanation && (
        <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg">
          <h4 className="text-sm font-semibold text-primary mb-2 flex items-center gap-2">
            <Activity className="size-4" /> AI Analysis
          </h4>
          <p className="text-sm text-foreground/90 whitespace-pre-wrap">{finding.ai_explanation}</p>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button 
          onClick={() => navigate("/scans")}
          className="p-2 hover:bg-muted rounded-full transition-colors"
        >
          <ArrowLeft className="size-5 text-muted-foreground" />
        </button>
        <PageHeader
          title={`Scan Details: ${status.repository_name}`}
          description={`Scan Job ID: ${status.scan_job_id}`}
        />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {(["overview", "findings", "compliance"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-6 py-3 text-sm font-medium border-b-2 transition-colors capitalize",
              activeTab === tab
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content: Overview */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatTile
              label="BRS Risk Level"
              value={status.brs_risk_level || "N/A"}
              icon={<Shield className="size-4" />}
              delta={
                status.brs_risk_level === "CRITICAL" ? { value: -100, isGoodWhenUp: true, label: "Critical Risk" } :
                status.brs_risk_level === "HIGH" ? { value: -75, isGoodWhenUp: true, label: "High Risk" } :
                undefined
              }
            />
            <StatTile
              label="Total Findings"
              value={status.total_findings?.toString() || "0"}
              icon={<AlertTriangle className="size-4" />}
            />
            <StatTile
              label="Exposure Score"
              value={status.attack_surface_exposure_score?.toString() || "0"}
              icon={<Activity className="size-4" />}
            />
            <StatTile
              label="Status"
              value={status.status}
              icon={<Info className="size-4" />}
            />
          </div>

          <Card>
            <CardHeader title="Scan Summary" />
            <CardContent>
              <div className="prose prose-sm dark:prose-invert max-w-none text-muted-foreground">
                {status.summary ? (
                  <pre className="whitespace-pre-wrap font-mono text-xs overflow-auto max-h-60 bg-muted/50 p-4 rounded-md">
                    {JSON.stringify(status.summary, null, 2)}
                  </pre>
                ) : (
                  <p>No summary data available.</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tab Content: Findings */}
      {activeTab === "findings" && (
        <Card>
          <CardHeader title="Vulnerability Findings" description={`Found ${findingsData?.total || 0} vulnerabilities`} />
          <Table>
            <TableHead>
              <tr>
                <TableHeaderCell>Severity</TableHeaderCell>
                <TableHeaderCell>Title</TableHeaderCell>
                <TableHeaderCell>File</TableHeaderCell>
                <TableHeaderCell>CVSS</TableHeaderCell>
              </tr>
            </TableHead>
            <TableBody>
              {findingsLoading ? (
                <TableRow><TableCell colSpan={4} className="text-center py-8">Loading findings...</TableCell></TableRow>
              ) : findingsData?.findings.length === 0 ? (
                <TableRow><TableCell colSpan={4} className="text-center py-8">No findings reported.</TableCell></TableRow>
              ) : (
                findingsData?.findings.map((f) => (
                  <TableRow 
                    key={f.id} 
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedFinding(f)}
                  >
                    <TableCell>
                      <Badge tone={
                        f.severity.toUpperCase() === "CRITICAL" ? "danger" : 
                        f.severity.toUpperCase() === "HIGH" ? "warning" : "primary"
                      }>
                        {f.severity}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium max-w-md truncate" title={f.title}>{f.title}</TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-xs truncate" title={f.file_path}>
                      {f.file_path}:{f.line_number}
                    </TableCell>
                    <TableCell className="tabular-nums">{f.cvss.toFixed(1)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Tab Content: Compliance */}
      {activeTab === "compliance" && (
        <div className="space-y-6">
          {complianceLoading ? (
             <div className="py-8 text-center text-muted-foreground">Loading compliance report...</div>
          ) : !complianceData || complianceData.frameworks.length === 0 ? (
             <Card><CardContent className="py-8 text-center text-muted-foreground">No compliance data available.</CardContent></Card>
          ) : (
            complianceData.frameworks.map((fw) => (
              <Card key={fw.short_code}>
                <CardHeader 
                  title={fw.framework_name} 
                  description={`Compliance: ${fw.compliance_percentage}% (${fw.passed_controls}/${fw.total_controls} controls passed)`} 
                />
                <Table>
                  <TableHead>
                    <tr>
                      <TableHeaderCell className="w-24">Status</TableHeaderCell>
                      <TableHeaderCell className="w-32">Req ID</TableHeaderCell>
                      <TableHeaderCell>Control Title</TableHeaderCell>
                    </tr>
                  </TableHead>
                  <TableBody>
                    {fw.controls.map((ctrl, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          {ctrl.status === "FAIL" ? (
                            <Badge tone="danger" className="flex gap-1 items-center w-max"><XCircle className="size-3" /> FAIL</Badge>
                          ) : (
                            <Badge tone="success" className="flex gap-1 items-center w-max"><CheckCircle className="size-3" /> PASS</Badge>
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-xs">{ctrl.requirement_id}</TableCell>
                        <TableCell className="text-sm">
                          <div className="font-medium">{ctrl.title}</div>
                          {ctrl.status === "FAIL" && ctrl.evidence.length > 0 && (
                            <div className="mt-2 pl-3 border-l-2 border-red-500/50 space-y-1">
                              {ctrl.evidence.map((ev, j) => (
                                <div key={j} className="text-xs text-muted-foreground">
                                  <span className="text-red-400 font-medium mr-1">[{ev.severity}]</span>
                                  {ev.finding_title} <span className="opacity-50">({ev.file_path}:{ev.line_number})</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Finding Detail Modal */}
      <Modal 
        open={!!selectedFinding} 
        onClose={() => setSelectedFinding(null)} 
        size="lg"
        title={selectedFinding?.title}
      >
        {selectedFinding && renderFindingModalContent(selectedFinding)}
        <div className="mt-4 flex justify-end">
           <Button variant="outline" onClick={() => setSelectedFinding(null)}>Close</Button>
        </div>
      </Modal>
    </div>
  );
}
