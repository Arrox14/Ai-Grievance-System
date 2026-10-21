import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import HTTPException


def validate_admin_status_transition(
    connection: sqlite3.Connection,
    complaint_id: int,
    new_status: str,
) -> str:
    row = connection.execute(
        "SELECT status FROM complaints WHERE id = ?",
        (complaint_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    current_status = row[0] or "Pending"
    allowed_transitions = {
        "Pending": {"Pending", "In Progress"},
        "In Progress": {"In Progress", "Pending"},
        "Resolved": {"Resolved"},
    }
    if new_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Status cannot transition from {current_status} to {new_status}",
        )
    return current_status


def transition_complaint_status(
    connection: sqlite3.Connection,
    complaint_id: int,
    new_status: str,
    actor: dict,
    remarks: Optional[str] = None,
    *,
    changed_at: Optional[str] = None,
    required_previous_status: Optional[str] = None,
    officer_id: Optional[int] = None,
    update_resolution: bool = False,
    resolution_date: Optional[str] = None,
    resolution_remarks: Optional[str] = None,
) -> dict:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT status, user_id, officer_id, resolution_date, resolution_remarks
        FROM complaints
        WHERE id = ?
        """,
        (complaint_id,),
    )
    complaint = cursor.fetchone()
    if complaint is None or (
        officer_id is not None and complaint[2] != officer_id
    ):
        raise HTTPException(status_code=404, detail="Complaint not found")

    previous_status, owner_id = complaint[0], complaint[1]
    if (
        required_previous_status is not None
        and previous_status != required_previous_status
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Status cannot transition from {previous_status} to {new_status}",
        )

    status_changed = previous_status != new_status
    metadata_changed = update_resolution and (
        complaint[3] != resolution_date
        or complaint[4] != resolution_remarks
    )
    if not status_changed and not metadata_changed:
        return {
            "changed": False,
            "updated": False,
            "previous_status": previous_status,
            "new_status": new_status,
            "changed_at": None,
            "owner_id": owner_id,
        }

    event_time = changed_at or datetime.now().isoformat()
    update_fields = ["status = ?"]
    update_values = [new_status]
    if update_resolution:
        update_fields.extend(
            ["resolution_date = ?", "resolution_remarks = ?"]
        )
        update_values.extend([resolution_date, resolution_remarks])

    where_clause = "id = ? AND status = ?"
    update_values.extend([complaint_id, previous_status])
    if officer_id is not None:
        where_clause += " AND officer_id = ?"
        update_values.append(officer_id)
    cursor.execute(
        f"UPDATE complaints SET {', '.join(update_fields)} WHERE {where_clause}",
        update_values,
    )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=409, detail="Complaint status changed concurrently")

    if status_changed:
        cursor.execute(
            """
            INSERT INTO complaint_status_history
            (complaint_id, previous_status, status, changed_at, actor_id,
             actor_name, actor_email, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                complaint_id,
                previous_status,
                new_status,
                event_time,
                actor["id"],
                actor["name"],
                actor["email"],
                remarks,
            ),
        )

    return {
        "changed": status_changed,
        "updated": status_changed or metadata_changed,
        "previous_status": previous_status,
        "new_status": new_status,
        "changed_at": event_time if status_changed else None,
        "owner_id": owner_id,
    }


def assign_complaint(
    connection: sqlite3.Connection,
    complaint_id: int,
    officer_id: int,
    assigned_by: int,
    assigned_at: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT u.id, p.user_id, p.department_id, u.role, u.is_active, d.is_active
        FROM users u
        LEFT JOIN officer_profiles p ON p.user_id = u.id
        LEFT JOIN departments d ON d.id = p.department_id
        WHERE u.id = ?
        """,
        (officer_id,),
    )
    officer = cursor.fetchone()
    if officer is None:
        raise HTTPException(status_code=404, detail="Officer not found")
    if officer[3] != "officer" or officer[1] is None:
        raise HTTPException(
            status_code=422,
            detail="Selected user is not eligible for complaint assignment",
        )
    if not officer[4] or (officer[2] is not None and officer[5] != 1):
        raise HTTPException(
            status_code=422,
            detail="Selected officer or their department is inactive",
        )

    cursor.execute(
        "SELECT user_id, officer_id, assigned_at FROM complaints WHERE id = ?",
        (complaint_id,),
    )
    complaint = cursor.fetchone()
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint[1] == officer_id:
        return {
            "changed": False,
            "owner_id": complaint[0],
            "previous_officer_id": complaint[1],
            "officer_id": officer_id,
            "assigned_at": complaint[2],
        }

    event_time = assigned_at or datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO complaint_assignment_history
        (complaint_id, previous_officer_id, new_officer_id, department_id,
         assigned_by, assigned_at, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            complaint_id,
            complaint[1],
            officer[0],
            officer[2],
            assigned_by,
            event_time,
            reason,
        ),
    )
    cursor.execute(
        """
        UPDATE complaints SET officer_id = ?, assigned_at = ?
        WHERE id = ? AND officer_id IS ?
        """,
        (officer[0], event_time, complaint_id, complaint[1]),
    )
    if cursor.rowcount != 1:
        raise HTTPException(
            status_code=409,
            detail="Complaint assignment changed concurrently",
        )
    return {
        "changed": True,
        "owner_id": complaint[0],
        "previous_officer_id": complaint[1],
        "officer_id": officer[0],
        "assigned_at": event_time,
    }
