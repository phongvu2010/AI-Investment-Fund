"""
AI Agent Harness cho Hệ thống Quỹ Đầu tư Cá nhân (Antigravity 2.0).
Cung cấp các lớp kiểm soát vòng đời thực thi, an toàn vốn và tự sửa chữa:
1. HarnessContextManager: Nạp trạng thái tài chính, phân bổ Dual-Book và bộ nhớ thất bại vào Prompt.
2. GuardrailMiddleware: Bộ lọc kiểm duyệt cứng (Hard Veto) bọc quanh lệnh giao dịch và rủi ro Jev AI.
3. HarnessVerificationLoop: Vòng lặp kiểm định Out-of-Sample và tự sửa chữa mã chiến lược.
"""

from harness.context_manager import HarnessContextManager
from harness.guardrail_middleware import GuardrailMiddleware, GuardrailVetoException
from harness.verification_loop import HarnessVerificationLoop

__all__ = [
    "HarnessContextManager",
    "GuardrailMiddleware",
    "GuardrailVetoException",
    "HarnessVerificationLoop"
]
