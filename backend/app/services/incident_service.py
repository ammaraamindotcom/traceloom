"""Dynamic, deterministic incident investigation projections."""

from datetime import datetime, timedelta, timezone

from app.models.activity import Activity
from app.schemas import (
    ActivityRead,
    AnalysisResult,
    EvidenceGraph,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    Incident,
    IncidentInvestigationResult,
    TimelineEntry,
)
from app.services.analysis_service import analyze_user_activities


EVENT_DESCRIPTIONS = {
    "LOGIN": "User login activity",
    "LOGOUT": "User logout activity",
    "FILE_ACCESS": "File access activity",
    "FILE_DOWNLOAD": "File download activity",
    "FILE_UPLOAD": "File upload activity",
    "REPOSITORY_ACCESS": "Repository access activity",
    "ARCHIVE_CREATED": "Archive creation activity",
    "EXTERNAL_UPLOAD": "External upload activity",
    "PASSWORD_CHANGE": "Password change activity",
}


def _activity_node_id(activity: ActivityRead) -> str:
    return f"activity:{activity.id}"


def _signal_node_id(signal_type: str) -> str:
    return f"signal:{signal_type}"


def _downloads_before(activity: ActivityRead, activities: list[ActivityRead]) -> list[ActivityRead]:
    return [
        candidate
        for candidate in activities
        if candidate.event_type == "FILE_DOWNLOAD"
        and timedelta(0) <= activity.timestamp - candidate.timestamp <= timedelta(minutes=30)
    ]


def _signal_activity_ids(signal_type: str, activities: list[ActivityRead], evidence: dict) -> set[str]:
    """Map each deterministic rule to precisely the telemetry it evaluates."""
    downloads = [activity for activity in activities if activity.event_type == "FILE_DOWNLOAD"]
    if signal_type in {"HIGH_DOWNLOAD_VOLUME", "LARGE_DATA_VOLUME"}:
        return {_activity_node_id(activity) for activity in downloads}
    if signal_type == "ARCHIVE_AFTER_DOWNLOADS":
        archives = [activity for activity in activities if activity.event_type == "ARCHIVE_CREATED"]
        return {
            _activity_node_id(activity)
            for archive in archives
            for activity in [archive, *_downloads_before(archive, activities)]
        }
    if signal_type == "EXTERNAL_UPLOAD_AFTER_DOWNLOADS":
        uploads = [activity for activity in activities if activity.event_type == "EXTERNAL_UPLOAD"]
        return {
            _activity_node_id(activity)
            for upload in uploads
            for activity in [upload, *_downloads_before(upload, activities)]
        }
    if signal_type == "UNUSUAL_EVENT_SEQUENCE":
        archive_positions = [index for index, activity in enumerate(activities) if activity.event_type == "ARCHIVE_CREATED"]
        if not archive_positions:
            return set()
        archive_index = archive_positions[0]
        sequence_activities = [
            *[activity for activity in activities[:archive_index] if activity.event_type == "FILE_DOWNLOAD"],
            activities[archive_index],
            *[activity for activity in activities[archive_index + 1:] if activity.event_type == "EXTERNAL_UPLOAD"],
        ]
        return {_activity_node_id(activity) for activity in sequence_activities}
    if signal_type == "OFF_PATTERN_ACTIVITY":
        off_pattern_types = set(evidence.get("absent_from_baseline", []))
        return {_activity_node_id(activity) for activity in activities if activity.event_type in off_pattern_types}
    return set()


def build_timeline(activities: list[ActivityRead]) -> list[TimelineEntry]:
    ordered = sorted(activities, key=lambda activity: activity.timestamp)
    timeline: list[TimelineEntry] = []
    for index, activity in enumerate(ordered):
        prior = ordered[:index]
        transition: str | None = None
        if activity.event_type == "ARCHIVE_CREATED" and len(_downloads_before(activity, ordered)) >= 3:
            transition = "High-volume downloads were followed by archive creation."
        elif activity.event_type == "EXTERNAL_UPLOAD":
            recent_archives = [item for item in prior if item.event_type == "ARCHIVE_CREATED" and activity.timestamp - item.timestamp <= timedelta(minutes=30)]
            if recent_archives:
                transition = "Archive creation was followed by an external upload."
        timeline.append(
            TimelineEntry(
                activity_id=activity.id,
                timestamp=activity.timestamp,
                event_type=activity.event_type,
                description=EVENT_DESCRIPTIONS.get(activity.event_type, activity.event_type.replace("_", " ").title() + " activity"),
                transition_explanation=transition,
            )
        )
    return timeline


def build_evidence_graph(analysis: AnalysisResult, incident: Incident) -> EvidenceGraph:
    activities = sorted(analysis.recent_activities, key=lambda activity: activity.timestamp)
    user_node_id = f"user:{analysis.user_id}"
    incident_node_id = f"incident:{incident.incident_id}"
    nodes = [
        EvidenceGraphNode(id=user_node_id, type="USER", label=analysis.user_id),
        EvidenceGraphNode(id=incident_node_id, type="INCIDENT", label=incident.incident_id),
    ]
    edges: list[EvidenceGraphEdge] = []

    for index, activity in enumerate(activities):
        activity_node_id = _activity_node_id(activity)
        nodes.append(
            EvidenceGraphNode(
                id=activity_node_id,
                type="ACTIVITY",
                label=activity.event_type,
                data={"activity_id": str(activity.id), "timestamp": activity.timestamp.isoformat()},
            )
        )
        edges.append(EvidenceGraphEdge(source=user_node_id, target=activity_node_id, relationship="performed"))
        if index:
            edges.append(
                EvidenceGraphEdge(
                    source=_activity_node_id(activities[index - 1]),
                    target=activity_node_id,
                    relationship="followed_by",
                )
            )

    for signal in analysis.signals:
        signal_node_id = _signal_node_id(signal.type)
        nodes.append(EvidenceGraphNode(id=signal_node_id, type="SIGNAL", label=signal.type))
        for activity_node_id in _signal_activity_ids(signal.type, activities, signal.evidence):
            edges.append(EvidenceGraphEdge(source=activity_node_id, target=signal_node_id, relationship="supports"))
        edges.append(EvidenceGraphEdge(source=signal_node_id, target=incident_node_id, relationship="contributes_to"))

    return EvidenceGraph(nodes=nodes, edges=edges)


def investigate_user_activities(user_id: str, activities: list[Activity]) -> IncidentInvestigationResult:
    """Create an incident only from a high deterministic-risk latest session."""
    analysis = analyze_user_activities(user_id, activities)
    if analysis.risk_level != "high":
        return IncidentInvestigationResult(
            incident=None,
            timeline=[],
            signals=analysis.signals,
            graph=EvidenceGraph(nodes=[], edges=[]),
            intent=None,
            deterministic_analysis=analysis,
        )

    ordered_activities = sorted(analysis.recent_activities, key=lambda activity: activity.timestamp)
    incident = Incident(
        incident_id=f"incident-{user_id}",
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
        start_time=ordered_activities[0].timestamp,
        end_time=ordered_activities[-1].timestamp,
        risk_level=analysis.risk_level,
        risk_score=analysis.risk_score,
        activity_ids=[activity.id for activity in ordered_activities],
        signal_types=[signal.type for signal in analysis.signals],
    )
    return IncidentInvestigationResult(
        incident=incident,
        timeline=build_timeline(ordered_activities),
        signals=analysis.signals,
        graph=build_evidence_graph(analysis, incident),
        intent=None,
        deterministic_analysis=analysis,
    )
