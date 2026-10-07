"""Rule-based anomaly signal detection; no inference model is involved."""

from datetime import timedelta

from app.models.activity import Activity
from app.schemas import AnomalySignal, BehavioralBaseline


DOWNLOAD_EVENTS_FOR_FOLLOW_UP = 3
FOLLOW_UP_WINDOW = timedelta(minutes=30)


def _download_size_mb(activity: Activity) -> float:
    value = activity.metadata_.get("size_mb", 0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def _recent_downloads_before(activity: Activity, activities: list[Activity]) -> list[Activity]:
    return [
        candidate
        for candidate in activities
        if candidate.event_type == "FILE_DOWNLOAD"
        and timedelta(0) <= activity.timestamp - candidate.timestamp <= FOLLOW_UP_WINDOW
    ]


def detect_anomaly_signals(
    activities: list[Activity], baseline: BehavioralBaseline
) -> list[AnomalySignal]:
    ordered = sorted(activities, key=lambda item: item.timestamp)
    downloads = [activity for activity in ordered if activity.event_type == "FILE_DOWNLOAD"]
    downloaded_mb = sum(_download_size_mb(activity) for activity in downloads)
    signals: list[AnomalySignal] = []

    download_threshold = max(5, baseline.average_file_downloads * 2)
    if len(downloads) >= download_threshold:
        signals.append(
            AnomalySignal(
                type="HIGH_DOWNLOAD_VOLUME",
                description="User downloaded significantly more files than their historical baseline.",
                severity="high",
                evidence={"downloads": len(downloads), "baseline_average": baseline.average_file_downloads, "threshold": download_threshold},
            )
        )

    data_threshold = max(100, baseline.average_downloaded_data_mb * 2)
    if downloaded_mb >= data_threshold:
        signals.append(
            AnomalySignal(
                type="LARGE_DATA_VOLUME",
                description="Cumulative downloaded data is significantly above the historical baseline.",
                severity="high",
                evidence={"downloaded_data_mb": downloaded_mb, "baseline_average_mb": baseline.average_downloaded_data_mb, "threshold_mb": data_threshold},
            )
        )

    archives = [activity for activity in ordered if activity.event_type == "ARCHIVE_CREATED"]
    archive_after_download = next(
        (archive for archive in archives if len(_recent_downloads_before(archive, ordered)) >= DOWNLOAD_EVENTS_FOR_FOLLOW_UP),
        None,
    )
    if archive_after_download is not None:
        signals.append(
            AnomalySignal(
                type="ARCHIVE_AFTER_DOWNLOADS",
                description="An archive was created shortly after a high-volume download sequence.",
                severity="medium",
                evidence={"archive_timestamp": archive_after_download.timestamp.isoformat(), "downloads_in_previous_30_minutes": len(_recent_downloads_before(archive_after_download, ordered))},
            )
        )

    uploads = [activity for activity in ordered if activity.event_type == "EXTERNAL_UPLOAD"]
    upload_after_download = next(
        (upload for upload in uploads if len(_recent_downloads_before(upload, ordered)) >= DOWNLOAD_EVENTS_FOR_FOLLOW_UP),
        None,
    )
    if upload_after_download is not None:
        signals.append(
            AnomalySignal(
                type="EXTERNAL_UPLOAD_AFTER_DOWNLOADS",
                description="An external upload occurred shortly after significant file downloads.",
                severity="high",
                evidence={"upload_timestamp": upload_after_download.timestamp.isoformat(), "downloads_in_previous_30_minutes": len(_recent_downloads_before(upload_after_download, ordered))},
            )
        )

    archive_index = next((index for index, activity in enumerate(ordered) if activity.event_type == "ARCHIVE_CREATED"), None)
    if archive_index is not None and any(activity.event_type == "EXTERNAL_UPLOAD" for activity in ordered[archive_index + 1:]) and sum(activity.event_type == "FILE_DOWNLOAD" for activity in ordered[:archive_index]) >= DOWNLOAD_EVENTS_FOR_FOLLOW_UP:
        signals.append(
            AnomalySignal(
                type="UNUSUAL_EVENT_SEQUENCE",
                description="A download sequence was followed by archive creation and an external upload.",
                severity="medium",
                evidence={"sequence": ["FILE_DOWNLOAD", "ARCHIVE_CREATED", "EXTERNAL_UPLOAD"]},
            )
        )

    rare_event_types = sorted(
        {
            activity.event_type
            for activity in ordered
            if activity.event_type not in {"LOGIN", "LOGOUT"}
            and baseline.event_type_counts.get(activity.event_type, 0) == 0
        }
    )
    if rare_event_types:
        signals.append(
            AnomalySignal(
                type="OFF_PATTERN_ACTIVITY",
                description="The session includes event types absent from the user's historical activity.",
                severity="low",
                evidence={"absent_from_baseline": rare_event_types},
            )
        )

    return signals
