import { useState } from "react";
import { useNavigate } from "react-router";
import { Camera, X, Sparkles, Loader2 } from "lucide-react";
import MeshGradientBackground from "../components/MeshGradientBackground";
import GlassCard from "../components/GlassCard";
import { submitFullProcess } from "../api";

export default function ScanPage() {
  const navigate = useNavigate();
  const [images, setImages] = useState<string[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files;
    if (!selected) return;
    const newFiles = Array.from(selected);
    const newImages = newFiles.map((file) => URL.createObjectURL(file));
    setFiles((prev) => [...prev, ...newFiles]);
    setImages((prev) => [...prev, ...newImages]);
    setError(null);
  };

  const removeImage = (index: number) => {
    URL.revokeObjectURL(images[index]);
    setImages((prev) => prev.filter((_, i) => i !== index));
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleGenerate = async () => {
    if (files.length === 0) return;

    const raw = localStorage.getItem("userSchedule");
    if (!raw) {
      setError("未找到作息设置，请返回首页重新设置");
      return;
    }

    const schedule = JSON.parse(raw);
    const medsRaw = localStorage.getItem("currentMedications");
    const currentMedications = medsRaw ? JSON.parse(medsRaw) : [];

    const formData = new FormData();
    formData.append("image", files[0]);
    formData.append("wake_up_time", schedule.wakeUp);
    formData.append("breakfast_time", schedule.breakfast);
    formData.append("lunch_time", schedule.lunch);
    formData.append("dinner_time", schedule.dinner);
    formData.append("sleep_time", schedule.sleep);
    formData.append("current_medications", JSON.stringify(currentMedications));

    setIsSubmitting(true);
    setError(null);

    try {
      const data = await submitFullProcess(formData);
      localStorage.setItem("taskId", data.task_id);
      navigate("/thinking");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败，请检查后端服务是否运行");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F2F2F7] relative overflow-hidden">
      <MeshGradientBackground />

      <div className="w-full max-w-[383px] min-h-[852px] mx-auto px-6 py-12 relative z-10 flex flex-col">
        <div className="mb-8">
          <h1 className="text-4xl mb-3 text-gray-900 tracking-tight">智能扫描</h1>
          <p className="text-lg text-gray-500">
            上传补剂标签，AI 自动识别成分
          </p>
        </div>

        <div className="flex-1 flex flex-col items-center justify-center mb-8">
          <div className="relative mb-12">
            <div className="w-64 h-64 rounded-full bg-gradient-to-br from-blue-400 via-purple-400 to-pink-400 animate-pulse shadow-[0_0_80px_rgba(147,51,234,0.4)]" />
            <div className="absolute inset-0 flex items-center justify-center">
              <label className={`cursor-pointer ${isSubmitting ? "pointer-events-none opacity-50" : ""}`}>
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                  disabled={isSubmitting}
                />
                <div className="w-32 h-32 rounded-full backdrop-blur-2xl bg-white/30 border-4 border-white/60 flex items-center justify-center shadow-2xl hover:scale-110 transition-transform duration-300">
                  <Camera className="w-16 h-16 text-white" />
                </div>
              </label>
            </div>
          </div>

          <p className="text-center text-gray-600 mb-2">点击中央按钮开始拍照</p>
          <p className="text-sm text-gray-400">支持多张连拍识别</p>
        </div>

        {images.length > 0 && (
          <div className="mb-8">
            <div className="flex gap-3 overflow-x-auto pb-4 mb-6">
              {images.map((image, index) => (
                <div
                  key={index}
                  className="relative flex-shrink-0"
                >
                  <GlassCard className="w-24 h-24 p-1 group">
                    <img
                      src={image}
                      alt={`补剂 ${index + 1}`}
                      className="w-full h-full object-cover rounded-[24px]"
                    />
                    <button
                      onClick={() => removeImage(index)}
                      disabled={isSubmitting}
                      className="absolute -top-2 -right-2 w-7 h-7 bg-red-500 text-white rounded-full flex items-center justify-center shadow-lg opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-30"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </GlassCard>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-2xl text-red-600 text-sm">
            {error}
          </div>
        )}

        <div className="fixed bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-[#F2F2F7] to-transparent">
          <div className="max-w-[383px] mx-auto">
            <GlassCard className="p-4">
              <button
                onClick={handleGenerate}
                disabled={images.length === 0 || isSubmitting}
                className={`w-full py-5 rounded-[24px] text-lg shadow-lg transition-all duration-300 flex items-center justify-center gap-2 ${
                  images.length > 0 && !isSubmitting
                    ? "bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white hover:shadow-xl"
                    : "bg-gray-200 text-gray-400 cursor-not-allowed"
                }`}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>提交中...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    <span>开始 AI 分析 ({images.length})</span>
                  </>
                )}
              </button>
            </GlassCard>
          </div>
        </div>
      </div>
    </div>
  );
}
