"""Replaceable OpenAI-backed intent inference over existing structured evidence."""

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

try:
    from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

    OPENAI_SDK_AVAILABLE = True
except ImportError:  # Allows the rest of the app and mocked tests to run before dependency setup.
    OPENAI_SDK_AVAILABLE = False

    class OpenAI:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("OpenAI SDK is unavailable")

    class APIConnectionError(Exception):  # type: ignore[no-redef]
        pass

    class APIStatusError(Exception):  # type: ignore[no-redef]
        pass

    class APITimeoutError(Exception):  # type: ignore[no-redef]
        pass

from app.config import APP_ENV, OPENAI_API_KEY, OPENAI_MODEL
from app.prompts.intent_system_prompt import INTENT_SYSTEM_PROMPT
from app.schemas import AnalysisResult, IntentInference


class IntentServiceError(Exception):
    """Safe error carrying an HTTP status and no provider secrets."""

    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


logger = logging.getLogger(__name__)


def _safe_provider_error_message(exc: Exception) -> str:
    """Keep development diagnostics useful without ever logging credentials."""
    message = str(exc)
    message = re.sub(r"sk-[A-Za-z0-9_-]+", "<redacted-api-key>", message)
    message = re.sub(
        r"(?i)(authorization|api[_-]?key|bearer)\s*[:=]\s*[^\s,]+",
        r"\1=<redacted>",
        message,
    )
    return message[:500]


def _log_provider_failure(exc: Exception) -> None:
    if APP_ENV in {"development", "dev"}:
        logger.warning(
            "OpenAI intent inference failed: type=%s status=%s code=%s message=%s",
            type(exc).__name__,
            getattr(exc, "status_code", "n/a"),
            _safe_provider_error_message(str(getattr(exc, "code", "n/a"))),
            _safe_provider_error_message(exc),
        )


def build_intent_input(analysis: AnalysisResult) -> dict[str, Any]:
    """Create the minimal, structured evidence sent as an untrusted user message."""
    return {
        "user_id": analysis.user_id,
        "deterministic_risk": {
            "risk_level": analysis.risk_level,
            "risk_score": analysis.risk_score,
        },
        "behavioral_baseline": analysis.baseline.model_dump(mode="json"),
        "deterministic_signals": [signal.model_dump(mode="json") for signal in analysis.signals],
        "recent_activity_sequence": [
            {
                "timestamp": activity.timestamp.isoformat(),
                "event_type": activity.event_type,
                "metadata": activity.metadata,
            }
            for activity in analysis.recent_activities
        ],
    }


def _validate_inference(inference: IntentInference, analysis: AnalysisResult) -> IntentInference:
    if not 0 <= inference.confidence <= 1:
        raise IntentServiceError("The intent provider returned an invalid confidence value.")

    supplied_signal_types = {signal.type for signal in analysis.signals}
    unsupported_evidence = [item.signal for item in inference.evidence if item.signal not in supplied_signal_types]
    if unsupported_evidence:
        raise IntentServiceError("The intent provider cited evidence not present in deterministic analysis.")
    return inference


def infer_intent(analysis: AnalysisResult, client: OpenAI | None = None) -> IntentInference:
    """Request one explicitly triggered structured inference; no caching or background calls."""
    if not OPENAI_API_KEY:
        raise IntentServiceError("Intent inference is not configured. Set OPENAI_API_KEY on the backend.", 503)
    if not OPENAI_SDK_AVAILABLE and client is None:
        raise IntentServiceError("Intent inference is unavailable. Install the backend dependencies and restart the server.", 503)

    telemetry_json = json.dumps(build_intent_input(analysis), separators=(",", ":"), default=str)
    api_client = client or OpenAI(api_key=OPENAI_API_KEY, timeout=20.0, max_retries=0)
    try:
        completion = api_client.beta.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "UNTRUSTED_TELEMETRY_JSON\n" + telemetry_json,
                },
            ],
            response_format=IntentInference,
        )
        message = completion.choices[0].message
        if message.refusal or message.parsed is None:
            raise IntentServiceError("The intent provider did not return a usable structured result.")
        return _validate_inference(message.parsed, analysis)
    except IntentServiceError:
        raise
    except APITimeoutError as exc:
        _log_provider_failure(exc)
        raise IntentServiceError("Intent inference timed out. Please try again.", 504) from exc
    except (APIConnectionError, APIStatusError) as exc:
        _log_provider_failure(exc)
        raise IntentServiceError("Intent inference is temporarily unavailable. Please try again.") from exc
    except (ValidationError, AttributeError, IndexError, TypeError) as exc:
        _log_provider_failure(exc)
        raise IntentServiceError("The intent provider returned an invalid structured result.") from exc
