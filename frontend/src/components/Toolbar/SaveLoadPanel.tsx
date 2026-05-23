import { useState, useEffect, useRef } from "react";
import { useCircuitStore } from "../../store/circuitStore";
import { circuitApi, type CircuitSummary } from "../../utils/circuitApi";

export function SaveLoadPanel() {
  const { elements, wires, groundElementId, currentCircuitId, currentCircuitName, setCircuitMeta, loadFromData } = useCircuitStore();

  const [saving, setSaving] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [showSaveForm, setShowSaveForm] = useState(false);

  const [showLibrary, setShowLibrary] = useState(false);
  const [circuits, setCircuits] = useState<CircuitSummary[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const libraryRef = useRef<HTMLDivElement>(null);

  // Close library on outside click
  useEffect(() => {
    if (!showLibrary) return;
    const handler = (e: MouseEvent) => {
      if (libraryRef.current && !libraryRef.current.contains(e.target as Node)) {
        setShowLibrary(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showLibrary]);

  const flash = (msg: string) => {
    setFeedback(msg);
    setTimeout(() => setFeedback(null), 2000);
  };

  const openSaveForm = () => {
    setNameInput(currentCircuitName);
    setShowSaveForm(true);
    setShowLibrary(false);
  };

  const confirmSave = async () => {
    const name = nameInput.trim() || "未命名电路";
    setSaving(true);
    try {
      let detail;
      if (currentCircuitId) {
        detail = await circuitApi.update(currentCircuitId, name, elements, wires, groundElementId);
      } else {
        detail = await circuitApi.save(name, elements, wires, groundElementId);
      }
      setCircuitMeta(detail.id, detail.name);
      setShowSaveForm(false);
      flash("已保存");
    } catch (e: unknown) {
      flash(`保存失败: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const openLibrary = async () => {
    setShowLibrary((v) => !v);
    setShowSaveForm(false);
    if (!showLibrary) {
      setLoadingList(true);
      try {
        const list = await circuitApi.list();
        setCircuits(list);
      } finally {
        setLoadingList(false);
      }
    }
  };

  const handleLoad = async (id: string) => {
    try {
      const detail = await circuitApi.load(id);
      loadFromData({
        elements: detail.elements,
        wires: detail.wires,
        groundElementId: detail.ground_element_id,
      });
      setCircuitMeta(detail.id, detail.name);
      setShowLibrary(false);
      flash(`已加载「${detail.name}」`);
    } catch (e: unknown) {
      flash(`加载失败: ${(e as Error).message}`);
    }
  };

  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`删除「${name}」？`)) return;
    try {
      await circuitApi.delete(id);
      setCircuits((prev) => prev.filter((c) => c.id !== id));
      if (currentCircuitId === id) setCircuitMeta(null, "未命名电路");
    } catch (e: unknown) {
      flash(`删除失败: ${(e as Error).message}`);
    }
  };

  const btnStyle = (active = false): React.CSSProperties => ({
    padding: "6px 10px",
    borderRadius: 6,
    border: "1px solid",
    borderColor: active ? "#3b82f6" : "#e2e8f0",
    background: active ? "#eff6ff" : "#fff",
    color: active ? "#1d4ed8" : "#334155",
    cursor: "pointer",
    fontSize: 13,
    whiteSpace: "nowrap",
  });

  return (
    <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 4 }}>
      {/* Current circuit name badge */}
      {currentCircuitId && (
        <span style={{ fontSize: 11, color: "#64748b", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {currentCircuitName}
        </span>
      )}

      {/* Save button */}
      {showSaveForm ? (
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <input
            autoFocus
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") confirmSave(); if (e.key === "Escape") setShowSaveForm(false); }}
            style={{ padding: "4px 8px", borderRadius: 4, border: "1px solid #93c5fd", fontSize: 13, width: 140, outline: "none" }}
            placeholder="电路名称"
          />
          <button onClick={confirmSave} disabled={saving} style={{ ...btnStyle(), borderColor: "#3b82f6", color: "#1d4ed8" }}>
            {saving ? "…" : "确认"}
          </button>
          <button onClick={() => setShowSaveForm(false)} style={btnStyle()}>取消</button>
        </div>
      ) : (
        <button onClick={openSaveForm} style={btnStyle()}>
          💾 {currentCircuitId ? "更新" : "保存"}
        </button>
      )}

      {/* Library button */}
      <button onClick={openLibrary} style={btnStyle(showLibrary)}>
        📂 加载
      </button>

      {/* Feedback toast */}
      {feedback && (
        <span style={{ fontSize: 11, color: "#16a34a", padding: "0 6px" }}>{feedback}</span>
      )}

      {/* Library dropdown */}
      {showLibrary && (
        <div
          ref={libraryRef}
          style={{
            position: "absolute", top: "calc(100% + 6px)", right: 0, zIndex: 100,
            background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8,
            boxShadow: "0 4px 16px rgba(0,0,0,0.1)", minWidth: 260, maxHeight: 360, overflowY: "auto",
          }}
        >
          <div style={{ padding: "8px 12px", borderBottom: "1px solid #f1f5f9", fontSize: 12, fontWeight: 600, color: "#374151" }}>
            已保存的电路
          </div>
          {loadingList ? (
            <div style={{ padding: 16, textAlign: "center", color: "#94a3b8", fontSize: 12 }}>加载中…</div>
          ) : circuits.length === 0 ? (
            <div style={{ padding: 16, textAlign: "center", color: "#94a3b8", fontSize: 12 }}>暂无保存的电路</div>
          ) : (
            circuits.map((c) => (
              <div
                key={c.id}
                onClick={() => handleLoad(c.id)}
                style={{
                  display: "flex", alignItems: "center", padding: "8px 12px",
                  cursor: "pointer", borderBottom: "1px solid #f8fafc",
                  background: c.id === currentCircuitId ? "#eff6ff" : "transparent",
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) => { if (c.id !== currentCircuitId) (e.currentTarget as HTMLDivElement).style.background = "#f8fafc"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = c.id === currentCircuitId ? "#eff6ff" : "transparent"; }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: "#1e293b", fontWeight: c.id === currentCircuitId ? 600 : 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.name}
                  </div>
                  <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>
                    {formatDate(c.updated_at)}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDelete(c.id, c.name, e)}
                  style={{ marginLeft: 8, padding: "2px 6px", fontSize: 11, borderRadius: 4, border: "1px solid #fee2e2", background: "#fff", color: "#ef4444", cursor: "pointer" }}
                >
                  删除
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}
