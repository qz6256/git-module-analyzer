/** 与 ARCHITECTURE.md 契约及后端 schemas 对齐的领域类型 */

// ---------------- 通用 ----------------
export interface Paged<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ApiError {
  detail: string
}

// ---------------- 用户与权限 ----------------
export interface Role {
  id: number
  code: string
  name: string
  description?: string
}

export interface GitIdentity {
  id: number
  name: string
  email: string
  source?: 'auto' | 'manual'
  commit_count?: number
  last_seen_at?: string | null
  user_id?: number | null
}

export interface User {
  id: number
  username: string
  email: string
  display_name?: string
  status?: 'active' | 'disabled'
  is_superuser?: boolean
  last_login_at?: string | null
  created_at?: string
  roles?: Role[]
  git_identity?: GitIdentity | null
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  display_name?: string
}

export interface UserUpdateInput {
  email?: string
  display_name?: string
  status?: 'active' | 'disabled'
  is_superuser?: boolean
}

export interface MemberOut {
  user_id: number
  username?: string
  display_name?: string
  email?: string
  role_id?: number
  role_code?: string
  role_name?: string
  joined_at?: string
}

export interface MemberCreateInput {
  user_id: number
  role_code: string
}

// ---------------- 项目与仓库 ----------------
export type ProjectStatus = 'planning' | 'active' | 'archived'
export type RepoType = 'frontend' | 'backend' | 'app' | 'miniprogram' | 'other'
export type RepoStatus = 'pending' | 'initializing' | 'ready' | 'syncing' | 'error'

export interface ProjectStats {
  module_count: number
  file_count: number
  commit_count: number
  pending_links: number
  issue_count?: number
}

export interface Project {
  id: number
  name: string
  code?: string
  city?: string
  department?: string
  business_domain?: string
  owner_id?: number
  description?: string
  start_date?: string | null
  planned_end_date?: string | null
  status: ProjectStatus
  tags?: string[]
  created_at?: string
  updated_at?: string
  stats?: ProjectStats
  members?: MemberOut[]
  repositories?: Repository[]
}

export interface ProjectCreateInput {
  name: string
  city?: string
  department?: string
  business_domain?: string
  description?: string
  start_date?: string
  planned_end_date?: string
  status?: ProjectStatus
  tags?: string[]
}

export interface Repository {
  id: number
  project_id?: number
  name: string
  display_name?: string
  source: string
  source_type?: 'local' | 'remote'
  local_path?: string
  repo_type?: RepoType
  default_branch?: string
  branches?: string[]
  auth_type?: GitAuthType
  has_credential?: boolean
  status?: RepoStatus
  status_message?: string
  last_analyzed_at?: string | null
  created_at?: string
}

export type GitAuthType = 'none' | 'token' | 'password' | 'ssh_key'

export interface RepositoryCreateInput {
  name: string
  source: string
  repo_type?: RepoType
  display_name?: string
  source_type?: 'local' | 'remote'
  default_branch?: string
  branches?: string[]
  auth_type?: GitAuthType
  credential?: string
}

export interface RepositoryUpdateInput {
  name?: string
  display_name?: string
  repo_type?: RepoType
  source?: string
  default_branch?: string
  branches?: string[]
  auth_type?: GitAuthType
  credential?: string
}

export interface RecentActivity {
  id?: number
  type?: string
  commit_sha?: string
  commit_message?: string
  message?: string
  author?: string
  committed_at?: string
  risk_level?: string
  repo_id?: number
  repo_name?: string
}

export interface RepoBreakdown {
  repo_id?: number
  repo_name?: string
  name?: string
  display_name?: string
  repo_type?: RepoType
  module_count?: number
  file_count?: number
  commit_count?: number
  issue_count?: number
}

export interface ProjectOverview extends ProjectStats {
  recent_activity: RecentActivity[]
  repo_breakdown: RepoBreakdown[]
}

export interface JobInfo {
  job_id: string
  status: string
  progress: number
  message: string
  result?: unknown
}

export interface BranchState {
  id: number
  repo_id: number
  branch: string
  last_commit_sha: string
  updated_at?: string
}

// ---------------- 分析产物 ----------------
export interface ProjectModule {
  id: number
  repo_id: number
  project_id?: number
  name: string
  path_rules: string[]
  responsibility?: string
  doc_path?: string
  file_count?: number
  one_liner?: string
  current_doc?: string
  evolution_line?: string
  risk_level?: string
  status?: 'active' | 'dormant' | 'new'
  last_commit_sha?: string
  change_count?: number
  created_at?: string
}

export interface ModuleChangeEvent {
  id: number
  repo_id: number
  module_id: number
  module_name?: string
  commit_sha: string
  branch?: string
  author?: string
  committed_at?: string | null
  commit_message?: string
  summary?: string
  capability_delta?: string
  affected_files?: string[]
  motivation?: string
  evidence_source?: string
  risk_level?: string
  analysis_mode?: string
  created_at?: string
}

export interface ModuleDetail {
  module: ProjectModule
  timeline: ModuleChangeEvent[]
  files: SourceFile[]
}

