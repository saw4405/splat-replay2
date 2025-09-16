const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export async function fetchRecorderState() {
  return request("/recorder/state");
}

export async function postRecorderAction(action) {
  return request(`/recorder/${action}`, { method: "POST" });
}

export async function startMonitorRequest() {
  return request("/recorder/monitor/start", { method: "POST" });
}

export async function stopMonitorRequest() {
  return request("/recorder/monitor/stop", { method: "POST" });
}

export async function runWorkflowRequest(path) {
  return request(path, { method: "POST" });
}

export async function fetchRecordedAssets() {
  return request("/assets/recorded");
}

export async function fetchEditedAssets() {
  return request("/assets/edited");
}

export async function updateRecordedMetadata(assetId, metadata) {
  return request(`/assets/recorded/${assetId}/metadata`, {
    method: "PUT",
    body: JSON.stringify({ metadata }),
  });
}

export async function deleteRecordedAssetRequest(assetId) {
  return request(`/assets/recorded/${assetId}`, { method: "DELETE" });
}

export async function deleteEditedAssetRequest(assetId) {
  return request(`/assets/edited/${assetId}`, { method: "DELETE" });
}

export async function fetchEvents(after) {
  const query = after ? `?after=${encodeURIComponent(after)}` : "";
  return request(`/events${query}`);
}

export async function fetchBehaviorSettings() {
  return request("/settings/behavior");
}

export async function updateBehaviorSettingsRequest(payload) {
  return request("/settings/behavior", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export { API_BASE };
