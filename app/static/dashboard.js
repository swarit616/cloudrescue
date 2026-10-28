"use strict";

const $ = (id) => document.getElementById(id);

const formatTime = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
};

async function getJSON(path, acceptedStatuses = [200]) {
  const response = await fetch(path, { cache: "no-store" });
  if (!acceptedStatuses.includes(response.status)) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return response.json();
}

function setValue(id, value, className = "") {
  const element = $(id);
  element.textContent = String(value);
  if (className) element.className = className;
}

function renderIncidents(data) {
  setValue("open-count", data.open_count);
  setValue("total-count", data.count);
  setValue("incident-summary", `${data.count} total`);

  const tbody = $("incident-rows");
  tbody.replaceChildren();

  if (!data.incidents.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "empty-state";
    cell.textContent = "No simulated incidents recorded yet.";
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }

  const incidents = [...data.incidents].sort(
    (a, b) => b.id - a.id
  );

  for (const incident of incidents) {
    const row = document.createElement("tr");

    const cells = [
      `#${incident.id}`,
      incident.reason,
      incident.severity,
      incident.status,
      formatTime(incident.started_at),
      formatTime(incident.resolved_at)
    ];

    cells.forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value ?? "—";

      if (index === 2) cell.className = `severity-${incident.severity}`;
      if (index === 3) cell.className = `status-${incident.status}`;

      row.appendChild(cell);
    });

    tbody.appendChild(row);
  }
}


function renderMonitoring(data) {
  setValue("monitoring-health", "Connected", "stat-value good");
  setValue("monitoring-open", data.open_count);
  setValue("monitoring-resolved", data.resolved_count);
  setValue("monitoring-total", data.total_count);
  setValue("monitoring-summary", `${data.count} displayed`);

  const tbody = $("monitoring-rows");
  tbody.replaceChildren();

  if (!data.incidents.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.className = "empty-state";
    cell.textContent = "No monitoring incidents received in this application process.";
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }

  for (const incident of data.incidents) {
    const row = document.createElement("tr");

    const cells = [
      incident.alertname,
      incident.reason,
      incident.severity,
      incident.source,
      incident.status,
      formatTime(incident.alert_starts_at || incident.started_at),
      formatTime(incident.alert_ends_at || incident.resolved_at)
    ];

    cells.forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value ?? "—";

      if (index === 2) {
        const severity = String(incident.severity).toLowerCase();
        if (["critical", "warning", "info"].includes(severity)) {
          cell.classList.add(`severity-${severity}`);
        }
      }

      if (index === 4 && ["open", "resolved"].includes(incident.status)) {
        cell.classList.add(`status-${incident.status}`);
      }

      row.appendChild(cell);
    });

    tbody.appendChild(row);
  }
}

function renderStatus(data) {
  const state = data.simulated_service.state;

  setValue(
    "service-state",
    state === "healthy" ? "Healthy" : "Failed",
    `stat-value ${state === "healthy" ? "good" : "bad"}`
  );

  setValue("environment", data.environment);
  setValue("version", data.version);
  setValue("state-since", formatTime(data.simulated_service.since));
  setValue("active-incident", data.simulated_service.open_incident_id ?? "None");
  setValue("runtime-badge", data.runtime_mode);

  setValue(
    "aws-description",
    data.aws.note ||
      "AWS integration is not implemented. No AWS API calls are made."
  );
}

let refreshing = false;

async function refreshDashboard() {
  if (refreshing) return;

  refreshing = true;
  $("refresh-button").disabled = true;

  try {
    const results = await Promise.allSettled([
      getJSON("/health"),
      getJSON("/api/status", [200, 503]),
      getJSON("/api/incidents"),
      getJSON("/api/monitoring/incidents")
    ]);

    const [health, status, incidents, monitoring] = results;
    const failures = [];

    if (health.status === "fulfilled") {
      setValue(
        "api-health",
        health.value.status === "ok" ? "Online" : "Unknown",
        `stat-value ${health.value.status === "ok" ? "good" : "bad"}`
      );
    } else {
      setValue("api-health", "Unavailable", "stat-value bad");
      failures.push("health");
    }

    if (status.status === "fulfilled") {
      renderStatus(status.value);
    } else {
      setValue("service-state", "Unavailable", "stat-value bad");
      failures.push("status");
    }

    if (incidents.status === "fulfilled") {
      renderIncidents(incidents.value);
    } else {
      setValue("open-count", "—");
      setValue("total-count", "—");
      failures.push("incidents");
    }

    if (monitoring.status === "fulfilled") {
      renderMonitoring(monitoring.value);
    } else {
      setValue("monitoring-health", "Unavailable", "stat-value bad");
      setValue("monitoring-open", "—");
      setValue("monitoring-resolved", "—");
      setValue("monitoring-total", "—");
      setValue("monitoring-summary", "Unavailable");
      failures.push("monitoring");
    }

    setValue("last-updated", new Date().toLocaleTimeString());

    setValue(
      "connection-message",
      failures.length
        ? `Unable to load: ${failures.join(", ")}. Retrying automatically.`
        : "Connected • Monitoring and simulation data are separate and stored in memory."
    );
  } finally {
    refreshing = false;
    $("refresh-button").disabled = false;
  }
}

$("refresh-button").addEventListener("click", refreshDashboard);

refreshDashboard();
setInterval(refreshDashboard, 15000);
