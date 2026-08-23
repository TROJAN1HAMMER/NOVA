import { lazy, Suspense, type JSX, type LazyExoticComponent } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { RequireRole } from "./components/layout/RequireRole";
import { FullPageSpinner } from "./components/ui/Spinner";
import { useAuth } from "./hooks/useAuth";
import { defaultRouteForRole } from "./lib/rbac";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const SignupPage = lazy(() => import("./pages/SignupPage"));
const LandingPage = lazy(() => import("./pages/LandingPage"));
const AssistantPage = lazy(() => import("./pages/AssistantPage"));
const SourceStudioPage = lazy(() => import("./pages/SourceStudioPage"));
const KnowledgeBasePage = lazy(() => import("./pages/KnowledgeBasePage"));
const GraphExplorerPage = lazy(() => import("./pages/GraphExplorerPage"));
const MemoryPage = lazy(() => import("./pages/MemoryPage"));
const KnowledgeEvolutionPage = lazy(() => import("./pages/KnowledgeEvolutionPage"));
const RagOperationsPage = lazy(() => import("./pages/RagOperationsPage"));
const BenchmarkPage = lazy(() => import("./pages/BenchmarkPage"));
const ExecutiveDashboardPage = lazy(() => import("./pages/ExecutiveDashboardPage"));
const MyActivityPage = lazy(() => import("./pages/MyActivityPage"));
const AdminUsersPage = lazy(() => import("./pages/AdminUsersPage"));
const ScanPage = lazy(() => import("./pages/ScanPage"));
const ScanDetailsPage = lazy(() => import("./pages/ScanDetailsPage"));

function SuspendedRoute({ Component }: { Component: LazyExoticComponent<() => JSX.Element> }) {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <Component />
    </Suspense>
  );
}

function DefaultRedirect() {
  const { status, user } = useAuth();
  if (status === "loading") return <FullPageSpinner />;
  if (status === "unauthenticated") return <Navigate to="/login" replace />;
  return <Navigate to={defaultRouteForRole(user?.role)} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SuspendedRoute Component={LandingPage} />} />
      <Route path="/login" element={<SuspendedRoute Component={LoginPage} />} />
      <Route path="/signup" element={<SuspendedRoute Component={SignupPage} />} />

      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route
          path="assistant"
          element={
            <RequireRole routeKey="assistant">
              <SuspendedRoute Component={AssistantPage} />
            </RequireRole>
          }
        />
        <Route
          path="source-studio"
          element={
            <RequireRole routeKey="source-studio">
              <SuspendedRoute Component={SourceStudioPage} />
            </RequireRole>
          }
        />
        <Route
          path="knowledge"
          element={
            <RequireRole routeKey="knowledge">
              <SuspendedRoute Component={KnowledgeBasePage} />
            </RequireRole>
          }
        />
        <Route
          path="graph-explorer"
          element={
            <RequireRole routeKey="graph-explorer">
              <SuspendedRoute Component={GraphExplorerPage} />
            </RequireRole>
          }
        />
        <Route
          path="memory"
          element={
            <RequireRole routeKey="memory">
              <SuspendedRoute Component={MemoryPage} />
            </RequireRole>
          }
        />
        <Route
          path="knowledge-evolution"
          element={
            <RequireRole routeKey="knowledge-evolution">
              <SuspendedRoute Component={KnowledgeEvolutionPage} />
            </RequireRole>
          }
        />
        <Route
          path="rag-operations"
          element={
            <RequireRole routeKey="rag-operations">
              <SuspendedRoute Component={RagOperationsPage} />
            </RequireRole>
          }
        />
        <Route
          path="benchmarks"
          element={
            <RequireRole routeKey="benchmarks">
              <SuspendedRoute Component={BenchmarkPage} />
            </RequireRole>
          }
        />
        <Route
          path="executive"
          element={
            <RequireRole routeKey="executive">
              <SuspendedRoute Component={ExecutiveDashboardPage} />
            </RequireRole>
          }
        />
        <Route
          path="my-activity"
          element={
            <RequireRole routeKey="my-activity">
              <SuspendedRoute Component={MyActivityPage} />
            </RequireRole>
          }
        />
        <Route
          path="admin/users"
          element={
            <RequireRole routeKey="admin/users">
              <SuspendedRoute Component={AdminUsersPage} />
            </RequireRole>
          }
        />
        <Route
          path="scans"
          element={
            <RequireRole routeKey="scans">
              <SuspendedRoute Component={ScanPage} />
            </RequireRole>
          }
        />
        <Route
          path="scans/:scanId"
          element={
            <RequireRole routeKey="scans">
              <SuspendedRoute Component={ScanDetailsPage} />
            </RequireRole>
          }
        />
      </Route>

      <Route path="*" element={<DefaultRedirect />} />
    </Routes>
  );
}
