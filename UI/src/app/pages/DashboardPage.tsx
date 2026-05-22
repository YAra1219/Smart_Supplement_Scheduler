import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { ChevronRight, AlertCircle, AlertTriangle, Pill } from "lucide-react";
import MeshGradientBackground from "../components/MeshGradientBackground";
import GlassCard from "../components/GlassCard";

interface Supplement {
  id: number;
  time: string;
  name: string;
  action: string;
  type: "normal" | "warning" | "danger";
  icon: string;
  iconGradient: string;
  reasoning: string;
  source: string;
  bestTime: string;
}

interface PlanResult {
  status: string;
  rejection_reason?: string | null;
  schedule?: Array<{
    time: string;
    action: string;
    reasoning: string;
  }>;
  warnings?: string[];
  safety_score?: number | null;
  data_sources?: string[];
  drug_interactions?: string[];
  has_high_risk_interaction?: boolean;
}

function pickIcon(name: string): { icon: string; gradient: string } {
  const n = name.toLowerCase();
  if (n.includes("维生素d") || n.includes("vd") || n.includes("d3"))
    return { icon: "☀️", gradient: "from-yellow-400 to-orange-400" };
  if (n.includes("鱼油") || n.includes("omega") || n.includes("dha") || n.includes("epa"))
    return { icon: "🐟", gradient: "from-blue-400 to-cyan-400" };
  if (n.includes("维生素b") || n.includes("b族") || n.includes("b1") || n.includes("b6") || n.includes("b12"))
    return { icon: "⚡", gradient: "from-green-400 to-emerald-400" };
  if (n.includes("铁") || n.includes("iron"))
    return { icon: "🩸", gradient: "from-red-400 to-rose-400" };
  if (n.includes("镁") || n.includes("magnesium"))
    return { icon: "🌿", gradient: "from-teal-400 to-green-400" };
  if (n.includes("褪黑素") || n.includes("melatonin"))
    return { icon: "🌙", gradient: "from-purple-400 to-indigo-400" };
  if (n.includes("钙") || n.includes("calcium"))
    return { icon: "🦴", gradient: "from-blue-300 to-indigo-300" };
  if (n.includes("维生素c") || n.includes("vc") || n.includes("维c") || n.includes("vitamin c"))
    return { icon: "🍊", gradient: "from-orange-300 to-red-300" };
  if (n.includes("益生菌") || n.includes("probiotic"))
    return { icon: "🦠", gradient: "from-green-300 to-teal-300" };
  if (n.includes("锌") || n.includes("zinc"))
    return { icon: "🔩", gradient: "from-gray-300 to-zinc-400" };
  if (n.includes("辅酶") || n.includes("q10") || n.includes("coq"))
    return { icon: "❤️", gradient: "from-red-300 to-pink-400" };
  if (n.includes("叶黄素") || n.includes("lutein"))
    return { icon: "👁️", gradient: "from-orange-200 to-yellow-300" };
  return { icon: "💊", gradient: "from-gray-400 to-slate-400" };
}

