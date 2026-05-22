import { useState } from "react";
import { useNavigate } from "react-router";
import { Sparkles, Pill } from "lucide-react";
import MeshGradientBackground from "../components/MeshGradientBackground";
import GlassCard from "../components/GlassCard";

export default function SetupPage() {
  const navigate = useNavigate();
  const [selectedTime, setSelectedTime] = useState<string | null>(null);
  const [schedule, setSchedule] = useState({
    wakeUp: "07:00",
    breakfast: "08:00",
    lunch: "12:30",
    dinner: "18:30",
    sleep: "23:00",
  });
  const [medications, setMedications] = useState("");

  const handleSave = () => {
    localStorage.setItem("userSchedule", JSON.stringify(schedule));
    const medsList = medications
      .split(/[，,\n]/)
      .map((m) => m.trim())
      .filter((m) => m.length > 0);
    localStorage.setItem("currentMedications", JSON.stringify(medsList));
    navigate("/scan");
  };

  const timeCards = [
    { key: "wakeUp", label: "起床", icon: "🌅", gradient: "from-orange-400 to-pink-400" },
    { key: "breakfast", label: "早餐", icon: "🍳", gradient: "from-yellow-400 to-orange-400" },
    { key: "lunch", label: "午餐", icon: "🍱", gradient: "from-green-400 to-emerald-400" },
    { key: "dinner", label: "晚餐", icon: "🍽️", gradient: "from-blue-400 to-indigo-400" },
    { key: "sleep", label: "睡觉", icon: "🌙", gradient: "from-indigo-400 to-purple-400" },
  ];

  return (
    <div className="min-h-screen bg-[#F2F2F7] flex items-center justify-center relative overflow-hidden">
      <MeshGradientBackground />

      <div className="w-full max-w-[383px] min-h-[852px] px-6 py-12 relative z-10 flex flex-col">
        <div className="text-center mb-10">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-2xl">
            <span className="text-4xl">💊</span>
          </div>
          <h1 className="text-4xl mb-3 text-gray-900 tracking-tight">欢迎使用</h1>
          <p className="text-lg text-gray-500">设置您的每日作息</p>
        </div>

        <div className="flex-1 space-y-6">
          {timeCards.map(({ key, label, icon, gradient }) => (
            <GlassCard
              key={key}
              className={`p-6 cursor-pointer transition-all duration-300 ${
                selectedTime === key ? "ring-2 ring-blue-500 shadow-[0_0_32px_rgba(59,130,246,0.3)]" : ""
              }`}
              onClick={() => setSelectedTime(key)}
            >
              <div className="flex items-center gap-4 mb-4">
                <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-lg`}>
                  <span className="text-2xl">{icon}</span>
                </div>
                <div className="flex-1">
                  <h3 className="text-xl text-gray-900 mb-1">{label}</h3>
                  <p className="text-sm text-gray-500">设置{label}时间</p>
                </div>
              </div>
              <input
                type="time"
                value={schedule[key as keyof typeof schedule]}
                onChange={(e) => setSchedule({ ...schedule, [key]: e.target.value })}
                onFocus={() => setSelectedTime(key)}
                className="w-full px-5 py-4 bg-white/60 backdrop-blur-sm border border-white/80 rounded-2xl text-2xl text-center text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              />
            </GlassCard>
          ))}

          <GlassCard className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-rose-400 to-red-400 flex items-center justify-center shadow-lg">
                <Pill className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-xl text-gray-900">当前用药</h3>
                <p className="text-sm text-gray-500">处方药 / OTC（选填）</p>
              </div>
            </div>
            <textarea
              value={medications}
              onChange={(e) => setMedications(e.target.value)}
              placeholder="例如：华法林、二甲双胍、阿司匹林&#10;多种药品用逗号或换行分隔"
              className="w-full px-4 py-3 bg-white/60 backdrop-blur-sm border border-white/80 rounded-2xl text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all resize-none h-28"
            />
            <p className="text-xs text-gray-400 mt-2">
              填写后系统将自动检测药物与补剂的相互作用风险
            </p>
          </GlassCard>
        </div>

        <button
          onClick={handleSave}
          className="w-full mt-8 py-5 rounded-[28px] bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white text-lg shadow-[0_8px_32px_rgba(0,0,0,0.12)] hover:shadow-[0_12px_48px_rgba(0,0,0,0.18)] transition-all duration-300 flex items-center justify-center gap-2"
        >
          <Sparkles className="w-5 h-5" />
          <span>保存并开始扫描</span>
        </button>

        <p className="text-center text-sm text-gray-400 mt-6">
          基于 NIH 医学数据库 · AI 智能优化
        </p>
      </div>
    </div>
  );
}
