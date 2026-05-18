"""JS Sandbox runtime for executing real JS functions (REPLAY-RUNTIME-1).

Provides a protocol-based sandbox that runs JS code in a Node.js subprocess.
Falls back gracefully when Node.js is unavailable.

Does NOT recover keys, bypass protections, or execute untrusted code from
the wild. All code is CLM-generated or user-provided fixture code.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Output limits and security constants
# ---------------------------------------------------------------------------

_MAX_OUTPUT_LENGTH = 4096
_MAX_STDERR_LENGTH = 2048
_DEFAULT_TIMEOUT_MS = 5000

_SENSITIVE_KEYS = frozenset({
    "secret", "secret_key", "api_secret", "api_key", "password",
    "token", "auth", "authorization", "bearer", "private_key",
    "x-sign", "x-signature", "x-token", "key",
})

_REDACT_PLACEHOLDER = "***REDACTED***"


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class SandboxResult:
    """Result of a sandbox JS execution."""
    status: str  # ok | timeout | error | missing_runtime | skipped
    result: Any = None
    error: str = ""
    duration_ms: float = 0.0
    runtime_events: list[dict[str, Any]] = field(default_factory=list)
    redacted_preview: str = ""
    execution_mode: str = "sandbox"  # sandbox | fixture_stub | skipped | error

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "execution_mode": self.execution_mode,
        }
        if self.result is not None:
            d["result"] = _redact_value(self.result)
        if self.error:
            d["error"] = self.error[:_MAX_STDERR_LENGTH]
        if self.redacted_preview:
            d["redacted_preview"] = self.redacted_preview[:_MAX_OUTPUT_LENGTH]
        if self.runtime_events:
            d["runtime_events"] = self.runtime_events[-20:]
        return d


def _redact_value(value: Any) -> Any:
    """Redact sensitive values from output."""
    if isinstance(value, dict):
        return {k: (_REDACT_PLACEHOLDER if k.lower() in _SENSITIVE_KEYS else _redact_value(v))
                for k, v in value.items()}
    if isinstance(value, str):
        if any(kw in value.lower() for kw in ("secret", "password", "api_key")):
            return _REDACT_PLACEHOLDER
        if len(value) > _MAX_OUTPUT_LENGTH:
            return value[:_MAX_OUTPUT_LENGTH] + "...[truncated]"
        return value
    if isinstance(value, list):
        return [_redact_value(v) for v in value[:50]]
    return value


# ---------------------------------------------------------------------------
# Runtime protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class JSRuntime(Protocol):
    """Protocol for JS sandbox runtimes."""

    def execute(
        self,
        source: str,
        function_name: str,
        args: dict[str, Any],
        *,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
        allowed_globals: list[str] | None = None,
        dynamic_inputs: dict[str, Any] | None = None,
    ) -> SandboxResult:
        """Execute a JS function with the given arguments.

        Args:
            source: JS source code containing the function.
            function_name: Name of the function to call.
            args: Arguments to pass to the function (JSON-serializable).
            timeout_ms: Execution timeout in milliseconds.
            allowed_globals: Restrict available globals (advisory).
            dynamic_inputs: Additional dynamic values to inject.

        Returns:
            SandboxResult with status, result, and metadata.
        """
        ...

    def is_available(self) -> bool:
        """Check if this runtime is available on the system."""
        ...

    @property
    def name(self) -> str:
        """Runtime name for logging."""
        ...


# ---------------------------------------------------------------------------
# Node.js subprocess runtime
# ---------------------------------------------------------------------------

class NodeJSRuntime:
    """Execute JS functions via Node.js subprocess."""

    @property
    def name(self) -> str:
        return "nodejs"

    def is_available(self) -> bool:
        return shutil.which("node") is not None

    def execute(
        self,
        source: str,
        function_name: str,
        args: dict[str, Any],
        *,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
        allowed_globals: list[str] | None = None,
        dynamic_inputs: dict[str, Any] | None = None,
    ) -> SandboxResult:
        if not self.is_available():
            return SandboxResult(
                status="missing_runtime",
                error="Node.js not found on system",
                execution_mode="skipped",
            )

        t0 = time.monotonic()
        args_json = json.dumps(args, default=str)
        dyn_json = json.dumps(dynamic_inputs or {}, default=str)

        # Build a self-contained JS wrapper that:
        # 1. Evaluates the source code
        # 2. Calls the named function with parsed args
        # 3. Injects dynamic_inputs as a global
        # 4. Outputs JSON result to stdout
        wrapper = _build_wrapper(source, function_name, args_json, dyn_json)

        timeout_s = max(timeout_ms / 1000.0, 0.5)

        try:
            proc = subprocess.run(
                ["node", "--eval", wrapper],
                capture_output=True,
                timeout=timeout_s,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                status="timeout",
                error=f"Execution timed out after {timeout_ms}ms",
                duration_ms=(time.monotonic() - t0) * 1000,
                execution_mode="error",
                runtime_events=[{"event": "timeout", "timeout_ms": timeout_ms}],
            )
        except FileNotFoundError:
            return SandboxResult(
                status="missing_runtime",
                error="Node.js executable not found",
                duration_ms=(time.monotonic() - t0) * 1000,
                execution_mode="skipped",
            )
        except Exception as exc:
            return SandboxResult(
                status="error",
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.monotonic() - t0) * 1000,
                execution_mode="error",
            )

        elapsed_ms = (time.monotonic() - t0) * 1000

        if proc.returncode != 0:
            stderr = proc.stderr[:_MAX_STDERR_LENGTH] if proc.stderr else ""
            return SandboxResult(
                status="error",
                error=f"exit_code={proc.returncode}: {stderr}",
                duration_ms=elapsed_ms,
                execution_mode="error",
                runtime_events=[
                    {"event": "exit", "code": proc.returncode},
                    {"event": "stderr", "text": stderr[:500]},
                ],
            )

        stdout = proc.stdout.strip() if proc.stdout else ""
        if not stdout:
            return SandboxResult(
                status="error",
                error="No output from sandbox (empty stdout)",
                duration_ms=elapsed_ms,
                execution_mode="error",
            )

        # Parse JSON result
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            # Treat raw stdout as string result
            parsed = {"raw": stdout[:_MAX_OUTPUT_LENGTH]}

        result_value = parsed.get("result") if isinstance(parsed, dict) else parsed
        stderr_text = proc.stderr[:500] if proc.stderr else ""

        return SandboxResult(
            status="ok",
            result=result_value,
            duration_ms=elapsed_ms,
            execution_mode="sandbox",
            redacted_preview=json.dumps(_redact_value(result_value), default=str)[:_MAX_OUTPUT_LENGTH],
            runtime_events=[
                {"event": "execute", "function": function_name, "duration_ms": round(elapsed_ms, 2)},
                *([{"event": "stderr", "text": stderr_text}] if stderr_text else []),
            ],
        )


def _build_wrapper(source: str, function_name: str, args_json: str, dyn_json: str) -> str:
    """Build a self-contained JS wrapper for Node.js --eval."""
    # Escape for JS string embedding
    def _js_str(s: str) -> str:
        return json.dumps(s)

    return f"""
