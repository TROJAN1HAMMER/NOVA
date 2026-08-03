import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { AlertCircle, ShieldCheck } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { authApi } from "../lib/api/auth";
import { Button } from "../components/ui/Button";
import { Input, Label } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { isAxiosError } from "axios";
import { defaultRouteForRole } from "../lib/rbac";

export default function SignupPage() {
  const { login, status, user } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated") {
    return <Navigate to={defaultRouteForRole(user?.role)} replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await authApi.register(email, password, fullName);
      // Registration alone doesn't establish a session — sign the new user
      // in immediately so they land in the dashboard without a second,
      // redundant login step. Self-registration always lands on the
      // least-privileged `read_only` role, so route by role rather than
      // assuming /repositories (read_only can't reach it).
      const me = await login(email, password);
      navigate(defaultRouteForRole(me.role), { replace: true });
    } catch (err) {
      if (isAxiosError(err) && !err.response) {
        // Same distinction LoginPage draws: no response at all means the
        // backend is unreachable/down or blocked by CORS, not a real
        // validation failure — worth telling the user that directly.
        setError("Could not reach the NOVA API. Check that it's running and that this origin is allowed by its CORS configuration.");
      } else {
        const message = isAxiosError(err) ? err.response?.data?.detail : null;
        setError(typeof message === "string" ? message : "Could not create your account. Please check your details and try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm p-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <ShieldCheck className="mb-3 size-10 text-primary" />
          <h1 className="text-xl font-semibold text-foreground">Create your NOVA account</h1>
          <p className="mt-1 text-sm text-muted-foreground">AI-Powered DevSecOps for Banking Applications</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="fullName">Full name</Label>
            <Input
              id="fullName"
              type="text"
              autoComplete="name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Jane Doe"
            />
          </div>
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@bank.example"
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
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
            Create account
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link to="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
