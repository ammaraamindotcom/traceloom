/** Build-time public frontend configuration. Never add secrets to this module. */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const INTENT_INFERENCE_ENABLED = import.meta.env.VITE_ENABLE_INTENT_INFERENCE !== "false";
