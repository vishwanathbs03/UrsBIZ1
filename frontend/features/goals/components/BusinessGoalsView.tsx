"use client";

import React, { useState, useEffect } from "react";
import {
  Target,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
  Plus,
  RefreshCw,
  History,
  Calendar,
  Layers,
  FileText,
  ArrowRight,
  X,
  Archive,
  Pause,
  Play,
  Check,
  ChevronDown,
  ChevronUp,
  Info,
  ShieldAlert,
  BarChart3,
  Lightbulb,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/common/PageHeader";
import { useLanguage } from "@/context/language-context";
import { formatINR, formatDate } from "@/lib/formatters";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import {
  goalsService,
  type BusinessGoal,
  type BusinessGoalListResponse,
  type BusinessGoalCreate,
  type BusinessGoalAudit,
  type GoalAIExplanationResponse,
  type GoalStatus,
  type GoalMeasurementMethod,
  type GoalMetricKey,
} from "@/services";

const METRIC_OPTIONS: { key: GoalMetricKey; label: string; unit: string; desc: string }[] = [
  {
    key: "monthly_revenue",
    label: "Monthly Revenue",
    unit: "INR",
    desc: "Calculated from completed transactions in the current calendar month (1st of month to today, or specified goal window)",
  },
  {
    key: "customer_concentration",
    label: "Customer Concentration (% Top Client)",
    unit: "%",
    desc: "Target reducing reliance on the single largest customer over the observation window",
  },
  {
    key: "repeat_customer_rate",
    label: "Repeat Customer Rate (%)",
    unit: "%",
    desc: "Percentage of unique customers with >=2 purchases in the observation window",
  },
  {
    key: "average_order_value",
    label: "Average Order Value (AOV)",
    unit: "INR",
    desc: "Total sales revenue divided by transaction count across the observation window",
  },
  {
    key: "new_customers_count",
    label: "New Customers Acquired",
    unit: "customers",
    desc: "Count of first-time purchasing customers acquired during the observation window",
  },
  {
    key: "sales_upload_frequency",
    label: "Sales Upload Frequency",
    unit: "uploads",
    desc: "Number of successful ledger uploads recorded during the observation window",
  },
  {
    key: "digital_twin_health_score",
    label: "Digital Twin Health Score",
    unit: "score",
    desc: "Holistic business vitality score out of 100",
  },
  {
    key: "manual",
    label: "Custom / Manual Benchmark",
    unit: "units",
    desc: "Self-reported milestone tracked with owner audit notes",
  },
];

export function BusinessGoalsView() {
  const { language } = useLanguage();
  const [data, setData] = useState<BusinessGoalListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

  // Modals
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [historyGoal, setHistoryGoal] = useState<BusinessGoal | null>(null);
  const [historyAudits, setHistoryAudits] = useState<BusinessGoalAudit[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [aiGoal, setAiGoal] = useState<BusinessGoal | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<GoalAIExplanationResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  const [manualGoal, setManualGoal] = useState<BusinessGoal | null>(null);
  const [manualProgressVal, setManualProgressVal] = useState<string>("");
  const [manualProgressNotes, setManualProgressNotes] = useState<string>("");
  const [manualSubmitting, setManualSubmitting] = useState(false);

  // Form State
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newMetricKey, setNewMetricKey] = useState<GoalMetricKey>("monthly_revenue");
  const [newMeasurementMethod, setNewMeasurementMethod] = useState<GoalMeasurementMethod>("AUTOMATED_METRIC");
  const [newBaseline, setNewBaseline] = useState<string>("");
  const [newTarget, setNewTarget] = useState<string>("");
  const [newUnit, setNewUnit] = useState<string>("INR");
  const [newStartDate, setNewStartDate] = useState<string>("");
  const [newTargetDate, setNewTargetDate] = useState<string>("");
  const [newPriority, setNewPriority] = useState<string>("medium");
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Expanded cards for related items
  const [expandedGoalId, setExpandedGoalId] = useState<number | null>(null);

  useEffect(() => {
    fetchGoals();
  }, [statusFilter, includeArchived]);

  const fetchGoals = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {
        status: statusFilter === "ALL" ? undefined : statusFilter,
        include_archived: includeArchived,
      };
      const res = await goalsService.listGoals(params);
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load business goals");
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async (goalId: number) => {
    try {
      await goalsService.evaluateGoal(goalId);
      await fetchGoals();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to re-evaluate goal");
    }
  };

  const handleStatusChange = async (goalId: number, status: GoalStatus) => {
    try {
      await goalsService.updateStatus(goalId, { status });
      await fetchGoals();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Status transition rejected");
    }
  };

  const handleArchive = async (goalId: number) => {
    if (!confirm("Are you sure you want to archive this goal? Historical audits will be preserved.")) return;
    try {
      await goalsService.archiveGoal(goalId);
      await fetchGoals();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to archive goal");
    }
  };

  const openHistory = async (goal: BusinessGoal) => {
    setHistoryGoal(goal);
    setHistoryLoading(true);
    try {
      const audits = await goalsService.getGoalHistory(goal.id);
      setHistoryAudits(audits);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setHistoryLoading(false);
    }
  };

  const openAiExplain = async (goal: BusinessGoal) => {
    setAiGoal(goal);
    setAiLoading(true);
    setAiAnalysis(null);
    try {
      const analysis = await goalsService.explainGoal(goal.id, "en");
      setAiAnalysis(analysis);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to generate AI explanation");
    } finally {
      setAiLoading(false);
    }
  };

  const openManualProgress = (goal: BusinessGoal) => {
    setManualGoal(goal);
    setManualProgressVal(goal.current_value !== null && goal.current_value !== undefined ? String(goal.current_value) : "");
    setManualProgressNotes("");
  };

  const handleManualProgressSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualGoal) return;
    const val = parseFloat(manualProgressVal);
    if (isNaN(val)) {
      alert("Please enter a valid numeric value.");
      return;
    }
    setManualSubmitting(true);
    try {
      await goalsService.recordProgress(manualGoal.id, {
        current_value: val,
        notes: manualProgressNotes.trim() || undefined,
      });
      setManualGoal(null);
      await fetchGoals();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to record manual progress");
    } finally {
      setManualSubmitting(false);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    if (!newTitle.trim()) {
      setCreateError("Goal title is required.");
      return;
    }
    const targetVal = parseFloat(newTarget);
    if (isNaN(targetVal)) {
      setCreateError("Target value must be a valid number.");
      return;
    }
    const baselineVal = newBaseline ? parseFloat(newBaseline) : undefined;
    if (newBaseline && isNaN(baselineVal!)) {
      setCreateError("Baseline value must be a valid number.");
      return;
    }

    setCreateSubmitting(true);
    try {
      const payload: BusinessGoalCreate = {
        title: newTitle.trim(),
        description: newDescription.trim() || undefined,
        metric_key: newMetricKey,
        measurement_method: newMeasurementMethod,
        baseline_value: baselineVal,
        target_value: targetVal,
        unit: newUnit.trim() || "INR",
        start_date: newStartDate || undefined,
        target_date: newTargetDate || undefined,
        priority: newPriority,
      };

      await goalsService.createGoal(payload);
      setIsCreateOpen(false);
      // Reset form
      setNewTitle("");
      setNewDescription("");
      setNewBaseline("");
      setNewTarget("");
      setNewStartDate("");
      setNewTargetDate("");
      await fetchGoals();
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Failed to create business goal");
    } finally {
      setCreateSubmitting(false);
    }
  };

  const handleMetricSelect = (metricKey: GoalMetricKey) => {
    setNewMetricKey(metricKey);
    const opt = METRIC_OPTIONS.find((m) => m.key === metricKey);
    if (opt) {
      setNewUnit(opt.unit);
      if (metricKey === "manual") {
        setNewMeasurementMethod("MANUAL_REPORTED");
      } else {
        setNewMeasurementMethod("AUTOMATED_METRIC");
      }
    }
  };

  const formatValue = (val: number | null | undefined, unit: string) => {
    if (val === null || val === undefined) return "—";
    if (unit.toUpperCase() === "INR" || unit === "₹") {
      return formatINR(val, { language });
    }
    if (unit === "%") {
      return `${val.toFixed(1)}%`;
    }
    return `${val.toLocaleString()} ${unit}`;
  };

  const getPriorityColor = (priority: string) => {
    switch (priority.toLowerCase()) {
      case "critical":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      case "high":
        return "bg-orange-500/10 text-orange-400 border-orange-500/20";
      case "medium":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      default:
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
    }
  };

  const getStatusColor = (status: GoalStatus) => {
    switch (status) {
      case "ACTIVE":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "COMPLETED":
        return "bg-primary/10 text-primary border-primary/20";
      case "PAUSED":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "INCOMPLETE":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      case "EXPIRED":
        return "bg-slate-500/10 text-slate-400 border-slate-500/20";
      case "ARCHIVED":
        return "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";
      default:
        return "bg-secondary text-secondary-foreground";
    }
  };

  const getMethodBadge = (method: GoalMeasurementMethod) => {
    switch (method) {
      case "AUTOMATED_METRIC":
        return (
          <Badge variant="outline" className="border-sky-500/30 text-sky-400 bg-sky-500/10 text-xs">
            ⚡ Automated Metric
          </Badge>
        );
      case "MANUAL_REPORTED":
        return (
          <Badge variant="outline" className="border-amber-500/30 text-amber-400 bg-amber-500/10 text-xs">
            ✍️ Owner Self-Reported
          </Badge>
        );
      case "ESTIMATE":
        return (
          <Badge variant="outline" className="border-purple-500/30 text-purple-400 bg-purple-500/10 text-xs">
            📊 Model Estimate
          </Badge>
        );
    }
  };

  const filteredGoals = (data?.items || []).filter((g) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      g.title.toLowerCase().includes(q) ||
      (g.description && g.description.toLowerCase().includes(q)) ||
      (g.metric_key && g.metric_key.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-8 pb-16">
      {/* Header Banner */}
      <PageHeader
        title="Business Goals & Progress Tracker"
        description="Establish measurable targets connected to authoritative business metrics, verified ledger transactions, and immutable audit trails."
        actions={
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" onClick={fetchGoals} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Button size="sm" onClick={() => setIsCreateOpen(true)} className="bg-primary text-primary-foreground">
              <Plus className="h-4 w-4 mr-2" />
              New Goal
            </Button>
          </div>
        }
      />

      {/* Summary KPI Cards */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm">
            <div className="flex items-center justify-between text-muted-foreground mb-1 text-xs">
              <span>Total Goals</span>
              <Target className="h-4 w-4 text-primary" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-foreground">{data.total}</div>
            <div className="text-[11px] text-muted-foreground mt-1">Configured for business</div>
          </div>

          <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 backdrop-blur-sm">
            <div className="flex items-center justify-between text-emerald-400 mb-1 text-xs font-medium">
              <span>Active</span>
              <Play className="h-4 w-4" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-emerald-400">{data.active_count}</div>
            <div className="text-[11px] text-emerald-400/80 mt-1">Currently being tracked</div>
          </div>

          <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 backdrop-blur-sm">
            <div className="flex items-center justify-between text-primary mb-1 text-xs font-medium">
              <span>Completed</span>
              <CheckCircle2 className="h-4 w-4" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-primary">{data.completed_count}</div>
            <div className="text-[11px] text-primary/80 mt-1">Achieved targets</div>
          </div>

          <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/5 backdrop-blur-sm">
            <div className="flex items-center justify-between text-rose-400 mb-1 text-xs font-medium">
              <span>At Risk / Behind</span>
              <TrendingUp className="h-4 w-4" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-rose-400">{data.at_risk_count}</div>
            <div className="text-[11px] text-rose-400/80 mt-1">Progress &lt; 50%</div>
          </div>

          <div className="p-4 rounded-xl border border-amber-500/20 bg-amber-500/5 backdrop-blur-sm">
            <div className="flex items-center justify-between text-amber-400 mb-1 text-xs font-medium">
              <span>Data Disclaimers</span>
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-amber-400">{data.stale_or_missing_data_count}</div>
            <div className="text-[11px] text-amber-400/80 mt-1">Missing or &gt;30d stale</div>
          </div>
        </div>
      )}

      {/* Filter and Controls Toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl border border-border/60 bg-card/40">
        <div className="flex flex-wrap items-center gap-2">
          {["ALL", "ACTIVE", "PAUSED", "COMPLETED", "INCOMPLETE"].map((st) => (
            <Button
              key={st}
              variant={statusFilter === st ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter(st)}
              className="text-xs h-8"
            >
              {st}
            </Button>
          ))}
          <label className="flex items-center gap-2 text-xs text-muted-foreground ml-3 cursor-pointer">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
              className="rounded border-border text-primary focus:ring-primary"
            />
            Include Archived
          </label>
        </div>

        <div className="w-full sm:w-64">
          <Input
            placeholder="Search goals..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 text-xs bg-background/50"
          />
        </div>
      </div>

      {/* Main Content Area */}
      {loading && !data ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorState description={error} onAction={fetchGoals} />
      ) : filteredGoals.length === 0 ? (
        <EmptyState
          title="No business goals found"
          description="Define measurable strategic goals to automatically track revenue milestones, customer retention, or operational health."
          actionLabel="Create First Goal"
          onAction={() => setIsCreateOpen(true)}
        />
      ) : (
        <div className="space-y-4">
          {filteredGoals.map((goal) => {
            const isAchieved = goal.is_achieved;
            const progress = Math.min(100, Math.max(0, goal.progress_pct ?? 0));
            const isExpanded = expandedGoalId === goal.id;

            return (
              <div
                key={goal.id}
                className="p-5 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm hover:border-border transition-all duration-200 space-y-4"
              >
                {/* Goal Card Top Row */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-semibold text-foreground tracking-tight">{goal.title}</span>
                      <Badge variant="outline" className={`text-[11px] ${getStatusColor(goal.status)}`}>
                        {goal.status}
                      </Badge>
                      <Badge variant="outline" className={`text-[11px] ${getPriorityColor(goal.priority)}`}>
                        {goal.priority.toUpperCase()}
                      </Badge>
                      {getMethodBadge(goal.measurement_method)}
                      {isAchieved && (
                        <Badge className="bg-emerald-500 text-white text-[11px] flex items-center gap-1">
                          <Check className="h-3 w-3" /> Target Achieved
                        </Badge>
                      )}
                    </div>

                    {goal.description && (
                      <p className="text-xs text-muted-foreground leading-relaxed max-w-3xl">{goal.description}</p>
                    )}
                  </div>

                  {/* Actions Bar */}
                  <div className="flex items-center gap-2 self-end sm:self-auto flex-wrap">
                    {goal.measurement_method === "AUTOMATED_METRIC" && goal.status === "ACTIVE" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEvaluate(goal.id)}
                        className="h-7 text-xs border-sky-500/30 text-sky-400 hover:bg-sky-500/10"
                        title="Re-calculate against live verified transactions"
                      >
                        <RefreshCw className="h-3.5 w-3.5 mr-1" /> Re-evaluate
                      </Button>
                    )}

                    {goal.measurement_method === "MANUAL_REPORTED" && goal.status === "ACTIVE" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openManualProgress(goal)}
                        className="h-7 text-xs border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
                      >
                        Update Progress
                      </Button>
                    )}

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openAiExplain(goal)}
                      className="h-7 text-xs border-primary/30 text-primary hover:bg-primary/10"
                    >
                      <Sparkles className="h-3.5 w-3.5 mr-1" /> AI Insights
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openHistory(goal)}
                      className="h-7 text-xs text-muted-foreground hover:text-foreground"
                    >
                      <History className="h-3.5 w-3.5 mr-1" /> Audit
                    </Button>

                    {/* Status Actions */}
                    {goal.status === "ACTIVE" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleStatusChange(goal.id, "PAUSED")}
                        className="h-7 text-xs text-amber-400 hover:text-amber-300"
                        title="Pause tracking"
                      >
                        <Pause className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {goal.status === "PAUSED" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleStatusChange(goal.id, "ACTIVE")}
                        className="h-7 text-xs text-emerald-400 hover:text-emerald-300"
                        title="Resume tracking"
                      >
                        <Play className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {goal.status === "ACTIVE" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleStatusChange(goal.id, "COMPLETED")}
                        className="h-7 text-xs text-primary hover:text-primary/80"
                        title="Mark Completed"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                    )}

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleArchive(goal.id)}
                      className="h-7 text-xs text-muted-foreground hover:text-rose-400"
                      title="Archive Goal"
                    >
                      <Archive className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                {/* Progress Metric & Bar Display */}
                <div className="p-4 rounded-lg bg-background/50 border border-border/40 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-4">
                      {goal.baseline_value !== null && goal.baseline_value !== undefined && (
                        <div>
                          <span className="text-muted-foreground">Baseline: </span>
                          <span className="font-semibold text-foreground">
                            {formatValue(goal.baseline_value, goal.unit)}
                          </span>
                        </div>
                      )}
                      <div>
                        <span className="text-muted-foreground">Current: </span>
                        <span className="font-bold text-foreground text-sm">
                          {formatValue(goal.current_value, goal.unit)}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Target: </span>
                        <span className="font-semibold text-primary">
                          {formatValue(goal.target_value, goal.unit)}
                        </span>
                      </div>
                      {goal.remaining_gap !== null && goal.remaining_gap !== undefined && (
                        <div className="text-muted-foreground">
                          Gap: <span className="text-foreground">{formatValue(goal.remaining_gap, goal.unit)}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      {goal.target_date && (
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <Calendar className="h-3.5 w-3.5" />
                          <span>Deadline: {goal.target_date}</span>
                          {goal.days_remaining !== null && goal.days_remaining !== undefined && (
                            <span className={goal.days_remaining < 7 ? "text-rose-400 font-medium" : "text-muted-foreground"}>
                              ({goal.days_remaining}d left)
                            </span>
                          )}
                        </div>
                      )}
                      <div className="font-bold text-sm text-foreground">{progress.toFixed(1)}%</div>
                    </div>
                  </div>

                  {/* Quantitative Progress Bar */}
                  <div className="w-full bg-secondary/50 rounded-full h-2.5 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 rounded-full ${
                        progress >= 100
                          ? "bg-emerald-500"
                          : progress >= 75
                          ? "bg-primary"
                          : progress >= 40
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      }`}
                      style={{ width: `${progress}%` }}
                    />
                  </div>

                  {/* Honest Data Availability Alert & Provenance */}
                  {goal.data_availability === "MISSING_DATA" && (
                    <div className="flex items-start gap-2 p-2.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs">
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold">Source Data Missing: </span>
                        {goal.data_freshness_warning ||
                          "No transactions found for the evaluation window. Upload sales CSV to activate automated tracking."}
                      </div>
                    </div>
                  )}

                  {goal.data_availability === "STALE_DATA" && (
                    <div className="flex items-start gap-2 p-2.5 rounded bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-xs">
                      <Clock className="h-4 w-4 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold">Stale Observation Window: </span>
                        {goal.data_freshness_warning}
                      </div>
                    </div>
                  )}

                  {goal.data_availability === "PENDING_PERIOD" && (
                    <div className="flex items-start gap-2 p-2.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs">
                      <Info className="h-4 w-4 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold">Observation Period Pending: </span>
                        Observation window begins on {goal.start_date}. Progress will calculate once data period opens.
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                    <div className="flex items-center gap-1.5">
                      <Layers className="h-3 w-3" />
                      <span>Evidence Source: {goal.evidence_source}</span>
                    </div>
                    {goal.last_evaluated_at && (
                      <div>Last Evaluated: {formatDate(goal.last_evaluated_at, { format: "datetime", language })}</div>
                    )}
                  </div>
                </div>

                {/* Related Items (Recommendations, Decisions) Accordion Toggle */}
                {(goal.related_recommendations.length > 0 || goal.related_decisions.length > 0) && (
                  <div>
                    <button
                      onClick={() => setExpandedGoalId(isExpanded ? null : goal.id)}
                      className="flex items-center gap-1.5 text-xs text-primary font-medium hover:underline cursor-pointer"
                    >
                      {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                      <span>
                        Related Actions ({goal.related_recommendations.length} Recommendations,{" "}
                        {goal.related_decisions.length} Decisions)
                      </span>
                    </button>

                    {isExpanded && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 pt-3 border-t border-border/40">
                        {goal.related_recommendations.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                              Action Board Recommendations
                            </span>
                            <div className="space-y-1">
                              {goal.related_recommendations.map((r) => (
                                <div
                                  key={r.id}
                                  className="p-2 rounded bg-background/40 border border-border/30 text-xs flex items-center justify-between"
                                >
                                  <span className="font-medium text-foreground">{r.title}</span>
                                  <Badge variant="outline" className="text-[10px]">
                                    {r.status}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {goal.related_decisions.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                              Decision Workbench Items
                            </span>
                            <div className="space-y-1">
                              {goal.related_decisions.map((d) => (
                                <div
                                  key={d.id}
                                  className="p-2 rounded bg-background/40 border border-border/30 text-xs flex items-center justify-between"
                                >
                                  <span className="font-medium text-foreground">{d.title}</span>
                                  <Badge variant="outline" className="text-[10px]">
                                    {d.status}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* CREATE GOAL MODAL */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-card border border-border rounded-xl max-w-xl w-full p-6 shadow-2xl space-y-5 my-8">
            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-bold text-foreground">Create Measurable Business Goal</h2>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setIsCreateOpen(false)} className="h-8 w-8 p-0">
                <X className="h-4 w-4" />
              </Button>
            </div>

            {createError && (
              <div className="p-3 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-muted-foreground">Goal Title *</label>
                <Input
                  placeholder="e.g. Achieve ₹15L monthly sales"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="mt-1 text-xs"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-muted-foreground">Strategic Context / Objective</label>
                <Input
                  placeholder="e.g. Expand product lines and strengthen marketing across tier-2 cities"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="mt-1 text-xs"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-muted-foreground">Measurement Metric</label>
                <select
                  value={newMetricKey}
                  onChange={(e) => handleMetricSelect(e.target.value as GoalMetricKey)}
                  className="w-full mt-1 p-2 rounded-md bg-background border border-border text-foreground text-xs focus:ring-1 focus:ring-primary"
                >
                  {METRIC_OPTIONS.map((opt) => (
                    <option key={opt.key} value={opt.key}>
                      {opt.label} ({opt.desc})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Measurement Method</label>
                  <select
                    value={newMeasurementMethod}
                    onChange={(e) => setNewMeasurementMethod(e.target.value as GoalMeasurementMethod)}
                    className="w-full mt-1 p-2 rounded-md bg-background border border-border text-foreground text-xs"
                  >
                    <option value="AUTOMATED_METRIC">⚡ Automated Metric (Deterministic Ledger)</option>
                    <option value="MANUAL_REPORTED">✍️ Owner Self-Reported</option>
                    <option value="ESTIMATE">📊 Statistical Model Estimate</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Priority</label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value)}
                    className="w-full mt-1 p-2 rounded-md bg-background border border-border text-foreground text-xs"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Baseline (Starting)</label>
                  <Input
                    type="number"
                    step="any"
                    placeholder="e.g. 1000000"
                    value={newBaseline}
                    onChange={(e) => setNewBaseline(e.target.value)}
                    className="mt-1 text-xs"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Target Value *</label>
                  <Input
                    type="number"
                    step="any"
                    placeholder="e.g. 1500000"
                    value={newTarget}
                    onChange={(e) => setNewTarget(e.target.value)}
                    className="mt-1 text-xs"
                    required
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Unit</label>
                  <Input
                    placeholder="e.g. INR, %, count"
                    value={newUnit}
                    onChange={(e) => setNewUnit(e.target.value)}
                    className="mt-1 text-xs"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Observation Start Date</label>
                  <Input
                    type="date"
                    value={newStartDate}
                    onChange={(e) => setNewStartDate(e.target.value)}
                    className="mt-1 text-xs"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Target Deadline</label>
                  <Input
                    type="date"
                    value={newTargetDate}
                    onChange={(e) => setNewTargetDate(e.target.value)}
                    className="mt-1 text-xs"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-border/60">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsCreateOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={createSubmitting} className="bg-primary text-primary-foreground">
                  {createSubmitting ? "Creating..." : "Create Goal"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MANUAL PROGRESS MODAL */}
      {manualGoal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <div>
                <h3 className="text-sm font-bold text-foreground">Record Self-Reported Progress</h3>
                <p className="text-xs text-muted-foreground mt-0.5">{manualGoal.title}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setManualGoal(null)} className="h-8 w-8 p-0">
                <X className="h-4 w-4" />
              </Button>
            </div>

            <form onSubmit={handleManualProgressSubmit} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-muted-foreground">
                  Measured Value ({manualGoal.unit}) *
                </label>
                <Input
                  type="number"
                  step="any"
                  value={manualProgressVal}
                  onChange={(e) => setManualProgressVal(e.target.value)}
                  className="mt-1 text-xs"
                  placeholder={`Target is ${formatValue(manualGoal.target_value, manualGoal.unit)}`}
                  required
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-muted-foreground">Audit Notes / Verification</label>
                <Input
                  value={manualProgressNotes}
                  onChange={(e) => setManualProgressNotes(e.target.value)}
                  className="mt-1 text-xs"
                  placeholder="e.g. Reconciled with accountant tally sheet"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setManualGoal(null)}>
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={manualSubmitting}>
                  {manualSubmitting ? "Saving..." : "Save Progress"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AUDIT HISTORY MODAL */}
      {historyGoal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-card border border-border rounded-xl max-w-2xl w-full p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <History className="h-4 w-4 text-primary" />
                  <h3 className="text-base font-bold text-foreground">Immutable Audit History</h3>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{historyGoal.title}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setHistoryGoal(null)} className="h-8 w-8 p-0">
                <X className="h-4 w-4" />
              </Button>
            </div>

            {historyLoading ? (
              <LoadingSkeleton />
            ) : historyAudits.length === 0 ? (
              <div className="text-center py-8 text-xs text-muted-foreground">No historical audit entries found.</div>
            ) : (
              <div className="max-h-96 overflow-y-auto space-y-2 pr-1">
                {historyAudits.map((a) => (
                  <div key={a.id} className="p-3 rounded-lg bg-background/50 border border-border/40 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-primary">{a.action}</span>
                      <span className="text-[11px] text-muted-foreground">
                        {formatDate(a.created_at, { format: "datetime", language })}
                      </span>
                    </div>

                    {a.old_status && a.new_status && (
                      <div className="text-muted-foreground">
                        Status Transition: <span className="text-foreground">{a.old_status}</span> &rarr;{" "}
                        <span className="font-semibold text-foreground">{a.new_status}</span>
                      </div>
                    )}

                    {a.measured_value !== null && a.measured_value !== undefined && (
                      <div className="text-muted-foreground">
                        Measured Value:{" "}
                        <span className="font-semibold text-foreground">
                          {formatValue(a.measured_value, historyGoal.unit)}
                        </span>{" "}
                        ({a.progress_pct !== null && a.progress_pct !== undefined ? `${a.progress_pct.toFixed(1)}%` : "0%"})
                      </div>
                    )}

                    {a.notes && <div className="text-muted-foreground italic text-[11px]">Note: "{a.notes}"</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* AI TRAJECTORY & EXPLANATION MODAL */}
      {aiGoal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-card border border-border rounded-xl max-w-xl w-full p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <h3 className="text-base font-bold text-foreground">AI Feasibility & Strategic Trajectory</h3>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setAiGoal(null)} className="h-8 w-8 p-0">
                <X className="h-4 w-4" />
              </Button>
            </div>

            {aiLoading ? (
              <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
                <Sparkles className="h-8 w-8 text-primary animate-pulse" />
                <span className="text-xs text-muted-foreground">
                  Analyzing current run-rate, historical velocity, and feasibility...
                </span>
              </div>
            ) : aiAnalysis ? (
              <div className="space-y-4 text-xs">
                <div className="flex items-center justify-between p-3 rounded-lg bg-background/50 border border-border/40">
                  <div>
                    <span className="text-muted-foreground">Trajectory: </span>
                    <Badge variant="outline" className="font-bold border-primary text-primary ml-1">
                      {aiAnalysis.trajectory}
                    </Badge>
                  </div>
                  <div className="text-muted-foreground font-medium">{aiAnalysis.feasibility_assessment}</div>
                </div>

                <div className="space-y-1.5">
                  <span className="font-semibold text-foreground text-xs">In-Depth Diagnostic</span>
                  <p className="text-muted-foreground leading-relaxed p-3 rounded-lg bg-background/40 border border-border/30">
                    {aiAnalysis.analysis}
                  </p>
                </div>

                {aiAnalysis.suggested_actions && aiAnalysis.suggested_actions.length > 0 && (
                  <div className="space-y-2">
                    <span className="font-semibold text-foreground text-xs">Recommended Action Steps</span>
                    <ul className="space-y-1.5">
                      {aiAnalysis.suggested_actions.map((act, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-2 p-2 rounded bg-background/40 border border-border/20 text-muted-foreground"
                        >
                          <ArrowRight className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
                          <span>{act}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="p-2.5 rounded bg-secondary/30 text-[11px] text-muted-foreground flex items-center gap-1.5">
                  <ShieldAlert className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span>
                    Deterministic Evidence: <strong className="text-foreground">{aiAnalysis.evidence_summary}</strong>. AI
                    analysis is non-mutating and cannot alter quantitative progress values.
                  </span>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