'use strict';
try {{
    // Inject dynamic inputs
    const __dynamicInputs = {dyn_json};

    // Evaluate user source
    const __module = {{}};
    const __fn = (function() {{
        {source}
        if (typeof {function_name} === 'function') return {function_name};
        if (typeof module !== 'undefined' && module.exports && module.exports.{function_name}) return module.exports.{function_name};
        throw new Error('Function not found: {function_name}');
    }})();

    // Parse args
    const __args = JSON.parse({json.dumps(args_json)});

    // Call
    const __result = __fn(__args, __dynamicInputs);

    // Handle promises
    if (__result && typeof __result.then === 'function') {{
        __result.then(r => {{
            process.stdout.write(JSON.stringify({{ result: r }}));
        }}).catch(e => {{
            process.stderr.write(String(e));
            process.exit(1);
        }});
    }} else {{
        process.stdout.write(JSON.stringify({{ result: __result }}));
    }}
}} catch(e) {{
    process.stderr.write(String(e));
    process.exit(1);
}}
"""


# ---------------------------------------------------------------------------
# Composite runtime with fallback
# ---------------------------------------------------------------------------

class CompositeRuntime:
    """Try multiple runtimes in order, falling back on failure."""

    def __init__(self, runtimes: list[JSRuntime | Any] | None = None):
        if runtimes is None:
            runtimes = [NodeJSRuntime()]
        self._runtimes = runtimes

    @property
    def name(self) -> str:
        names = [r.name for r in self._runtimes if hasattr(r, 'name')]
        return f"composite({','.join(names)})"

    def is_available(self) -> bool:
        return any(r.is_available() for r in self._runtimes)

    def execute(
        self,
        source: str,
        function_name: str,
        args: dict[str, Any],
        *,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
        allowed_globals: list[str] | None = None,
        dynamic_inputs: dict[str, Any] | None = None,
    ) -> SandboxResult:
        last_result: SandboxResult | None = None
        for runtime in self._runtimes:
            if not runtime.is_available():
                continue
            result = runtime.execute(
                source, function_name, args,
                timeout_ms=timeout_ms,
                allowed_globals=allowed_globals,
                dynamic_inputs=dynamic_inputs,
            )
            if result.status == "ok":
                return result
            last_result = result

        if last_result is not None:
            return last_result
        return SandboxResult(
            status="missing_runtime",
            error="No JS runtime available",
            execution_mode="skipped",
        )


# ---------------------------------------------------------------------------
# Module-level default runtime
# ---------------------------------------------------------------------------

_default_runtime: CompositeRuntime | None = None


def get_default_runtime() -> CompositeRuntime:
    """Get or create the module-level default runtime."""
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = CompositeRuntime()
    return _default_runtime


def set_default_runtime(runtime: CompositeRuntime | None) -> None:
    """Override the default runtime (for testing)."""
    global _default_runtime
    _default_runtime = runtime
