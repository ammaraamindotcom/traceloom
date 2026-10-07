import { useMemo, useState } from "react";
import type { Activity } from "../api/activities";
import { activityDetail, formatEvent, formatTime } from "../lib/format";

type ActivityTableProps = {
  activities: Activity[];
};

export function ActivityTable({ activities }: ActivityTableProps) {
  const [eventFilter, setEventFilter] = useState("ALL"); const [search, setSearch] = useState("");
  const eventTypes = useMemo(() => [...new Set(activities.map(activity => activity.event_type))].sort(), [activities]);
  const filtered = activities.filter(activity => (eventFilter === "ALL" || activity.event_type === eventFilter) && `${activity.user_id} ${activity.event_type} ${JSON.stringify(activity.metadata)}`.toLowerCase().includes(search.toLowerCase()));
  if (activities.length === 0) {
    return <div className="empty-state"><strong>No activity telemetry yet</strong><p>Generate a scenario to create deterministic events for this user.</p></div>;
  }

  return (
    <div className="table-region"><div className="table-controls"><label>Event type<select value={eventFilter} onChange={event => setEventFilter(event.target.value)}><option value="ALL">All events</option>{eventTypes.map(type => <option key={type}>{type}</option>)}</select></label><label>Search telemetry<input value={search} onChange={event => setSearch(event.target.value)} placeholder="User, file, resource…" /></label></div><div className="table-scroll"><table>
      <thead>
        <tr>
          <th>Timestamp</th><th>User</th><th>Event type</th>
          <th>Metadata</th>
        </tr>
      </thead>
      <tbody>{filtered.map((activity) => {
          const isHighVolume =
            activity.event_type === "FILE_DOWNLOAD" && Number(activity.metadata.size_mb) >= 100;

          return (
          <tr key={activity.id} className={isHighVolume ? "high-volume" : undefined}><td className="mono">{formatTime(activity.timestamp)}</td><td>{activity.user_id}</td>
            <td>
              <strong className="mono">{formatEvent(activity.event_type)}</strong>
              {isHighVolume && <span className="volume-label">High-volume</span>}
            </td><td><span>{activityDetail(activity)}</span><details><summary>View metadata</summary><code>{JSON.stringify(activity.metadata, null, 2)}</code></details></td>
          </tr>
          );
        })}
      </tbody></table></div>{filtered.length === 0 && <div className="empty-state"><strong>No matching telemetry</strong><p>Adjust the activity filters to view recorded events.</p></div>}</div>
  );
}
