"""
LLM 客户端抽象层

提供统一的 LLM 接口，支持：
- 多模型后端（DashScope/OpenAI/Claude）
- 自动重试机制
- 超时配置
- 熔断器模式
- 优雅降级
"""

import os
import time
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
from functools import wraps
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError
from enum import Enum


class ModelProvider(Enum):
    """支持的模型提供商"""
    DASHSCOPE = "dashscope"
    OPENAI = "openai"
    CLAUDE = "claude"  # 预留，需额外安装 anthropic 库


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态，快速失败
    HALF_OPEN = "half_open"  # 半开状态，尝试恢复


class CircuitBreaker:
    """
    熔断器实现

    当连续失败达到阈值时，自动切换到 OPEN 状态，
    在 OPEN 状态下快速失败，不再调用后端服务。
    经过一段时间后进入 HALF_OPEN 状态，尝试一次请求，
    如果成功则恢复 CLOSED 状态，失败则继续 OPEN。
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def call(self, func, *args, **kwargs):
        """执行带熔断保护的调用"""
        if self.state == CircuitState.OPEN:
            # 检查是否可以尝试恢复
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpenError("服务不可用，请稍后重试")

        if self.state == CircuitState.HALF_OPEN and self.half_open_calls >= self.half_open_max_calls:
            raise CircuitBreakerOpenError("服务正在恢复中，请稍后重试")

        try:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1

            result = func(*args, **kwargs)

            # 调用成功
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.half_open_calls = 0

            return result

        except Exception as e:
            self._record_failure()
            raise e

    def _record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass


class LLMClient:
    """
    统一的 LLM 客户端

    支持配置：
    - 重试次数
    - 重试延迟
    - 超时时间
    - 熔断器
    - 回退模型
    """

    def __init__(
        self,
        provider: ModelProvider = ModelProvider.DASHSCOPE,
        model: str = "qwen-max",
        fallback_model: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        timeout: int = 30,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.provider = provider
        self.model = model
        self.fallback_model = fallback_model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.timeout = timeout
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

        self._client: Optional[OpenAI] = None
        self._init_client()

    def _init_client(self):
        """初始化客户端"""
        # 尝试从多个来源获取 API 密钥
        api_key = os.getenv("DASHSCOPE_API_KEY")

        # 如果没有设置环境变量，尝试从.env 文件加载
        if not api_key:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("DASHSCOPE_API_KEY")

        if not api_key:
            raise ValueError("API key not found. Please set DASHSCOPE_API_KEY or OPENAI_API_KEY")

        if self.provider == ModelProvider.DASHSCOPE:
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout=self.timeout
            )
        elif self.provider == ModelProvider.OPENAI:
            self._client = OpenAI(
                api_key=api_key,
                timeout=self.timeout
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _execute_with_retry(self, func, **kwargs):
        """执行带重试和熔断的调用"""
        current_model = self.model
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                # 熔断器检查
                return self.circuit_breaker.call(func, **kwargs)

            except (CircuitBreakerOpenError, APITimeoutError) as e:
                # 熔断器打开或超时，快速失败
                last_error = e
                if attempt == self.max_retries:
                    break
                # 不重试，直接尝试降级或退出
                break

            except (APIConnectionError, APIError) as e:
                # 网络错误或 API 错误，可以重试
                last_error = e
                if attempt == self.max_retries:
                    break

                # 指数退避
                wait_time = self.retry_delay * (self.retry_backoff ** attempt)
                time.sleep(wait_time)

            except Exception as e:
                # 其他异常，记录失败并重试
                last_error = e
                self.circuit_breaker._record_failure()
                if attempt == self.max_retries:
                    break

        # 所有重试失败，尝试降级
        if self.fallback_model and current_model != self.fallback_model:
            print(f"主模型 {current_model} 调用失败，尝试降级到 {self.fallback_model}")
            self.model = self.fallback_model
            self._init_client()
            try:
                return func(**kwargs)
            except Exception as fallback_error:
                last_error = fallback_error

        raise LLMCallError(f"LLM 调用失败：{str(last_error)}", last_error)

    def chat_completion(self, messages: List[Dict], **kwargs) -> str:
        """
        同步聊天调用

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            **kwargs: 其他参数 (temperature, max_tokens, etc.)

        Returns:
            响应文本
        """
        def _call(**call_kwargs):
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                **call_kwargs
            )
            return response.choices[0].message.content

        return self._execute_with_retry(_call, **kwargs)

    def chat_completion_stream(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        """
        流式聊天调用

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Yields:
            文本片段
        """
        def _call(**call_kwargs):
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **call_kwargs
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        for chunk in self._execute_with_retry(_call, **kwargs):
            yield chunk

    async def chat_completion_async(self, messages: List[Dict], **kwargs) -> str:
        """异步聊天调用"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.chat_completion, messages, **kwargs)

    async def chat_completion_stream_async(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        """异步流式调用"""
        loop = asyncio.get_event_loop()

        def _generate():
            for chunk in self.chat_completion_stream(messages, **kwargs):
                yield chunk

        for chunk in _generate():
            yield chunk
            await asyncio.sleep(0.01)  # 让流式更平滑


class LLMCallError(Exception):
    """LLM 调用失败异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


# ==================== 便捷工厂函数 ====================

def get_dashscope_client(
    model: str = "qwen-max",
    fallback_model: Optional[str] = "qwen-plus",
    max_retries: int = 3,
    timeout: int = 30
) -> LLMClient:
    """获取 DashScope 客户端（带重试和熔断）"""
    return LLMClient(
        provider=ModelProvider.DASHSCOPE,
        model=model,
        fallback_model=fallback_model,
        max_retries=max_retries,
        timeout=timeout
    )


def get_openai_client(
    model: str = "gpt-4o",
    fallback_model: Optional[str] = "gpt-4o-mini",
    max_retries: int = 3,
    timeout: int = 30
) -> LLMClient:
    """获取 OpenAI 客户端（带重试和熔断）"""
    return LLMClient(
        provider=ModelProvider.OPENAI,
        model=model,
        fallback_model=fallback_model,
        max_retries=max_retries,
        timeout=timeout
    )


# ==================== 装饰器 ====================

def with_llm_retry(func):
    """
    为函数添加 LLM 重试和熔断装饰

    使用方式：
    @with_llm_retry
    async def my_llm_function(...):
        ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper
