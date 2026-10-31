import type { CircuitElement, Wire } from "../types/circuit";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface CircuitSummary {
  id: string;
  name: string;
  project_id: string | null;
  updated_at: string;
}

export interface CircuitDetail {
  id: string;
  name: string;
  elements: Record<string, CircuitElement>;
  wires: Record<string, Wire>;
  ground_element_id: string | null;
  project_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  circuit_count: number;
  updated_at: string;
}

export interface ProjectDetail {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  circuits: CircuitSummary[];
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

  save: (name: string, elements: Record<string, CircuitElement>, wires: Record<string, Wire>, groundElementId: string | null, projectId: string | null = null) =>
    apiFetch<CircuitDetail>("/circuits", {
      method: "POST",
      body: JSON.stringify({ name, elements, wires, ground_element_id: groundElementId, project_id: projectId }),
    }),

  update: (id: string, name: string, elements: Record<string, CircuitElement>, wires: Record<string, Wire>, groundElementId: string | null, projectId: string | null = null) =>
    apiFetch<CircuitDetail>(`/circuits/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name, elements, wires, ground_element_id: groundElementId, project_id: projectId }),
    }),

  load: (id: string) => apiFetch<CircuitDetail>(`/circuits/${id}`),

  delete: (id: string) => apiFetch<void>(`/circuits/${id}`, { method: "DELETE" }),

  projects: {
    list: () => apiFetch<ProjectSummary[]>("/projects"),
    create: (name: string) => apiFetch<ProjectDetail>("/projects", { method: "POST", body: JSON.stringify({ name }) }),
    rename: (id: string, name: string) => apiFetch<ProjectDetail>(`/projects/${id}`, { method: "PUT", body: JSON.stringify({ name }) }),
    delete: (id: string) => apiFetch<void>(`/projects/${id}`, { method: "DELETE" }),
  },
};
