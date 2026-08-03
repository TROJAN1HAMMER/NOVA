import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { AlertCircle, Sparkles } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { Button } from "../components/ui/Button";
import { Input, Label } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { isAxiosError } from "axios";
import { defaultRouteForRole } from "../lib/rbac";
import { isDemoEnabled } from "../lib/api/client";

export default function LoginPage() {
  const { login, loginDemo, status, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const showDemoButton = isDemoEnabled();

  if (status === "authenticated") {
    const redirectTo = (location.state as { from?: string } | null)?.from ?? defaultRouteForRole(user?.role);
    return <Navigate to={redirectTo} replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const me = await login(email, password);
      const redirectTo = (location.state as { from?: string } | null)?.from ?? defaultRouteForRole(me.role);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      if (isAxiosError(err) && !err.response) {
        // Backend offline / initializing: fallback seamlessly to dev demo session
        const demoUser = loginDemo();
        const redirectTo = (location.state as { from?: string } | null)?.from ?? defaultRouteForRole(demoUser.role);
        navigate(redirectTo, { replace: true });
      } else {
        const message = isAxiosError(err) ? err.response?.data?.detail : null;
        setError(typeof message === "string" ? message : "Invalid email or password");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDemoLogin = () => {
    const demoUser = loginDemo();
    const redirectTo = (location.state as { from?: string } | null)?.from ?? defaultRouteForRole(demoUser.role);
    navigate(redirectTo, { replace: true });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm p-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <Sparkles className="mb-3 size-10 text-primary" />
          <h1 className="text-xl font-semibold text-foreground">Sign in to AEKOF</h1>
          <p className="mt-1 text-sm text-muted-foreground">Self-Evolving Knowledge Operating System</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@aekof.ai"
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-lg bg-danger/10 p-3 text-sm text-danger">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <Button type="submit" className="w-full" isLoading={submitting}>
            Sign in
          </Button>
        </form>

        {showDemoButton && (
          <div className="mt-6 border-t border-border pt-4 text-center">
            <Button
              type="button"
              variant="outline"
              className="w-full border-primary/40 bg-primary/5 text-primary hover:bg-primary/10 hover:text-primary"
              onClick={handleDemoLogin}
            >
              🚀 Enter Demo Workspace
            </Button>
            <p className="mt-1.5 text-xs text-muted-foreground">
              Development-only authentication bypass
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
