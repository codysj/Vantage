import { useEffect, useState } from "react";

import { getWhaleAlerts } from "../api/client";
import type { WhaleAlertsResponse } from "../types";

export function WhaleAlertsPanel() {
  const [data, setData] = useState<WhaleAlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);

    getWhaleAlerts()
      .then((response) => {
        if (active) {
          setData(response);
          setError(null);
        }
      })
      .catch(() => {
        if (active) {
          setError("Unable to load whale alerts right now.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>Whale Alerts</h3>
      </div>
      {loading ? <div className="list-state">Loading whale-alert status...</div> : null}
      {error ? <div className="list-state error-state">{error}</div> : null}
      {!loading && !error && data ? (
        <div className="placeholder-card">
          <strong>{data.status}</strong>
          <p>{data.message}</p>
        </div>
      ) : null}
    </div>
  );
}
