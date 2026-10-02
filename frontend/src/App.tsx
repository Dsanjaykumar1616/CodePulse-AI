import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./lib/auth";
import { ErrorBoundary } from "./components/ErrorBoundary";
import AppLayout from "./layouts/AppLayout";
import RepoLayout from "./layouts/RepoLayout";
import Landing from "./pages/Landing";
import { Login, Signup } from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Repositories from "./pages/Repositories";
import AnalysisProgress from "./pages/AnalysisProgress";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";
import RepoOverview from "./pages/repo/Overview";
import StartHere from "./pages/repo/StartHere";
import ExplorerPage from "./pages/repo/Explorer";
import HealthPage from "./pages/repo/Health";
import RiskPage from "./pages/repo/Risk";
import DebtPage from "./pages/repo/Debt";
import DuplicatesPage from "./pages/repo/Duplicates";
import ArchitecturePage from "./pages/repo/Architecture";
import ReviewPage from "./pages/repo/Review";
import IssuesPage from "./pages/repo/Issues";
import IssueWorkPage from "./pages/repo/IssueWork";
import OpportunitiesPage from "./pages/repo/Opportunities";
import FilePage from "./pages/repo/FilePage";
import { Spinner } from "./components/ui";

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Checking your session" />
      </div>
    );
  }
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "authenticated") return <Navigate to="/app" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/login"
          element={
            <GuestOnly>
              <Login />
            </GuestOnly>
          }
        />
        <Route
          path="/signup"
          element={
            <GuestOnly>
              <Signup />
            </GuestOnly>
          }
        />
        <Route
          path="/app"
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="repositories" element={<Repositories />} />
          <Route path="analysis/:jobId" element={<AnalysisProgress />} />
          <Route path="settings" element={<Settings />} />
          <Route path="r/:repoId" element={<RepoLayout />}>
            <Route index element={<StartHere />} />
            <Route path="metrics" element={<RepoOverview />} />
            <Route path="explore" element={<ExplorerPage />} />
            <Route path="health" element={<HealthPage />} />
            <Route path="risk" element={<RiskPage />} />
            <Route path="debt" element={<DebtPage />} />
            <Route path="duplicates" element={<DuplicatesPage />} />
            <Route path="architecture" element={<ArchitecturePage />} />
            <Route path="review" element={<ReviewPage />} />
            <Route path="issues" element={<IssuesPage />} />
            <Route path="issues/:issueNumber" element={<IssueWorkPage />} />
            <Route path="opportunities" element={<OpportunitiesPage />} />
            <Route path="file" element={<FilePage />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<NotFound standalone />} />
      </Routes>
    </ErrorBoundary>
  );
}
