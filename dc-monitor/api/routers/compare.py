from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from database import get_db
from models import Server, Metric
from typing import List

# Configuración del router [cite: 510]
router = APIRouter(prefix="/metrics", tags=["compare"])

@router.get("/compare", summary="Compare metrics across multiple servers")
def compare_metrics(
    ids: str = Query(..., description="Comma separated server IDs. Example: 1,2,3"),
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Return aggregated metric summaries for multiple servers side by site.
    Useful for identifying which servers are underperforming or overutilized.
    """
    try:
        # Separar los IDs recibidos como string [cite: 523, 604]
        server_ids = [int(i.strip()) for i in ids.split(",")]
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail="Invalid format for server IDs. Use comma separated integers."
        )

    # Límite de diseño de 10 servidores para proteger la base de datos [cite: 527, 605, 607]
    if len(server_ids) > 10:
        raise HTTPException(
            status_code=400, 
            detail="A maximum of 10 servers can be compared at once."
        )

    since = datetime.utcnow() - timedelta(hours=hours) [cite: 531]
    results = []

    for server_id in server_ids:
        # Verificar si el servidor existe [cite: 533]
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            # Si un servidor no existe, se notifica en el resultado sin romper la respuesta [cite: 536, 601]
            results.append({
                "server_id": server_id,
                "error": f"Server with ID {server_id} not found"
            })
            continue

        # Consulta de agregación (promedios y máximos) [cite: 539-546]
        result = db.query(
            func.avg(Metric.cpu_usage).label("avg_cpu"),
            func.avg(Metric.memory_usage).label("avg_memory"),
            func.avg(Metric.disk_usage).label("avg_disk"),
            func.avg(Metric.temperature).label("avg_temperature"),
            func.max(Metric.cpu_usage).label("max_cpu"),
            func.max(Metric.temperature).label("max_temperature"),
            func.count(Metric.id).label("sample_count")
        ).filter(
            Metric.server_id == server_id,
            Metric.recorded_at >= since
        ).first()

        # Manejo de servidores sin datos en el rango de tiempo [cite: 600]
        if not result or result.sample_count == 0:
            results.append({
                "server_id": server.id,
                "hostname": server.hostname,
                "message": "No metrics in the requested time window."
            })
            continue

        # Construcción del objeto de respuesta para el servidor [cite: 555-562]
        results.append({
            "server_id": server.id,
            "hostname": server.hostname,
            "role": server.role,
            "datacenter_zone": server.datacenter_zone,
            "avg_cpu": round(result.avg_cpu, 2),
            "avg_memory": round(result.avg_memory, 2),
            "avg_disk": round(result.avg_disk, 2),
            "avg_temperature": round(result.avg_temperature, 2),
            "max_cpu": round(result.max_cpu, 2),
            "max_temperature": round(result.max_temperature, 2),
            "sample_count": result.sample_count,
            "hours_analyzed": hours
        })

    return results