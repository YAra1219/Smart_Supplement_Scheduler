const API_BASE_URL = "http://localhost:8000";

export interface AsyncTaskResponse {
  task_id: string;
  status: string;
  message?: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
  progress?: number | null;
  stage?: string | null;
}

export async function submitFullProcess(formData: FormData): Promise<AsyncTaskResponse> {
  const res = await fetch(`${API_BASE_URL}/api/async/full-process`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`提交失败 (${res.status}): ${err}`);
  }
  return res.json();
}

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/api/task/${taskId}`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`查询失败 (${res.status}): ${err}`);
  }
  return res.json();
}
