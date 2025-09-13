const url_generated = document.getElementById("total-url-generated");
const database_size_gb = document.getElementById("database-size-gb");
const database_size_mb = document.getElementById("database-size-mb");
const total_generated_count = document.getElementById("total-generated-count");
const queue_size = document.getElementById("queue-size");
const total_worker_of_worker = document.getElementById("total-worker");
const worker_pecentage = document.getElementById("percent-worker");
const not_found_percent = document.getElementById("notfound-percent");
const total_notfound_of_total = document.getElementById("notfound-of-total");
const page_per_minute = document.getElementById("pages-per-minute");
const scraped_pages_total = document.getElementById("scraped-pages-total");
const redirect_failed_percentage = document.getElementById("redirect-failed-percent");
const redirect_failed_of_total = document.getElementById("redirect-failed-of-total");
const last_updated = document.getElementById("last-updated");




function updateWorkerHoldUI(isHeld) {
  if (isHeld) {
    holdWorkerBtn.dataset.state = "held";
    holdWorkerBtn.innerHTML = `<i class="bi bi-arrow-counterclockwise me-2"></i> Lift Worker Hold`;
    holdWorkerBtn.classList.remove("btn-danger");
    holdWorkerBtn.classList.add("btn-success");
  } else {
    holdWorkerBtn.dataset.state = "released";
    holdWorkerBtn.innerHTML = `<i class="bi bi-pause-circle me-2"></i> Hold Workers`;
    holdWorkerBtn.classList.remove("btn-success");
    holdWorkerBtn.classList.add("btn-danger");
  }
}

function updateQueueHoldUI(isHeld) {
  if (isHeld) {
    holdQueueBtn.dataset.state = "held";
    holdQueueBtn.innerHTML = `<i class="bi bi-arrow-counterclockwise me-2"></i> Lift Queue Hold`;
    holdQueueBtn.classList.remove("btn-warning");
    holdQueueBtn.classList.add("btn-success");
  } else {
    holdQueueBtn.dataset.state = "released";
    holdQueueBtn.innerHTML = `<i class="bi bi-pause-circle me-2"></i> Hold Queue`;
    holdQueueBtn.classList.remove("btn-success");
    holdQueueBtn.classList.add("btn-warning");
  }
}

function updateScrapingRateUI(value) {
  scrapingDelay.textContent = `${value} sec/batch`;
}


function updateDashboard(data) {
  // Scraping stats
  url_generated.textContent = data.scraping_stats.urls_count.value;
  const sizeInMB = data.scraping_stats.data_size.value;
  const sizeInGB = sizeInMB / 1024; // Convert MB to GB
  
  database_size_gb.textContent = sizeInGB.toFixed(2) + " GB";
  database_size_mb.textContent = sizeInMB.toFixed(2) + " MB";
  queue_size.textContent = data.scraping_stats.queue_size.value;
  total_generated_count.textContent = data.scraping_stats.lastcount;

  // Worker stats
  total_worker_of_worker.textContent = data.stats_overview.active_workers.count + " / " + data.stats_overview.active_workers.total;
  worker_pecentage.textContent =
    ((data.stats_overview.active_workers.count / data.stats_overview.active_workers.total) * 100).toFixed(1) + "%";

  // Not found
  not_found_percent.textContent =
    ((data.stats_overview.url_not_found.count / data.stats_overview.url_not_found.total) * 100).toFixed(1) + "%";
  total_notfound_of_total.textContent =
    data.stats_overview.url_not_found.count + " / " + data.stats_overview.url_not_found.total;

  // Scraped pages
  scraped_pages_total.textContent = data.stats_overview.scraped_pages.value;
  // Assuming `change` means per minute (adjust if different)
  page_per_minute.textContent = data.stats_overview.scraped_pages.change + " pages/min";

  // Redirect failed
  redirect_failed_percentage.textContent =
    ((data.stats_overview.redirect_failed.count / data.stats_overview.redirect_failed.total) * 100).toFixed(1) + "%";
  redirect_failed_of_total.textContent =
    data.stats_overview.redirect_failed.count + " of " + data.stats_overview.redirect_failed.total;

  last_updated.textContent = data.last_updated

  updateWorkerHoldUI(data.hold_worker);
  updateQueueHoldUI(data.hold_queue);
  updateScrapingRateUI(data.batch_delay);
}

