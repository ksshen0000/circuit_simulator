import type { CircuitElement, Wire } from "../types/circuit";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface CircuitSummary {
  id: string;
  name: string;
  updated_at: string;
}

export interface CircuitDetail {
  id: string;
  name: string;
  elements: Record<string, CircuitElement>;
  wires: Record<string, Wire>;
  ground_element_id: string | null;
  created_at: string;
  updated_at: string;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const circuitApi = {
  list: () => apiFetch<CircuitSummary[]>("/circuits"),

  save: (name: string, elements: Record<string, CircuitElement>, wires: Record<string, Wire>, groundElementId: string | null) =>
    apiFetch<CircuitDetail>("/circuits", {
      method: "POST",
      body: JSON.stringify({ name, elements, wires, ground_element_id: groundElementId }),
    }),

  update: (id: string, name: string, elements: Record<string, CircuitElement>, wires: Record<string, Wire>, groundElementId: string | null) =>
    apiFetch<CircuitDetail>(`/circuits/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name, elements, wires, ground_element_id: groundElementId }),
    }),

  load: (id: string) => apiFetch<CircuitDetail>(`/circuits/${id}`),

  delete: (id: string) => apiFetch<void>(`/circuits/${id}`, { method: "DELETE" }),
};
