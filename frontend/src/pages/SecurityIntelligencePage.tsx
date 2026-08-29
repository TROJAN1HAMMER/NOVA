import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldCheck,
  Cpu,
  Layers,
  GitBranch,
  ArrowRight,
  CheckCircle2,
  Play,
  RefreshCw,
  Zap,
} from "lucide-react";
import { Card, CardContent } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { apiClient } from "../lib/api/client";

interface SecurityAsset {
  asset_name: string;
  asset_type: string;
  criticality: string;
  owner: string;
  location: string;
}

interface SecurityAssessment {
  id: string;
  asset_name: string;
  risk_type: string;
  severity: string;
  confidence: number;
  affected_scope: string;
  reasoning: string;
  remediation: string;
  status: string;
  attack_path: string[];
  controls_evaluated: { control: string; state: string }[];
}

interface PostureData {
  posture_score: number;
  posture_rating: string;
  delta_score?: number | null;
  total_assets: number;
  critical_assets: number;
  control_coverage: {
    present_controls: number;
    absent_or_partial_controls: number;
    coverage_percentage: number;
  };
  unresolved_risks_count: number;
  security_trend: string;
}

export default function SecurityIntelligencePage() {
  const [posture, setPosture] = useState<PostureData | null>(null);
  const [assets, setAssets] = useState<SecurityAsset[]>([]);
  const [assessments, setAssessments] = useState<SecurityAssessment[]>([]);
  const [selectedAssessment, setSelectedAssessment] = useState<SecurityAssessment | null>(null);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [remediating, setRemediating] = useState<boolean>(false);
  const [verificationResult, setVerificationResult] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setAnalyzing(true);
      const [resP, resA, resAss] = await Promise.all([
        apiClient.get("/security-intelligence/posture"),
        apiClient.get("/security-intelligence/assets"),
        apiClient.get("/security-intelligence/assessments"),
      ]);

      const dataP = resP.data || {};
      const dataA = resA.data || {};
      const dataAss = resAss.data || {};

      if (dataP.posture) setPosture(dataP.posture);
      const loadedAssets = dataA.assets || [];
      const loadedAssessments = dataAss.assessments || [];

      setAssets(loadedAssets);
      setAssessments(loadedAssessments);
      if (loadedAssessments.length > 0) {
        setSelectedAssessment(loadedAssessments[0]);
      }
    } catch (err) {
      console.error("Failed to load Security Intelligence data", err);
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRunAnalysis = async () => {
    setAnalyzing(true);
    try {
      const res = await apiClient.post("/security-intelligence/analyze", { target_path: "." });
      const data = res.data;
      if (data.posture) setPosture(data.posture);
      if (data.assets) setAssets(data.assets);
      if (data.assessments) {
        setAssessments(data.assessments);
        if (data.assessments.length > 0) {
          setSelectedAssessment(data.assessments[0]);
        }
      }
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
      const res = await apiClient.post("/security-intelligence/verify-remediation", {
        assessment_id: ass.id || "ass-001",
        code_snippet: snippet,
      });
      const data = res.data;
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
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Security Intelligence Service"
        description="Asset-centric security context graph, trust boundary data flow modeling, and risk scenario reasoning."
        action={
          <Button onClick={handleRunAnalysis} disabled={analyzing} className="gap-2">
            {analyzing ? <RefreshCw className="size-4 animate-spin" /> : <Play className="size-4" />}
            {analyzing ? "Analyzing Codebase..." : "Run Security Analysis"}
          </Button>
        }
      />

      {/* Posture Highlights */}
      {posture ? (
        <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4 bg-gradient-to-br from-primary/15 via-card to-card border-primary/30">
            <div className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
              <span>Security Posture Score</span>
              <Badge tone={posture.posture_rating === "STRONG" ? "success" : "danger"}>
                {posture.posture_rating}
              </Badge>
            </div>
            <div className="text-3xl font-bold text-primary font-mono flex items-center gap-2">
              {posture.posture_score} / 100
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">Repository security health</div>
          </Card>

          <Card className="p-4 bg-gradient-to-br from-blue-500/15 via-card to-card border-blue-500/30">
            <div className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
              <span>Discovered Assets</span>
              <Badge tone="primary">{posture.critical_assets} Critical</Badge>
            </div>
            <div className="text-3xl font-bold text-foreground font-mono">
              {posture.total_assets}
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">Endpoints, DBs & Services</div>
          </Card>

          <Card className="p-4 bg-gradient-to-br from-emerald-500/15 via-card to-card border-emerald-500/30">
            <div className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
              <span>Control Coverage</span>
              <Badge tone="success">{posture.control_coverage.present_controls} Enforced</Badge>
            </div>
            <div className="text-3xl font-bold text-emerald-400 font-mono">
              {posture.control_coverage.coverage_percentage}%
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">Security control ratio</div>
          </Card>

          <Card className="p-4 bg-gradient-to-br from-amber-500/15 via-card to-card border-amber-500/30">
            <div className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
              <span>Unresolved Risks</span>
              <Badge tone="warning">Scenarios</Badge>
            </div>
            <div className="text-3xl font-bold text-amber-400 font-mono">
              {posture.unresolved_risks_count}
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">Open attack path scenarios</div>
          </Card>
        </motion.div>
      ) : (
        <div className="p-4 rounded-lg bg-primary/10 border border-primary/20 flex items-center gap-3 text-xs text-primary font-medium">
          <RefreshCw className="size-4 animate-spin shrink-0" />
          Running initial codebase security analysis... discovering assets, endpoints & trust boundaries.
        </div>
      )}

      {/* Main Grid: Assets & Assessments */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Asset Registry & Risk Assessments */}
        <div className="space-y-6 lg:col-span-1">
          <Card>
            <div className="p-4 pb-0 flex items-center justify-between font-semibold text-sm">
              <span className="flex items-center gap-2 text-foreground">
                <Cpu className="size-4 text-primary" /> Discovered Assets ({assets.length})
              </span>
            </div>
            <CardContent className="space-y-2.5 pt-3 max-h-[16rem] overflow-y-auto">
              {assets.length === 0 ? (
                <div className="py-4 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                  <RefreshCw className="size-3.5 animate-spin text-primary" /> Analyzing repository assets...
                </div>
              ) : (
                assets.map((asset, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.15, delay: i * 0.03 }}
                    className="p-2.5 border border-border/60 rounded-lg bg-muted/20 flex items-center justify-between text-xs hover:border-primary/40 transition-colors"
                  >
                    <div className="min-w-0 pr-2">
                      <div className="font-semibold text-foreground truncate">{asset.asset_name}</div>
                      <div className="text-[11px] text-muted-foreground truncate font-mono">{asset.location}</div>
                    </div>
                    <Badge tone={asset.criticality === "CRITICAL" ? "danger" : "neutral"} className="shrink-0 text-[10px]">
                      {asset.criticality}
                    </Badge>
                  </motion.div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <div className="p-4 pb-0 flex items-center justify-between font-semibold text-sm">
              <span className="flex items-center gap-2 text-foreground">
                <Layers className="size-4 text-primary" /> Security Assessments ({assessments.length})
              </span>
            </div>
            <CardContent className="space-y-2 pt-3 max-h-[22rem] overflow-y-auto">
              {assessments.length === 0 ? (
                <div className="py-4 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                  <RefreshCw className="size-3.5 animate-spin text-primary" /> Evaluating risk scenarios...
                </div>
              ) : (
                assessments.map((ass, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.15, delay: i * 0.03 }}
                    onClick={() => { setSelectedAssessment(ass); setVerificationResult(null); }}
                    className={`p-3 border rounded-lg cursor-pointer transition-all ${
                      selectedAssessment?.risk_type === ass.risk_type && selectedAssessment?.asset_name === ass.asset_name
                        ? "border-primary bg-primary/15 shadow-sm"
                        : "border-border/60 hover:bg-muted/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-foreground font-mono">{ass.risk_type}</span>
                      <Badge tone={ass.severity === "HIGH" ? "danger" : ass.severity === "MEDIUM" ? "warning" : "neutral"} className="text-[10px]">
                        {ass.severity}
                      </Badge>
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-1 truncate">{ass.affected_scope}</div>
                  </motion.div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Assessment Detail & Risk Path Visualization */}
        <div className="lg:col-span-2 space-y-6">
          <AnimatePresence mode="wait">
            {selectedAssessment ? (
              <motion.div
                key={selectedAssessment.asset_name + selectedAssessment.risk_type}
                initial={{ opacity: 0, x: 15 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -15 }}
                transition={{ duration: 0.2 }}
              >
                <Card className="border-primary/40 shadow-lg">
                  <div className="p-5 pb-0 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <Badge tone="primary" className="mb-2">
                        {selectedAssessment.asset_name}
                      </Badge>
                      <div className="text-xl font-bold font-mono text-foreground">{selectedAssessment.risk_type}</div>
                      <div className="text-xs text-muted-foreground font-mono">{selectedAssessment.affected_scope}</div>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => handleVerifyRemediation(selectedAssessment)}
                      disabled={remediating}
                      className="gap-2"
                    >
                      {remediating ? <RefreshCw className="size-4 animate-spin" /> : <ShieldCheck className="size-4 text-emerald-400" />}
                      {remediating ? "Verifying AST Fix..." : "Verify Remediation"}
                    </Button>
                  </div>

                  <CardContent className="space-y-6 pt-4">
                    {/* Verification result alert */}
                    {verificationResult && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={`p-3.5 rounded-lg text-xs font-mono flex items-center gap-2 ${
                          verificationResult.includes("VERIFIED_FIXED")
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                            : "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                        }`}
                      >
                        <CheckCircle2 className="size-4 shrink-0" />
                        <span>{verificationResult}</span>
                      </motion.div>
                    )}

                    {/* Reasoning Chain */}
                    <div>
                      <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2 flex items-center gap-1.5">
                        <Zap className="size-3.5 text-primary" /> Reasoning Chain
                      </h4>
                      <p className="text-xs bg-muted/30 p-3 rounded-lg leading-relaxed text-foreground border border-border/40 font-sans">
                        {selectedAssessment.reasoning}
                      </p>
                    </div>

                    {/* Risk Path Visualization */}
                    <div>
                      <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-3 flex items-center gap-2">
                        <GitBranch className="size-4 text-primary" /> Risk & Attack Path Visualization
                      </h4>
                      <div className="space-y-2">
                        {selectedAssessment.attack_path?.map((step, idx) => (
                          <div key={idx} className="flex items-center gap-3 text-xs bg-muted/20 p-2.5 rounded-md border border-border/40">
                            <span className="font-bold text-primary font-mono shrink-0">Step {idx + 1}</span>
                            <ArrowRight className="size-3.5 text-muted-foreground shrink-0" />
                            <span className="text-foreground">{step}</span>
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
                          <Badge key={i} tone={c.state === "PRESENT" ? "success" : "danger"} className="text-xs font-mono">
                            {c.control}: {c.state}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    {/* Remediation Guidance */}
                    <div>
                      <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
                        Recommended AST Remediation
                      </h4>
                      <div className="text-xs font-mono bg-card p-3 rounded-lg border border-emerald-500/30 text-emerald-400 leading-relaxed">
                        {selectedAssessment.remediation}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ) : (
              <Card>
                <CardContent className="p-8 text-center text-muted-foreground text-xs">
                  Select a security assessment from the left panel to inspect attack paths and verify remediations.
                </CardContent>
              </Card>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
