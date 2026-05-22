import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { AlertCircle } from "lucide-react";
import MeshGradientBackground from "../components/MeshGradientBackground";
import { getTaskStatus } from "../api";

export default function ThinkingPage() {
  const navigate = useNavigate();
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const steps = [
    "识别补剂成分中...",
    "安全校验中...",
    "排期生成中...",
    "检查药物相互作用中...",
  ];

  useEffect(() => {
    const taskId = localStorage.getItem("taskId");
    if (!taskId) {
      setError("未找到任务 ID，请返回重新上传");
      return;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const data = await getTaskStatus(taskId);
        if (cancelled) return;

        let prog = 0;
        if (data.status === "PENDING") prog = 5;
        else if (data.status === "STARTED") prog = 15;
        else if (data.status === "PROGRESS") prog = data.progress ?? 50;
        else if (data.status === "SUCCESS") prog = 100;
        else if (data.status === "FAILURE") prog = 0;

        setProgress(prog);

        if (prog <= 40) setCurrentStep(0);
        else if (prog <= 70) setCurrentStep(1);
        else if (prog <= 85) setCurrentStep(2);
        else setCurrentStep(3);

        if (data.status === "SUCCESS") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          localStorage.setItem("planResult", JSON.stringify(data.result));
          localStorage.removeItem("taskId");
          setTimeout(() => navigate("/dashboard"), 800);
        } else if (data.status === "FAILURE") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setError(data.error || "任务执行失败");
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "查询任务状态失败");
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 1500);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [navigate]);

  const circumference = 2 * Math.PI * 120;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className="min-h-screen bg-[#F2F2F7] relative overflow-hidden">
      <MeshGradientBackground />

      <div className="w-full max-w-[383px] min-h-[852px] mx-auto px-6 py-12 relative z-10 flex flex-col items-center justify-center">
        {error ? (
          <div className="w-full backdrop-blur-xl bg-white/60 border border-red-200 rounded-[28px] p-8 text-center shadow-xl">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-100 flex items-center justify-center">
              <AlertCircle className="w-8 h-8 text-red-500" />
            </div>
            <h2 className="text-xl text-gray-900 mb-2">分析失败</h2>
            <p className="text-gray-600 mb-6">{error}</p>
            <button
              onClick={() => navigate("/scan")}
              className="w-full py-4 rounded-[24px] bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white shadow-lg hover:shadow-xl transition-all"
            >
              重新上传
            </button>
          </div>
        ) : (
          <>
            <div className="relative mb-16">
              <svg className="w-80 h-80 -rotate-90" viewBox="0 0 280 280">
                <defs>
                  <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#3B82F6" />
                    <stop offset="50%" stopColor="#A855F7" />
                    <stop offset="100%" stopColor="#EC4899" />
                  </linearGradient>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                    <feMerge>
                      <feMergeNode in="coloredBlur"/>
                      <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                  </filter>
                </defs>

                <circle
                  cx="140"
                  cy="140"
                  r="120"
                  fill="none"
                  stroke="rgba(255,255,255,0.3)"
                  strokeWidth="12"
                />

                <circle
                  cx="140"
                  cy="140"
                  r="120"
                  fill="none"
                  stroke="url(#progressGradient)"
                  strokeWidth="12"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={offset}
                  filter="url(#glow)"
                  className="transition-all duration-500 ease-out"
                />
              </svg>

              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-7xl mb-4 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 bg-clip-text text-transparent">
                    {Math.round(progress)}%
                  </div>
                  <div className="px-6 py-2 backdrop-blur-xl bg-white/40 rounded-full border border-white/60">
                    <p className="text-sm text-gray-700">AI 深度分析中</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="w-full space-y-4">
              {steps.map((step, index) => (
                <div
                  key={index}
                  className={`transition-all duration-500 ${
                    index <= currentStep ? "opacity-100 translate-y-0" : "opacity-30 translate-y-2"
                  }`}
                >
                  <div className="backdrop-blur-xl bg-white/40 border border-white/60 rounded-[28px] p-5 flex items-center gap-4">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        index < currentStep
                          ? "bg-green-500"
                          : index === currentStep
                          ? "bg-blue-500 animate-pulse"
                          : "bg-gray-300"
                      }`}
                    />
                    <p className={`text-base ${index <= currentStep ? "text-gray-900" : "text-gray-400"}`}>
                      {step}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <p className="text-center text-sm text-gray-400 mt-12">
              基于 NIH · RxNorm 医学数据库
            </p>
          </>
        )}
      </div>
    </div>
  );
}
