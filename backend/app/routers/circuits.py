import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..models.circuit import CircuitDetail, CircuitSummary, SaveCircuitRequest

router = APIRouter(prefix="/circuits", tags=["circuits"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("", response_model=list[CircuitSummary])
def list_circuits(project_id: str | None = None):
    with get_conn() as conn:
        if project_id is None:
            rows = conn.execute(
                "SELECT id, name, project_id, updated_at FROM circuits ORDER BY updated_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, project_id, updated_at FROM circuits WHERE project_id=? ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
    return [CircuitSummary(id=r["id"], name=r["name"], project_id=r["project_id"], updated_at=r["updated_at"]) for r in rows]


@router.post("", response_model=CircuitDetail, status_code=201)
def create_circuit(body: SaveCircuitRequest):
    cid = str(uuid.uuid4())
    now = _now()
    data = body.model_dump(mode="json")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO circuits (id, name, elements, wires, ground_element_id, project_id, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (cid, body.name, json.dumps(data["elements"]), json.dumps(data["wires"]),
             body.ground_element_id, body.project_id, now, now),
        )
    return CircuitDetail(
        id=cid, name=body.name,
        elements=data["elements"], wires=data["wires"],
        ground_element_id=body.ground_element_id,
        project_id=body.project_id,
        created_at=now, updated_at=now,
    )


@router.get("/{cid}", response_model=CircuitDetail)
def get_circuit(cid: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM circuits WHERE id=?", (cid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Circuit not found")
    return CircuitDetail(
        id=row["id"], name=row["name"],
        elements=json.loads(row["elements"]),
        wires=json.loads(row["wires"]),
        ground_element_id=row["ground_element_id"],
        project_id=row["project_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.put("/{cid}", response_model=CircuitDetail)
def update_circuit(cid: str, body: SaveCircuitRequest):
    now = _now()
    data = body.model_dump(mode="json")
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE circuits SET name=?, elements=?, wires=?, ground_element_id=?, project_id=?, updated_at=?"
            " WHERE id=?",
            (body.name, json.dumps(data["elements"]), json.dumps(data["wires"]),
             body.ground_element_id, body.project_id, now, cid),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Circuit not found")
        row = conn.execute("SELECT created_at FROM circuits WHERE id=?", (cid,)).fetchone()
    return CircuitDetail(
        id=cid, name=body.name,
        elements=data["elements"], wires=data["wires"],
        ground_element_id=body.ground_element_id,
        project_id=body.project_id,
        created_at=row["created_at"], updated_at=now,
    )


@router.delete("/{cid}", status_code=204)
def delete_circuit(cid: str):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM circuits WHERE id=?", (cid,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Circuit not found")
