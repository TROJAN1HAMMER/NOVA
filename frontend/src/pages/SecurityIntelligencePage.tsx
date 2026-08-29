import { useState, useEffect } from "react";
import { ShieldAlert, ShieldCheck, Cpu, Layers, GitBranch, ArrowRight, CheckCircle2, AlertTriangle, Play, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

interface SecurityAsset {
  asset_name: str;
  asset_type: str;
  criticality: str;
  owner: str;
  location: str;
}

interface SecurityAssessment {
  id: str;
  asset_name: str;
  risk_type: str;
  severity: str;
  confidence: number;
  affected_scope: str;
  reasoning: str;
  remediation: str;
  status: str;
  attack_path: str[];
  controls_evaluated: { control: str; state: str }[];
}

interface PostureData {
  posture_score: number;
  posture_rating: str;
  total_assets: number;
  critical_assets: number;
  control_coverage: {
    present_controls: number;
    absent_or_partial_controls: number;
    coverage_percentage: number;
  };
  unresolved_risks_count: number;
  security_trend: str;
}

export default function SecurityIntelligencePage() {
  const [posture, setPosture] = useState<PostureData | null>(null);
  const [assets, setAssets] = useState<SecurityAsset[]>([]);
  const [assessments, setAssessments] = useState<SecurityAssessment[]>([]);
  const [selectedAssessment, setSelectedAssessment] = useState<SecurityAssessment | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [remediating, setRemediating] = useState<boolean>(false);
  const [verificationResult, setVerificationResult] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [resP, resA, resAss] = await Promise.all([
        fetch("/api/v1/security-intelligence/posture"),
        fetch("/api/v1/security-intelligence/assets"),
        fetch("/api/v1/security-intelligence/assessments"),
      ]);

      const dataP = await resP.json();
      const dataA = await resA.json();
      const dataAss = await resAss.json();

      setPosture(dataP.posture);
      setAssets(dataA.assets || []);
      setAssessments(dataAss.assessments || []);
      if (dataAss.assessments && dataAss.assessments.length > 0) {
        setSelectedAssessment(dataAss.assessments[0]);
      }
    } catch (err) {
      console.error("Failed to load Security Intelligence data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRunAnalysis = async () => {
    setAnalyzing(true);
    try {
      await fetch("/api/v1/security-intelligence/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_path: "." }),
      });
      await fetchData();
    } catch (err) {
      console.error("Failed to execute analysis", err);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleVerifyRemediation = async (ass: SecurityAssessment) => {
    setRemediating(true);
    setVerificationResult(null);
    try {
      const snippet = ass.risk_type.includes("PRIVILEGE")
        ? "@router.post('/role', dependencies=[Depends(RequireRole('admin'))])\ndef update_role(): pass"
        : "class LoginSchema(BaseModel):\n  username: str\n  password: str";
      const res = await fetch("/api/v1/security-intelligence/verify-remediation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assessment_id: ass.id || "ass-001",
          code_snippet: snippet,
        }),
      });
      const data = await res.json();
      if (data.fixed) {
        setVerificationResult("VERIFIED_FIXED: Remediation patch confirmed in AST analysis.");
      } else {
        setVerificationResult("STILL_PRESENT: Required security controls missing in patch.");
      }
    } catch (err) {
      setVerificationResult("Error verifying remediation.");
    } finally {
      setRemediating(false);
    }
  };

  return (
    <div className="space-y-8 p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <ShieldAlert className="size-6 text-primary" />
            Security Intelligence Service
          </h1>
          <p className="text-sm text-muted-foreground">
            Asset-centric security context graph, trust boundary data flow, and risk scenario reasoning.
          </p>
        </div>
        <Button onClick={handleRunAnalysis} disabled={analyzing} className="gap-2">
          {analyzing ? <RefreshCw className="size-4 animate-spin" /> : <Play className="size-4" />}
          {analyzing ? "Analyzing..." : "Run Security Analysis"}
        </Button>
      </div>

      {/* Posture Highlights */}
      {posture && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-card/60 backdrop-blur-md">
            <CardHeader className="pb-2">
              <CardDescription>Security Posture Score</CardDescription>
              <CardTitle className="text-3xl font-bold text-primary flex items-center gap-2">
                {posture.posture_score} / 100
                <Badge variant={posture.posture_rating === "STRONG" ? "default" : "destructive"}>
                  {posture.posture_rating}
                </Badge>
              </CardTitle>
            </CardHeader>
          </Card>

          <Card className="bg-card/60 backdrop-blur-md">
            <CardHeader className="pb-2">
              <CardDescription>Discovered Assets</CardDescription>
              <CardTitle className="text-3xl font-bold text-foreground">
                {posture.total_assets}
                <span className="text-xs text-muted-foreground font-normal ml-2">
                  ({posture.critical_assets} Critical)
                </span>
              </CardTitle>
            </CardHeader>
          </Card>

          <Card className="bg-card/60 backdrop-blur-md">
            <CardHeader className="pb-2">
              <CardDescription>Control Coverage</CardDescription>
              <CardTitle className="text-3xl font-bold text-emerald-500">
                {posture.control_coverage.coverage_percentage}%
                <span className="text-xs text-muted-foreground font-normal ml-2">
                  ({posture.control_coverage.present_controls} Present)
                </span>
              </CardTitle>
            </CardHeader>
          </Card>

          <Card className="bg-card/60 backdrop-blur-md">
            <CardHeader className="pb-2">
              <CardDescription>Unresolved Risks</CardDescription>
              <CardTitle className="text-3xl font-bold text-amber-500">
                {posture.unresolved_risks_count}
                <span className="text-xs text-muted-foreground font-normal ml-2">Open Scenarios</span>
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Main Grid: Assets & Assessments */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Asset Registry & Risk Assessments */}
        <div className="space-y-6 lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Cpu className="size-4 text-primary" /> Discovered Assets ({assets.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {assets.map((asset, i) => (
                <div key={i} className="p-3 border rounded-lg bg-muted/30 flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-sm">{asset.asset_name}</div>
                    <div className="text-xs text-muted-foreground">{asset.location}</div>
                  </div>
                  <Badge variant={asset.criticality === "CRITICAL" ? "destructive" : "secondary"}>
                    {asset.criticality}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Layers className="size-4 text-primary" /> Security Assessments ({assessments.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {assessments.map((ass, i) => (
                <div
                  key={i}
                  onClick={() => { setSelectedAssessment(ass); setVerificationResult(null); }}
                  className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                    selectedAssessment?.risk_type === ass.risk_type ? "border-primary bg-primary/5" : "hover:bg-muted/40"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-xs text-foreground">{ass.risk_type}</span>
                    <Badge variant={ass.severity === "HIGH" ? "destructive" : "outline"}>{ass.severity}</Badge>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 truncate">{ass.affected_scope}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Assessment Detail & Risk Path Visualization */}
        <div className="lg:col-span-2 space-y-6">
          {selectedAssessment ? (
            <Card className="border-primary/30">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <Badge variant="outline" className="mb-2">
                      Assessment Detail
                    </Badge>
                    <CardTitle className="text-xl font-bold">{selectedAssessment.risk_type}</CardTitle>
                    <CardDescription>{selectedAssessment.affected_scope}</CardDescription>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleVerifyRemediation(selectedAssessment)}
                    disabled={remediating}
                    className="gap-2"
                  >
                    <ShieldCheck className="size-4 text-emerald-500" />
                    {remediating ? "Verifying..." : "Verify Remediation"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Verification result alert */}
                {verificationResult && (
                  <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
                    verificationResult.includes("VERIFIED_FIXED") ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20" : "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                  }`}>
                    <CheckCircle2 className="size-4" /> {verificationResult}
                  </div>
                )}

                {/* Reasoning Chain */}
                <div>
                  <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
                    Why Identified (Reasoning Chain)
                  </h4>
                  <p className="text-sm bg-muted/40 p-3 rounded-lg leading-relaxed">{selectedAssessment.reasoning}</p>
                </div>

                {/* Risk Path Visualization */}
                <div>
                  <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-3 flex items-center gap-2">
                    <GitBranch className="size-4 text-primary" /> Risk & Attack Path Visualization
                  </h4>
                  <div className="space-y-2">
                    {selectedAssessment.attack_path?.map((step, idx) => (
                      <div key={idx} className="flex items-center gap-3 text-xs bg-muted/20 p-2.5 rounded-md border border-border/40">
                        <span className="font-bold text-primary shrink-0">Step {idx + 1}</span>
                        <ArrowRight className="size-3.5 text-muted-foreground shrink-0" />
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Controls Evaluated */}
                <div>
                  <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
                    Security Controls Evaluated
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedAssessment.controls_evaluated?.map((c, i) => (
                      <Badge key={i} variant={c.state === "PRESENT" ? "default" : "destructive"}>
                        {c.control}: {c.state}
                      </Badge>
                    ))}
                  </div>
                </div>

                {/* Remediation Guidance */}
                <div>
                  <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
                    Recommended Remediation
                  </h4>
                  <div className="text-xs font-mono bg-card p-3 rounded-lg border text-emerald-400">
                    {selectedAssessment.remediation}
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                Select a security assessment from the left panel to inspect attack paths and verify remediations.
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
