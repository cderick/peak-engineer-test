const el = (id) => document.getElementById(id);

const BAND_ORDER = ["optimal", "good", "improve"];
const BAND_LABEL = { optimal: "Optimal", good: "Good", improve: "Needs work" };

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return body;
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/* The scale spans the full width of every band the marker defines. Bands are
   laid out in value order, not in optimal/good/improve order, so that the tick
   sits in a place that means something. */
function scaleFor(ranges) {
  const bands = BAND_ORDER.map((band) => ({
    band,
    min: ranges[band].min,
    max: ranges[band].max,
  })).sort((a, b) => a.min - b.min);

  const low = bands[0].min;
  const high = bands[bands.length - 1].max;
  const span = high - low || 1;

  return { bands, low, high, span };
}

function renderMarker(result) {
  const { bands, low, high, span } = scaleFor(result.ranges);
  const offset = Math.min(100, Math.max(0, ((result.value - low) / span) * 100));

  const node = document.createElement("article");
  node.className = "marker";
  node.innerHTML = `
    <div class="marker-head">
      <span class="marker-name"></span>
      <span>
        <span class="marker-value"></span><span class="marker-unit"></span>
        <span class="marker-status status-${result.status}"></span>
      </span>
    </div>
    <div class="scale-wrap">
      <div class="scale">
        ${bands
          .map(
            (b) =>
              `<div class="band band-${b.band}" style="width:${
                ((b.max - b.min) / span) * 100
              }%"></div>`
          )
          .join("")}
      </div>
      <div class="tick" style="left:${offset}%"></div>
    </div>
    <div class="scale-labels"><span class="low"></span><span class="high"></span></div>
  `;

  node.querySelector(".marker-name").textContent = result.name;
  node.querySelector(".marker-value").textContent = result.value;
  node.querySelector(".marker-unit").textContent = result.unit;
  node.querySelector(".marker-status").textContent =
    BAND_LABEL[result.status] ?? result.status;
  node.querySelector(".low").textContent = low;
  node.querySelector(".high").textContent = high;
  return node;
}

function renderResults(results) {
  const root = el("results");
  root.replaceChildren();

  if (results.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No results yet. They appear here after your first draw.";
    root.append(empty);
    return;
  }

  let category = null;
  for (const result of results) {
    if (result.category !== category) {
      category = result.category;
      const heading = document.createElement("h2");
      heading.className = "category";
      heading.textContent = category;
      root.append(heading);
    }
    root.append(renderMarker(result));
  }
}

async function showDashboard(user) {
  el("signin").hidden = true;
  el("dashboard").hidden = false;
  el("whoami").textContent = user.name;

  const { data, meta } = await api("/api/home");
  renderResults(data.results);

  const latest = meta.tested_at || data.results[0]?.tested_at;
  el("drawn").textContent = latest ? `Drawn ${formatDate(latest)}` : "";
}

function showSignIn(message) {
  el("dashboard").hidden = true;
  el("signin").hidden = false;
  const error = el("signin-error");
  error.hidden = !message;
  error.textContent = message || "";
}

el("signin-button").addEventListener("click", async () => {
  const email = el("email").value.trim();
  if (!email) {
    showSignIn("Enter an email address to sign in.");
    return;
  }
  try {
    const { data } = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    await showDashboard(data.user);
  } catch (err) {
    showSignIn(err.message);
  }
});

el("email").addEventListener("keydown", (event) => {
  if (event.key === "Enter") el("signin-button").click();
});

el("signout-button").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  el("email").value = "";
  showSignIn();
});

(async function start() {
  try {
    const { data } = await api("/api/me");
    await showDashboard(data.user);
  } catch {
    showSignIn();
  }
})();
