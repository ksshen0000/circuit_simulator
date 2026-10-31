import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..models.circuit import CircuitSummary, ProjectCreate, ProjectDetail, ProjectSummary

router = APIRouter(prefix="/projects", tags=["projects"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("", response_model=list[ProjectSummary])
def list_projects():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.updated_at, COUNT(c.id) AS circuit_count
            FROM projects p LEFT JOIN circuits c ON c.project_id = p.id
            GROUP BY p.id ORDER BY p.updated_at DESC
            """
        ).fetchall()
    return [
        ProjectSummary(id=r["id"], name=r["name"], circuit_count=r["circuit_count"], updated_at=r["updated_at"])
        for r in rows
    ]


@router.post("", response_model=ProjectDetail, status_code=201)
def create_project(body: ProjectCreate):
    pid = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?,?,?,?)",
            (pid, body.name, now, now),
        )
    return ProjectDetail(id=pid, name=body.name, created_at=now, updated_at=now, circuits=[])


@router.get("/{pid}", response_model=ProjectDetail)
def get_project(pid: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        circuits = conn.execute(
            "SELECT id, name, project_id, updated_at FROM circuits WHERE project_id=? ORDER BY updated_at DESC",
            (pid,),
        ).fetchall()
    return ProjectDetail(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        circuits=[
            CircuitSummary(id=c["id"], name=c["name"], project_id=c["project_id"], updated_at=c["updated_at"])
            for c in circuits
        ],
    )


@router.put("/{pid}", response_model=ProjectDetail)
def rename_project(pid: str, body: ProjectCreate):
    now = _now()
    with get_conn() as conn:
        cur = conn.execute("UPDATE projects SET name=?, updated_at=? WHERE id=?", (body.name, now, pid))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        row = conn.execute("SELECT created_at FROM projects WHERE id=?", (pid,)).fetchone()
        circuits = conn.execute(
            "SELECT id, name, project_id, updated_at FROM circuits WHERE project_id=? ORDER BY updated_at DESC",
            (pid,),
        ).fetchall()
    return ProjectDetail(
        id=pid,
        name=body.name,
        created_at=row["created_at"],
        updated_at=now,
        circuits=[
            CircuitSummary(id=c["id"], name=c["name"], project_id=c["project_id"], updated_at=c["updated_at"])
            for c in circuits
        ],
    )


@router.delete("/{pid}", status_code=204)
def delete_project(pid: str):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        # Detach circuits rather than deleting them (FK ON DELETE SET NULL).
        conn.execute("UPDATE circuits SET project_id=NULL WHERE project_id=?", (pid,))
