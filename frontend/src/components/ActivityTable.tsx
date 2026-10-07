import type { Activity } from "../api/activities";

type ActivityTableProps = {
  activities: Activity[];
};

export function ActivityTable({ activities }: ActivityTableProps) {
  if (activities.length === 0) {
    return <p>No activities recorded yet.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>User</th>
          <th>Event type</th>
          <th>Timestamp</th>
          <th>Metadata</th>
        </tr>
      </thead>
      <tbody>
        {activities.map((activity) => {
          const isHighVolume =
            activity.event_type === "FILE_DOWNLOAD" && Number(activity.metadata.size_mb) >= 100;

          return (
          <tr key={activity.id} className={isHighVolume ? "high-volume" : undefined}>
            <td>{activity.user_id}</td>
            <td>
              {activity.event_type}
              {isHighVolume && <span className="volume-label">High-volume</span>}
            </td>
            <td>{new Date(activity.timestamp).toLocaleString()}</td>
            <td><code>{JSON.stringify(activity.metadata)}</code></td>
          </tr>
          );
        })}
      </tbody>
    </table>
  );
}