function mapResultToSupplements(plan: PlanResult): Supplement[] {
  if (!plan.schedule || plan.schedule.length === 0) return [];

  return plan.schedule.map((entry, index) => {
    const { icon, gradient } = pickIcon(entry.action);
    const lowerReasoning = (entry.reasoning || "").toLowerCase();
    const lowerAction = (entry.action || "").toLowerCase();
    const warnings = plan.warnings || [];

    let type: "normal" | "warning" | "danger" = "normal";

    if (
      warnings.some(
        (w) =>
          w.toLowerCase().includes("黑盒") ||
          w.toLowerCase().includes("召回") ||
          w.toLowerCase().includes("处方")
      )
    ) {
      type = "danger";
    } else if (
      lowerReasoning.includes("竞争") ||
      lowerReasoning.includes("间隔") ||
      lowerReasoning.includes("避免") ||
      lowerReasoning.includes("注意") ||
      lowerReasoning.includes("干扰")
    ) {
      type = "warning";
    }

    if (
      lowerAction.includes("处方") ||
      lowerReasoning.includes("处方") ||
      lowerReasoning.includes("遵医嘱")
    ) {
      type = "danger";
    }

    return {
      id: index + 1,
      time: entry.time,
      name: entry.action,
      action: entry.reasoning.length > 20 ? entry.reasoning.slice(0, 20) + "…" : entry.reasoning,
      type,
      icon,
      iconGradient: gradient,
      reasoning: entry.reasoning,
      source: (plan.data_sources && plan.data_sources[0]) || "AI 智能分析",
      bestTime: `${entry.time} 为推荐服用时间。${entry.reasoning}`,
    };
  });
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [selectedSupplement, setSelectedSupplement] = useState<Supplement | null>(null);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [supplements, setSupplements] = useState<Supplement[]>([]);

  useEffect(() => {
    const raw = localStorage.getItem("planResult");
    if (!raw) {
      navigate("/");
      return;
    }
    try {
      const parsed: PlanResult = JSON.parse(raw);
      setPlan(parsed);
      setSupplements(mapResultToSupplements(parsed));
    } catch {
      navigate("/");
    }
  }, [navigate]);

  if (!plan) {
    return (
      <div className="min-h-screen bg-[#F2F2F7] flex items-center justify-center">
        <div className="text-gray-500">加载中…</div>
      </div>
    );
  }

  if (plan.status === "error") {
    return (
      <div className="min-h-screen bg-[#F2F2F7] relative overflow-hidden">
        <MeshGradientBackground />
        <div className="w-full max-w-[383px] min-h-[852px] mx-auto px-6 py-12 relative z-10 flex flex-col items-center justify-center">
          <div className="w-full backdrop-blur-xl bg-white/60 border border-red-200 rounded-[28px] p-8 text-center shadow-xl">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-red-100 flex items-center justify-center">
              <AlertCircle className="w-10 h-10 text-red-500" />
            </div>
            <h1 className="text-2xl text-gray-900 mb-3">分析失败</h1>
            <p className="text-gray-600 mb-2">{plan.rejection_reason || "后端处理出错"}</p>
            {plan.warnings && plan.warnings.length > 0 && (
              <div className="text-left space-y-2 mb-6">
                {plan.warnings.map((w, i) => (
                  <div key={i} className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">
                    {w}
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={() => navigate("/scan")}
              className="w-full py-4 rounded-[24px] bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white shadow-lg hover:shadow-xl transition-all"
            >
              重新上传
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (plan.status === "rejected_due_to_safety") {
    return (
      <div className="min-h-screen bg-[#F2F2F7] relative overflow-hidden">
        <MeshGradientBackground />
        <div className="w-full max-w-[383px] min-h-[852px] mx-auto px-6 py-12 relative z-10 flex flex-col items-center justify-center">
          <div className="w-full backdrop-blur-xl bg-white/60 border border-red-200 rounded-[28px] p-8 text-center shadow-xl">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-red-100 flex items-center justify-center">
              <AlertCircle className="w-10 h-10 text-red-500" />
            </div>
            <h1 className="text-2xl text-gray-900 mb-3">安全警告</h1>
            <p className="text-gray-600 mb-2">{plan.rejection_reason || "检测到潜在风险成分"}</p>
            {plan.safety_score !== undefined && plan.safety_score !== null && (
              <p className="text-sm text-gray-500 mb-6">安全评分: {plan.safety_score}/100</p>
            )}
            {plan.warnings && plan.warnings.length > 0 && (
              <div className="text-left space-y-2 mb-6">
                {plan.warnings.map((w, i) => (
                  <div key={i} className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">
                    {w}
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={() => navigate("/scan")}
              className="w-full py-4 rounded-[24px] bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white shadow-lg hover:shadow-xl transition-all"
            >
              重新上传
            </button>
          </div>
        </div>
      </div>
    );
  }

  const warningCount = supplements.filter((s) => s.type === "warning").length;
  const dangerCount = supplements.filter((s) => s.type === "danger").length;
  const currentTime = new Date().getHours().toString().padStart(2, "0") + ":" + new Date().getMinutes().toString().padStart(2, "0");

  return (
    <div className="min-h-screen bg-[#F2F2F7] relative overflow-hidden">
      <MeshGradientBackground />

      <div className="w-full max-w-[383px] min-h-[852px] mx-auto px-6 py-8 relative z-10">
        <div className="mb-6">
          <h1 className="text-4xl mb-2 text-gray-900 tracking-tight">今日排期</h1>
          <p className="text-lg text-gray-500">基于您的作息智能优化</p>
          {plan.safety_score !== undefined && plan.safety_score !== null && (
            <p className="text-sm text-gray-400 mt-1">安全评分: {plan.safety_score}/100</p>
          )}
        </div>

        {plan.drug_interactions && plan.drug_interactions.length > 0 && (
          <div className="mb-6 space-y-3">
            <GlassCard className={`p-4 ${plan.has_high_risk_interaction ? "ring-2 ring-red-500/50 shadow-[0_0_24px_rgba(239,68,68,0.2)]" : "ring-2 ring-amber-500/50 shadow-[0_0_24px_rgba(245,158,11,0.2)]"}`}>
              <div className="flex items-start gap-3">
                <div className={`w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 ${plan.has_high_risk_interaction ? "bg-gradient-to-br from-red-500 to-rose-500" : "bg-gradient-to-br from-amber-400 to-orange-400"}`}>
                  <AlertTriangle className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1">
                  <h3 className="text-gray-900 mb-1">
                    {plan.has_high_risk_interaction ? "药物-补剂相互作用（高风险）" : "药物-补剂相互作用"}
                  </h3>
                  <div className="space-y-2 mt-2">
                    {plan.drug_interactions.map((interaction, i) => (
                      <p key={i} className={`text-sm ${interaction.startsWith("【严重】") ? "text-red-700 bg-red-50" : interaction.startsWith("【注意】") ? "text-amber-700 bg-amber-50" : "text-gray-600 bg-gray-50"} rounded-xl px-3 py-2`}>
                        {interaction}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            </GlassCard>
          </div>
        )}

        {(warningCount > 0 || dangerCount > 0) && (
          <div className="mb-6 space-y-3">
            {dangerCount > 0 && (
              <GlassCard className="p-4 ring-2 ring-red-500/50 shadow-[0_0_24px_rgba(239,68,68,0.2)]">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-red-500 to-rose-500 flex items-center justify-center flex-shrink-0">
                    <AlertCircle className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-gray-900 mb-1">处方药安全提醒</h3>
                    <p className="text-sm text-gray-600">
                      发现 {dangerCount} 项需医生确认的用药问题
                    </p>
                  </div>
                </div>
              </GlassCard>
            )}
            {warningCount > 0 && (
              <GlassCard className="p-4 ring-2 ring-amber-500/50 shadow-[0_0_24px_rgba(245,158,11,0.2)]">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-400 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-gray-900 mb-1">成分相互作用</h3>
                    <p className="text-sm text-gray-600">
                      发现 {warningCount} 项补剂可能存在吸收竞争
                    </p>
                  </div>
                </div>
              </GlassCard>
            )}
          </div>
        )}

        {plan.warnings && plan.warnings.length > 0 && (
          <div className="mb-6 space-y-2">
            {plan.warnings.map((w, i) => (
              <GlassCard key={i} className="p-3 bg-amber-50/40">
                <p className="text-sm text-amber-800">{w}</p>
              </GlassCard>
            ))}
          </div>
        )}

        <div className="relative pb-20">
          <div className="absolute left-[31px] top-0 bottom-0 w-[2px] bg-gradient-to-b from-gray-200 via-gray-300 to-gray-200" style={{ backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 8px, rgba(156, 163, 175, 0.3) 8px, rgba(156, 163, 175, 0.3) 16px)" }} />

          <div className="space-y-5">
            {supplements.map((supplement) => {
              const isCurrent = supplement.time === currentTime;

              return (
                <div key={supplement.id} className="relative flex gap-4 items-start">
                  <div className="relative z-10 flex-shrink-0">
                    <div
                      className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${supplement.iconGradient} flex items-center justify-center shadow-lg ${
                        isCurrent ? "ring-4 ring-blue-500/50 shadow-[0_0_24px_rgba(59,130,246,0.4)]" : ""
                      }`}
                    >
                      <Pill className="w-7 h-7 text-white" />
                    </div>
                    {isCurrent && (
                      <div className="absolute -right-1 -top-1 w-5 h-5 rounded-full bg-blue-500 border-2 border-white animate-pulse" />
                    )}
                  </div>

                  <div className="flex-1 pt-1">
                    <GlassCard
                      onClick={() => setSelectedSupplement(supplement)}
                      className={`p-5 cursor-pointer transition-all hover:shadow-xl ${
                        supplement.type === "danger"
                          ? "ring-1 ring-red-500/30"
                          : supplement.type === "warning"
                          ? "ring-1 ring-amber-500/30"
                          : ""
                      }`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-lg font-bold text-slate-700 bg-white border border-slate-200 rounded-xl px-3 py-1 shadow-sm">{supplement.time}</span>
                            {supplement.type !== "normal" && (
                              <span
                                className={`px-2 py-0.5 rounded-full text-xs ${
                                  supplement.type === "danger"
                                    ? "bg-red-500/20 text-red-700"
                                    : "bg-amber-500/20 text-amber-700"
                                }`}
                              >
                                {supplement.type === "danger" ? "处方" : "注意"}
                              </span>
                            )}
                          </div>
                          <h3 className="text-lg text-gray-900 mb-1">
                            {supplement.name}
                          </h3>
                          <p className="text-sm text-gray-600">
                            {supplement.action}
                          </p>
                        </div>
                        <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0 mt-1" />
                      </div>
                    </GlassCard>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {supplements.length === 0 && (
          <div className="text-center text-gray-400 py-12">
            暂无排期数据
          </div>
        )}
      </div>

      {selectedSupplement && (
        <div
          onClick={() => setSelectedSupplement(null)}
          className="fixed inset-0 bg-black/40 flex items-end z-50 animate-in fade-in duration-200 backdrop-blur-sm"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[383px] mx-auto backdrop-blur-2xl bg-white/95 rounded-t-[32px] shadow-2xl animate-in slide-in-from-bottom duration-300"
          >
            <div className="w-12 h-1.5 bg-gray-300 rounded-full mx-auto mt-3 mb-6" />

            <div className="px-6 pb-8">
              <div className="flex items-start gap-4 mb-6">
                <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${selectedSupplement.iconGradient} flex items-center justify-center shadow-lg flex-shrink-0`}>
                  <Pill className="w-7 h-7 text-white" />
                </div>
                <div className="flex-1">
                  <h2 className="text-2xl text-gray-900 mb-1">
                    {selectedSupplement.name}
                  </h2>
                  <p className="text-gray-500">
                    {selectedSupplement.time} · {selectedSupplement.action}
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <GlassCard className="p-5">
                  <h3 className="text-sm text-gray-500 mb-3">科学依据</h3>
                  <p className="text-gray-900 leading-relaxed mb-4">
                    {selectedSupplement.reasoning}
                  </p>
                  <div className="pt-4 border-t border-gray-200">
                    <p className="text-xs text-gray-400">
                      数据来源: {selectedSupplement.source}
                    </p>
                  </div>
                </GlassCard>

                <GlassCard className="p-5 bg-gradient-to-br from-blue-50/50 to-purple-50/50">
                  <h3 className="text-sm text-gray-500 mb-2">最佳吸收时间</h3>
                  <p className="text-gray-900">
                    {selectedSupplement.bestTime}
                  </p>
                </GlassCard>
              </div>

              <button
                onClick={() => setSelectedSupplement(null)}
                className="w-full mt-6 py-4 rounded-[24px] bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white shadow-lg hover:shadow-xl transition-all"
              >
                知道了
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