function renderWorkers(data) {
    const container = document.querySelector('.worker-grid');
    if (!container) return;

    // --- get current filter state ---
    const activeButton = document.querySelector('.filter-btn.active');
    const filterStatus = activeButton
        ? activeButton.textContent.trim().toLowerCase()
        : "all";

    // --- sort worker nodes by CPU usage (desc) ---
    const sortedWorkers = [...data.worker_nodes].sort((a, b) => {
        // if you want status to take priority:
        // const statusOrder = { active: 1, idle: 0 };
        // const diff = (statusOrder[b.status] || 0) - (statusOrder[a.status] || 0);
        // if (diff !== 0) return diff;

        return b.cpu_usage - a.cpu_usage;
    });

    // --- clear and render ---
    container.innerHTML = '';

    sortedWorkers.forEach(worker => {
        // --- apply filter ---
        if (
            filterStatus !== "all" &&
            worker.status.toLowerCase() !== filterStatus
        ) {
            return; // skip this worker
        }

        // Create card container
        const card = document.createElement('div');
        card.className = 'card compact-worker';

        // Card body
        const cardBody = document.createElement('div');
        cardBody.className = 'card-body p-2';

        // Header (ID + status)
        const header = document.createElement('div');
        header.className = 'd-flex justify-content-between align-items-center mb-1';
        const title = document.createElement('h6');
        title.className = 'card-title mb-0';
        title.textContent = worker.id;
        const badge = document.createElement('span');
        badge.className = `badge bg-${worker.status === 'active' ? 'success' : 'warning text-dark'}`;
        badge.textContent = worker.status.charAt(0).toUpperCase() + worker.status.slice(1);
        header.appendChild(title);
        header.appendChild(badge);

        // Worker info
        const info = document.createElement('p');
        info.className = 'text-muted mb-2';
        info.textContent = `${worker.ip} • ${worker.urls_onqueue} URLs • ${worker.disk_name}`;

        // Helper to create progress bars
        function createProgress(labelText, value, colorClass) {
            const containerDiv = document.createElement('div');
            containerDiv.className = 'resource-usage';

            const label = document.createElement('div');
            label.className = 'progress-label';
            label.textContent = `${labelText}: ${value}%`;

            const progress = document.createElement('div');
            progress.className = `progress ${colorClass}`;
            const bar = document.createElement('div');
            bar.className = 'progress-bar';
            bar.setAttribute('role', 'progressbar');
            bar.style.width = `${value}%`;
            bar.setAttribute('aria-valuenow', value);
            bar.setAttribute('aria-valuemin', 0);
            bar.setAttribute('aria-valuemax', 100);

            progress.appendChild(bar);
            containerDiv.appendChild(label);
            containerDiv.appendChild(progress);
            return containerDiv;
        }

        // Resource usage bars
        const cpuBar = createProgress('CPU', worker.cpu_usage, 'progress-cpu');
        const ramBar = createProgress('RAM', worker.ram_usage.percent, 'progress-ram');
        const diskBar = createProgress('Disk', worker.disk_usage.percent, 'progress-disk');

        // Last active
        const lastActive = document.createElement('p');
        lastActive.className = 'last-active text-muted mb-0';
        lastActive.textContent = `Active: ${worker.last_active}`;

        // Network bars
        function createNetworkBar(labelText, value, color) {
            const containerDiv = document.createElement('div');
            containerDiv.className = 'resource-usage';

            const label = document.createElement('div');
            label.className = 'progress-label';
            label.textContent = `${labelText}: ${formatBytes(value)}`;

            const barContainer = document.createElement('div');
            barContainer.className = 'bar-container';
            const barFill = document.createElement('div');
            barFill.className = 'bar-fill';
            barFill.style.width = `${Math.min(value / 1_000_000, 100)}%`;
            barFill.style.backgroundColor = color;

            barContainer.appendChild(barFill);
            containerDiv.appendChild(label);
            containerDiv.appendChild(barContainer);
            return containerDiv;
        }

        const networkInBar = createNetworkBar('Network In', worker.network_in, '#0dcaf0');
        const networkOutBar = createNetworkBar('Network Out', worker.network_out, '#fd7e14');

        // Assemble card body
        cardBody.appendChild(header);
        cardBody.appendChild(info);
        cardBody.appendChild(cpuBar);
        cardBody.appendChild(ramBar);
        cardBody.appendChild(diskBar);
        cardBody.appendChild(lastActive);
        cardBody.appendChild(networkInBar);
        cardBody.appendChild(networkOutBar);

        card.appendChild(cardBody);
        container.appendChild(card);
    });

    // Helper to format bytes
    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
    }
}



async function sendPostRequest() {
  try {
    const response = await fetch("/", {
      method: "POST",
      credentials: "include" // ensures cookies are sent
    });

    if (!response.ok) {
      throw new Error("Request failed with status " + response.status);
    }

    const result = await response.json().catch(() => null); // handle if no JSON body
    return result;
  } catch (error) {
    console.error("POST request error:", error);
    return null;
  }
}

// Hide overlay after first render
function hideInitialLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.transition = 'opacity 0.5s ease';
        overlay.style.opacity = 0;
        setTimeout(() => overlay.remove(), 500); // remove from DOM
    }
}

// Main first-load function
async function initialLoad() {
    try {
        const data = await sendPostRequest(); // your existing function
        updateDashboard(data);
        renderWorkers(data);
    } catch (err) {
        console.error('Failed to load dashboard:', err);
    } finally {
        hideInitialLoading();
        // Start recurring updates without overlay
        setInterval(async () => {
            try {
                const data = await sendPostRequest();
                updateDashboard(data);
                renderWorkers(data);
            } catch (err) {
                console.error('Failed to update dashboard:', err);
            }
        }, 1500);
    }
}

// Run initial load
initialLoad();