export interface ModuleCandidate {
  id: number
  repo_id: number
  name: string
  path_rules: string[]
  reason?: string
  evidence_commit?: string
  sample_files?: string[]
  status?: 'pending' | 'confirmed' | 'ignored'
  created_at?: string
  decided_at?: string | null
}

export interface DiffStats {
  additions?: number
  deletions?: number
  files_changed?: number
  [key: string]: unknown
}

export interface CodeBlock {
  name?: string
  change_type?: string
  description?: string
  [key: string]: unknown
}

export interface SourceFile {
  id: number
  repo_id: number
  path: string
  module_name?: string
  language?: string
  one_liner?: string
  current_doc?: string
  evolution_line?: string
  baseline_doc_path?: string
  last_commit_sha?: string
  risk_level?: string
  change_count?: number
  updated_at?: string
}

export interface FileChangeEvent {
  id: number
  source_file_id: number
  repo_id: number
  commit_sha: string
  branch?: string
  author?: string
  committed_at?: string | null
  commit_message?: string
  summary?: string
  blocks?: CodeBlock[]
  doc_update?: string
  motivation?: string
  evidence_source?: string
  risk_level?: string
  diff_stats?: DiffStats
  analysis_mode?: string
  created_at?: string
}

export interface FileDetail {
  file: SourceFile
  timeline: FileChangeEvent[]
}

export interface CommitAnalysis {
  id: number
  repo_id: number
  project_id?: number
  commit_sha: string
  branch?: string
  author?: string
  committed_at?: string | null
  message?: string
  summary?: string
  motivation?: string
  evidence_source?: string
  affected_files?: string[]
  diff_stats?: DiffStats
  risk_level?: string
  is_high_signal?: boolean
  filter_reason?: string
  analysis_mode?: string
  created_at?: string
}

// ---------------- 需求 / 缺陷 ----------------
export type Assessment = 'strong' | 'weak' | 'review'
export type ReviewStatus = 'pending' | 'confirmed' | 'rejected'

export interface Issue {
  id: number
  repo_id: number
  project_id?: number
  external_id: string
  issue_type: 'bug' | 'story' | string
  title?: string
  description?: string
  status?: string
  source?: string
  external_url?: string
  reporter?: string
  keywords?: string[]
  related_paths?: string[]
  occurred_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface IssueCreateInput {
  external_id: string
  issue_type?: string
  title?: string
  description?: string
  status?: string
  source?: string
  external_url?: string
  reporter?: string
  keywords?: string[]
  related_paths?: string[]
  occurred_at?: string
}

export interface SignalMatrix {
  explicit_ref?: boolean
  file_hit?: boolean
  test_change?: boolean
  fix_declaration?: boolean
  [key: string]: boolean | undefined
}

export interface IssueCommitLink {
  id: number
  repo_id: number
  issue_id: number
  commit_sha: string
  branch?: string
  link_type?: 'explicit' | 'semantic' | 'inferred' | 'manual'
  confidence?: number
  evidence?: string
  signals?: SignalMatrix
  assessment?: Assessment
  assessment_label?: string
  assessment_note?: string
  review_status?: ReviewStatus
  llm_note?: string
  decided_at?: string | null
  created_at?: string
  // 详情接口可能附带关联提交信息
  commit?: CommitAnalysis
  message?: string
  author?: string
  committed_at?: string
  commits?: CommitAnalysis[]
}

export interface IssueDetailStats {
  link_count?: number
  strong_count?: number
  weak_count?: number
  review_count?: number
  confirmed_count?: number
  pending_count?: number
  rejected_count?: number
  [key: string]: number | undefined
}

export interface IssueDetail {
  issue: Issue
  links: IssueCommitLink[]
  signals?: Record<string, number | boolean>
  stats?: IssueDetailStats
}

// ---------------- 设置 ----------------
export interface LlmConfig {
  base_url: string
  api_key: string
  model: string
  max_diff_chars: number
  commit_web_base_url: string
  llm_enabled: boolean
  updated_at?: string
}

export interface LlmConfigUpdate {
  base_url?: string
  api_key?: string
  model?: string
  max_diff_chars?: number
  commit_web_base_url?: string
  llm_enabled?: boolean
}

export interface LlmTestResult {
  ok: boolean
  message: string
}

export interface DatabaseStatus {
  dialect: string
  connected: boolean
  tables: string[]
}

export interface HealthStatus {
  status: string
  version: string
}

export interface ImportResult {
  imported: number
  updated: number
}

export interface RelinkResult {
  linked: number
  pending: number
}

export interface ConfirmResult {
  file_count: number
}

// ---------------- 展示用常量 ----------------
export const REPO_TYPE_LABELS: Record<RepoType, string> = {
  frontend: '前端',
  backend: '后端',
  app: 'App',
  miniprogram: '小程序',
  other: '其他',
}

export const SIGNAL_LABELS: Record<string, string> = {
  explicit_ref: '显式引用',
  file_hit: '文件命中',
  test_change: '测试改动',
  fix_declaration: '修复声明',
}

export const ASSESSMENT_LABELS: Record<Assessment, string> = {
  strong: '证据充分',
  weak: '证据较弱',
  review: '需人工复核',
}

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: '待复核',
  confirmed: '已确认',
  rejected: '已否决',
}
