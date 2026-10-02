// Response types for the CodePulse API. These mirror the documents built by
// backend/app/services/result_builder.py; the backend is the source of truth.

export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export type StageStatus = "pending" | "running" | "done" | "skipped" | "failed";
export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface Stage {
  key: string;
  label: string;
  status: StageStatus;
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Job {
  id: string;
  repository_id: string;
  status: JobStatus;
  current_stage: string | null;
  progress: number;
  stages: Stage[];
  warnings: string[];
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  queue_position: number | null;
}

export interface Repository {
  id: string;
  owner: string;
  name: string;
  full_name: string;
  url: string;
  created_at: string;
  last_analyzed_at: string | null;
  health_score: number | null;
  debt_score: number | null;
  risk_signal: number | null;
  status: "never_analyzed" | JobStatus;
  latest_job: Job | null;
  has_results: boolean;
}

export interface RepositoryCreated {
  repository: Repository;
  job: Job | null;
  created: boolean;
}

/** Every result section is wrapped with the job it came from. */
export interface Envelope {
  job_id: string;
  analyzed_at: string | null;
}

export interface Unavailable {
  available: false;
  reason: string;
}

export interface Metric<T = number> {
  value: T | null;
  available: boolean;
  reason: string | null;
}

export interface Overview extends Envelope {
  repository: {
    owner: string | null;
    name: string;
    full_name: string;
    url: string | null;
    analyzed_at: string;
  };
  languages: Record<string, number>;
  analyzed_languages: Record<string, number>;
  total_files: number | null;
  analyzed_files: number;
  unsupported_files: number | null;
  commits: number | null;
  metrics: {
    health_score: Metric;
    health_level: string | null;
    code_quality: Metric;
    git_stability: Metric;
    maintainability: Metric;
    historical_risk_signal: Metric;
    elevated_risk_files: number | null;
    technical_debt: Metric;
    technical_debt_level: string | null;
    duplicate_groups: Metric;
    dependencies: Metric;
    contributors: Metric;
  };
  warnings: string[];
}

export interface TopFile {
  file: string;
  value: number;
}

export interface HealthComponent {
  key: "code_quality" | "git_stability" | "defect_risk" | "maintainability";
  label: string;
  description: string;
  value: number | null;
  available: boolean;
  weight: number;
  effective_weight: number | null;
  reason: string | null;
}

export interface HealthAvailable {
  available: true;
  overall_score: number | null;
  health_level: string | null;
  components: HealthComponent[];
  evidence: {
    code_quality: {
      average_complexity: number | null;
      average_nesting_depth: number | null;
      average_comment_ratio: number | null;
      most_complex_files: TopFile[];
      deepest_nesting_files: TopFile[];
    };
    git_stability: {
      total_churn: number;
      files_with_bug_fix_activity: number;
      highest_churn_files: TopFile[];
      most_bug_fix_activity: TopFile[];
    };
    defect_risk: {
      average_signal: number | null;
      risk_level_counts: Record<string, number>;
      highest_signal_files: TopFile[];
    };
    maintainability: {
      average_index: number | null;
      lowest_maintainability_files: TopFile[];
    };
  };
}
export type Health = Envelope & (HealthAvailable | Unavailable);

export interface FileRow {
  file: string;
  directory: string;
  language: string | null;
  loc: number | null;
  complexity: number | null;
  functions: number | null;
  classes: number | null;
  nesting_depth: number | null;
  comment_ratio: number | null;
  commit_count: number | null;
  contributors: number | null;
  code_churn: number | null;
  bug_fix_commits: number | null;
  file_age_days: number | null;
  maintainability: number | null;
  risk_probability: number | null;
  risk_level: string | null;
  debt_score: number | null;
  debt_level: string | null;
  review_findings: number;
}

export interface ModelResult {
  model: string;
  selected: boolean;
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  roc_auc: number | null;
}

export interface Risk extends Envelope {
  available: boolean;
  reason: string | null;
  label_definition: string;
  selected_model: string | null;
  models: ModelResult[];
  class_distribution: Record<string, number> | null;
  files: FileRow[];
}

export type DebtLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface DebtRow {
  file: string;
  technical_debt_score: number;
  technical_debt_level: DebtLevel;
  complexity_component: number | null;
  ml_component: number | null;
  duplication_component: number | null;
  maintainability_component: number | null;
  churn_component: number | null;
  duplication_available: boolean;
  ml_available: boolean;
  maintainability_available: boolean;
  debt_reasons: string[];
}

export interface DebtAvailable {
  available: true;
  repository_debt_score: number | null;
  debt_level: DebtLevel | null;
  distribution: Record<DebtLevel, number>;
  high_critical_percentage: number | null;
  duplication_available: boolean;
  weights: Record<string, number>;
  files: DebtRow[];
}
export type Debt = Envelope & (DebtAvailable | Unavailable);

export interface DuplicatePair {
  file_a: string;
  file_b: string;
  similarity_score: number;
  similarity_level: string;
  matching_token_count: number;
  evidence: string;
}

export interface DuplicateGroup {
  id: number;
  files: string[];
  pair_count: number;
  max_similarity: number;
  severity: string;
  pairs: DuplicatePair[];
}

export interface DuplicatesAvailable {
  available: true;
  duplicate_groups: number;
  high_similarity_pairs: number;
  pair_count: number;
  groups: DuplicateGroup[];
  pairs: DuplicatePair[];
  limitations: string;
}
export type Duplicates = Envelope &
  (DuplicatesAvailable | (Unavailable & { limitations: string }));

export interface GraphNode {
  id: string;
  label: string;
  directory: string;
  language: string | null;
  incoming: number;
  outgoing: number;
  total: number;
  centrality: number;
  risk_probability: number | null;
  risk_level: string | null;
  debt_score: number | null;
  debt_level: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface ArchitectureAvailable {
  available: true;
  files: number;
  dependency_relationships: number;
  unresolved_dependencies: number;
  graphviz_available: boolean;
  nodes: AnnotatedNode[];
  edges: GraphEdge[];
  candidate_count: number;
  truncated: boolean;
  focus: string | null;
  directory: string | null;
  directories: { directory: string; count: number }[];
  most_connected: AnnotatedNode[];
  unresolved: { file: string; imports: string[] }[];
}
export type Architecture = Envelope & (ArchitectureAvailable | Unavailable);

export interface Finding {
  id: number;
  file: string;
  rule_id: string;
  severity: string;
  title: string;
  evidence: string;
  metric: string;
  value: number | string | null;
  recommendation: string;
}

export interface ReviewAvailable {
  available: true;
  files_reviewed: number | null;
  total_findings: number;
  counts: Record<string, number>;
  findings: Finding[];
}
export type Review = Envelope & (ReviewAvailable | Unavailable);

export type IssueState = "OPEN" | "CLOSED" | "UNKNOWN";

export interface Issue {
  number: number;
  title: string;
  state: IssueState;
  labels: string[];
  url: string | null;
  author: string | null;
  comments: number | null;
  created_at: string | null;
  updated_at: string | null;
  description: string;
  related_files: string[];
  /** Added by the enriched /issues endpoint (absent on older responses). */
  signals?: IssueSignal[];
  difficulty?: IssueDifficulty;
  match_count?: number;
}

export interface IssueSignal {
  kind: "beginner" | "help_wanted" | "documentation";
  label: string;
}

export interface IssueDifficulty {
  status: "ESTIMATED" | "UNAVAILABLE";
  level: Difficulty | null;
  base_level?: Difficulty;
  raised?: boolean;
  basis: string[];
  files_considered: string[];
  match_strength?: "strong" | "weak";
  reason: string | null;
}

export interface Issues extends Envelope {
  available: boolean;
  reason: string | null;
  note?: string;
  counts?: Record<IssueState, number>;
  difficulty_note?: string;
  issues: Issue[];
}

export type Difficulty = "BEGINNER" | "INTERMEDIATE" | "ADVANCED";

export interface Opportunity {
  rank: number;
  title: string;
  file: string;
  priority: string;
  difficulty: Difficulty;
  suggested_for: string;
  reasons: string[];
  suggested_action: string;
  score: number;
  opportunity_score: number;
  impact: string;
  centrality: number | null;
  related_files: string[];
  open_issue_count: number;
  closed_issue_count: number;
  related_issue_status: string;
  review_finding_count: number;
}

export interface Opportunities extends Envelope {
  available: boolean;
  reason: string | null;
  disclaimer?: string;
  items: Opportunity[];
}

export interface FileListItem {
  file: string;
  language: string | null;
  risk_level: string | null;
  debt_level: string | null;
  has_intelligence: boolean;
}

export interface FileList extends Envelope {
  files: FileListItem[];
  limited: boolean;
}

export interface IssueMatch {
  number: number;
  title: string;
  body: string;
  state: string;
  labels: string[];
  url: string | null;
  author?: string;
  relevance: string;
  score: number;
  evidence: string[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ContributionPlan {
  target: string;
  contribution_type: string;
  difficulty: Difficulty;
  priority: string;
  steps: string[];
}

export interface FileIntelligence extends Envelope, Partial<FileContributorIntel> {
  file: string;
  explanation?: {
    file: string;
    risk_level: string;
    bug_probability: number;
    metrics: {
      loc: number;
      complexity: number;
      nesting_depth: number;
      commit_count: number;
      bug_fix_commits: number;
      contributors: number;
      code_churn: number;
      maintainability: number | null;
    };
    reasons: string[];
    recommendation: string;
    complexity_high: boolean;
    churn_high: boolean;
  };
  explanation_error?: string;
  related_files?: { file: string; reason: string }[];
  impact?: {
    file: string;
    depends_on: string[];
    used_by: string[];
    dependent_count?: number;
    dependency_count?: number;
    total_connections?: number;
    impact_level: string;
    reason: string;
    checklist?: string[];
    available: boolean;
  } | null;
  history?: {
    file: string;
    commit_count: number;
    contributors: number;
    lines_added?: number;
    lines_deleted?: number;
    code_churn: number;
    bug_fix_commits: number;
    file_age_days?: number;
    first_modified?: string | null;
    last_modified?: string | null;
    recent_activity: string;
    explanation: string;
  } | null;
  issues?: IssueMatch[];
  plan?: ContributionPlan;
  open_issue_number?: number | null;
  summary?: FileRow | null;
  debt?: DebtRow | null;
  review_findings?: Omit<Finding, "id">[];
  duplicates?: DuplicatePair[];
  opportunity?: Omit<Opportunity, "rank" | "review_finding_count"> | null;
}

// ---------------------------------------------------------------------------
// Contributor guide (backend/app/services/guide.py)
// ---------------------------------------------------------------------------

export interface DirectoryGroup {
  id: string;
  label: string;
  name_hint: string | null;
  structure: string;
  file_count: number;
  test_files: number;
  loc: number;
  languages: Record<string, number>;
  high_risk_files: number;
  high_debt_files: number;
  opportunities: number;
  incoming: number;
  outgoing: number;
  internal_dependencies: number;
  key_files: { file: string; total: number; roles: string[] }[];
}

export interface StartHereItem {
  file: string;
  label: string;
  reason: string;
}

export interface RoadmapItem {
  file: string;
  title: string | null;
  opportunity_score: number | null;
  open_issue_count: number;
}

export interface Guide extends Envelope {
  repository: Overview["repository"];
  facts: {
    languages: Record<string, number>;
    files: number;
    total_files: number | null;
    lines_of_code: number;
    contributors: number | null;
    commits: number | null;
    test_files: number;
    most_changed_files: { file: string; commits: number }[];
    issues_available: boolean;
    open_issues: number | null;
  };
  architecture_available: boolean;
  architecture_reason: string | null;
  groups: { depth: number; groups: DirectoryGroup[]; edges: { source: string; target: string; count: number }[]; basis?: string };
  start_here: StartHereItem[];
  high_risk_areas: { file: string; risk_level: string | null; risk_probability: number | null }[];
  roadmap: {
    BEGINNER: RoadmapItem[];
    INTERMEDIATE: RoadmapItem[];
    ADVANCED: RoadmapItem[];
    BEGINNER_total: number;
    INTERMEDIATE_total: number;
    ADVANCED_total: number;
  };
  unresolved_dependencies: number | null;
  notes: string[];
}

export interface WhyCheck {
  key: string;
  label: string;
  met: boolean;
  detail: string;
}

export interface WhyThisFile {
  checks: WhyCheck[];
  why_it_matters: string;
  engine_reasons: string[];
  note: string;
}

export interface DifficultyBasis {
  level: Difficulty | null;
  summary: string | null;
  conditions_met: string[];
  factors: Record<string, number | string | null>;
  rule: string;
  disclaimer: string;
}

export type IssueStatus = "ISSUE_AVAILABLE" | "NO_ISSUE" | "UNAVAILABLE";

export interface EnrichedOpportunity extends Opportunity {
  risk_probability: number | null;
  risk_level: string | null;
  debt_score: number | null;
  debt_level: string | null;
  connectivity: string | null;
  used_by: number | null;
  depends_on: number | null;
  issue_status: IssueStatus;
  roles: string[];
  why: WhyThisFile;
  difficulty_basis: DifficultyBasis | null;
}

export interface EnrichedOpportunities extends Envelope {
  available: boolean;
  reason: string | null;
  disclaimer?: string;
  issues_available: boolean;
  items: EnrichedOpportunity[];
}

export interface ReadinessItem {
  key: string;
  status: "ok" | "missing" | "unavailable";
  label: string;
}

export interface RelatedTests {
  available: boolean;
  detected: { file: string; basis: string }[];
  heuristic: { file: string; basis: string }[];
  reason: string | null;
}

export interface ChangeImpact {
  available: boolean;
  reason?: string;
  file?: string;
  upstream: string[];
  downstream: string[];
  indirect: string[];
  affected_areas: { directory: string; files: number }[];
  unresolved_imports: string[];
  truncated: boolean;
  note: string;
}

export interface FileContributorIntel {
  roles: { role: string; basis: string }[];
  connectivity: string | null;
  directory: string;
  tests: RelatedTests;
  readiness: ReadinessItem[];
  why: WhyThisFile;
  difficulty_basis: DifficultyBasis | null;
  change_impact: ChangeImpact;
  issues_available: boolean;
}

export interface AnnotatedNode extends GraphNode {
  connectivity: string;
  roles: string[];
  opportunity: { difficulty: Difficulty; score: number; rank: number } | null;
}

export interface IssueFiles extends Envelope {
  issue: Issue;
  basis: string;
  files: {
    file: string;
    relevance: string | null;
    score: number | null;
    evidence: string[];
    risk_level: string | null;
    debt_level: string | null;
    opportunity: { difficulty: Difficulty; score: number } | null;
  }[];
}

export interface IssueWorkFile {
  file: string;
  relevance: string | null;
  score: number | null;
  evidence: string[];
  direct: boolean;
  primary: boolean;
  risk_level: string | null;
  debt_level: string | null;
  difficulty: Difficulty | null;
  roles: string[];
  connectivity: string | null;
  used_by: string[];
  depends_on: string[];
  tests: RelatedTests;
}

export interface IssueWorkStep {
  key: string;
  title: string;
  detail: string;
  files: string[];
}

export interface IssueWork extends Envelope {
  issue: Issue & { signals: IssueSignal[] };
  difficulty: IssueDifficulty;
  files: IssueWorkFile[];
  more_files: number;
  steps: IssueWorkStep[];
  search: { terms: string[]; url: string } | null;
  basis: string;
  files_limited: boolean;
}
