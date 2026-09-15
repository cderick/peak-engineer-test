/* Page timer.
 *
 * Wraps fetch and reports how long the page took to go quiet: from the first
 * request of a run until the last one finishes and nothing new starts for a
 * moment. That last part matters — if one request triggers another, both are in
 * the same run, and the panel counts them both.
 *
 * It shows three numbers and they measure different things:
 *
 *   settled   wall clock from first request to quiet. What the member waits.
 *             Ends when fetch resolves with response headers; excludes body
 *             parsing and rendering.
 *   server    the sum of X-Response-Time-Ms across the run, which is the part
 *             server middleware measures. Tests measure complete requests.
 *   requests  how many round trips the screen cost.
 *
 * This is a development aid, not a test. It is not reproducible enough to gate
 * anything on, and it is only ever as honest as the page is — if you fetch
 * something later, on scroll or on a timer, it lands in a different run.
 */

(function () {
  const QUIET_MS = 250;

  const state = { inflight: 0, started: null, ended: null, calls: [], timer: null };

  const panel = document.createElement("div");
  panel.className = "perf";
  panel.hidden = true;
  panel.innerHTML = `
    <div class="perf-head">
      <span class="perf-total"></span>
      <button type="button" class="perf-toggle" aria-expanded="false">details</button>
    </div>
    <dl class="perf-summary">
      <dt>server</dt><dd class="perf-server"></dd>
      <dt>requests</dt><dd class="perf-count"></dd>
      <dt>transferred</dt><dd class="perf-bytes"></dd>
    </dl>
    <ol class="perf-calls" hidden></ol>
    <div class="perf-chart"><canvas aria-label="Recent request batches, milliseconds" role="img"></canvas></div>
  `;
  document.body.append(panel);

  const chart = typeof Chart === "undefined" ? null : new Chart(panel.querySelector("canvas"), {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { label: "Elapsed ms", data: [], borderColor: "#386b9b", pointRadius: 2 },
        { label: "Server sum ms", data: [], borderColor: "#67865b", pointRadius: 2 },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true } },
      plugins: { legend: { labels: { boxWidth: 12 } } },
    },
  });
  let batch = 0;

  const calls = panel.querySelector(".perf-calls");
  panel.querySelector(".perf-toggle").addEventListener("click", (event) => {
    const open = calls.hidden;
    calls.hidden = !open;
    event.target.setAttribute("aria-expanded", String(open));
  });

  function report() {
    // Measured to the last response, not to the end of the quiet window.
    const settled = state.ended - state.started;
    const server = state.calls.reduce((total, c) => total + (c.server || 0), 0);
    const bytes = state.calls.reduce((total, c) => total + (c.bytes || 0), 0);

    panel.hidden = false;
    panel.querySelector(".perf-total").textContent = `${settled.toFixed(0)} ms to settle`;

    const serverCell = panel.querySelector(".perf-server");
    serverCell.textContent = `${server.toFixed(1)} ms`;
    if (chart) {
      chart.data.labels.push(String(++batch));
      chart.data.datasets[0].data.push(settled);
      chart.data.datasets[1].data.push(server);
      if (chart.data.labels.length > 30) {
        chart.data.labels.shift();
        chart.data.datasets.forEach((series) => series.data.shift());
      }
      chart.update();
    }

    panel.querySelector(".perf-count").textContent = String(state.calls.length);
    panel.querySelector(".perf-bytes").textContent = `${(bytes / 1024).toFixed(1)} KB`;

    calls.replaceChildren();
    for (const call of state.calls) {
      const row = document.createElement("li");
      const path = document.createElement("span");
      path.className = "perf-path";
      path.textContent = call.path;
      const timing = document.createElement("span");
      timing.className = "perf-timing";
      timing.textContent = `${call.server != null ? call.server.toFixed(1) : "?"} / ${call.wall.toFixed(0)} ms`;
      row.append(path, timing);
      calls.append(row);
    }

    state.started = null;
    state.ended = null;
    state.calls = [];
  }

  const original = window.fetch;
  window.fetch = async function (...args) {
    const url = typeof args[0] === "string" ? args[0] : args[0].url;
    const tracked = url.includes("/api/");

    if (tracked) {
      if (state.timer) {
        clearTimeout(state.timer);
        state.timer = null;
      }
      if (state.started === null) {
        state.started = performance.now();
        state.calls = [];
      }
      state.inflight += 1;
    }

    const began = performance.now();
    try {
      const response = await original.apply(this, args);
      if (tracked) {
        const header = response.headers.get("X-Response-Time-Ms");
        const length = response.headers.get("Content-Length");
        state.calls.push({
          path: new URL(url, location.origin).pathname,
          wall: performance.now() - began,
          server: header ? Number(header) : null,
          bytes: length ? Number(length) : 0,
        });
      }
      return response;
    } finally {
      if (tracked) {
        state.inflight -= 1;
        if (state.inflight === 0) {
          state.ended = performance.now();
          state.timer = setTimeout(report, QUIET_MS);
        }
      }
    }
  };
})();
