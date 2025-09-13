
window.holdWorkerBtn = document.getElementById("worker-hold-btn");
window.holdQueueBtn = document.getElementById("queue-hold-btn");
window.scrapingDelay = document.getElementById("rate-value");

const preset50 = document.getElementById("preset-50");
const preset25 = document.getElementById("preset-25");
const preset0 = document.getElementById("preset-0");

const wipeWorkersDB = document.getElementById("wipe-workers");
const revokeAPIKeys = document.getElementById("revoke-keys");
const restartWorkers = document.getElementById("restart-workers");
const cleanupDB = document.getElementById("cleanup-db");

async function sendStateUpdate(state_type, value) {
  const apiUrl = "/actions"; // replace with your API endpoint

  try {
    const response = await fetch(apiUrl, {
      method: "POST",
      credentials: "include", // ensures cookies are sent
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ state_type, value }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    res = await response.json();
    showAlert(`${res["message"]}<br><br>
requested action: ${res["state_type"]}<br>
requested value: ${res["value"]}`, "info");
  } catch (err) {
    console.error("API call failed:", err);
  }
}

function showConfirmation(message) {
  return window.confirm(message);
}

document.addEventListener("DOMContentLoaded", () => {

  if (holdWorkerBtn) {
    holdWorkerBtn.addEventListener("click", () => {
      const isHeld = holdWorkerBtn.dataset.state === "held";

      if (isHeld) {
        sendStateUpdate("worker_hold", false);
      } else {
        // Hold
        const userConfirmed = showConfirmation("All scraping operations will be stopped immediately, this may cause a traffic anomaly, are you sure?");
        if (userConfirmed) {
          sendStateUpdate("worker_hold", true);
        }
      }
    });
  }

  if (holdQueueBtn) {
    holdQueueBtn.addEventListener("click", () => {
      const isHeld = holdQueueBtn.dataset.state === "held";
  
      if (isHeld) {
        sendStateUpdate("queue_hold", false);
      } else {
        const userConfirmed = showConfirmation("All scraping operations will be stopped gradually after workers started pulling new tasks from queue, this has less risk than holding worker but may still have some risk, are you sure?");
        if (userConfirmed) {
          sendStateUpdate("queue_hold", true);
        }
      }
    });
  }

  function updateScrapingRate(value) {
    if (scrapingDelay) {
     const userConfirmed = showConfirmation("This may cause scraping traffic to burst down in the set delay, are you sure?");
        if (userConfirmed) {
          sendStateUpdate("delay_per_batch", value);
        } 
    }
  }
  
  // Event listeners
  if (preset50) {
    preset50.addEventListener("click", () => updateScrapingRate(50));
  }
  if (preset25) {
    preset25.addEventListener("click", () => updateScrapingRate(25));
  }
  if (preset0) {
    preset0.addEventListener("click", () => updateScrapingRate(0));
  }

  if (revokeAPIKeys) {
    revokeAPIKeys.addEventListener("click", () => {
      const userConfirmed = showConfirmation("By revoking all admin cookies, all dashboard admin will need to re-login, no exception, continue?");
      if (userConfirmed) {
        sendStateUpdate("revoke_all_admin_cookies", true);
      }
    });
  }

  if (wipeWorkersDB) {
    wipeWorkersDB.addEventListener("click", () => {
      const userConfirmed = showConfirmation("By wiping the workers DB all workers would need to restart and re-register, continue?");1
      if (userConfirmed) {
        sendStateUpdate("wipe_worker_db", true);
      }
    });
  }

  if (restartWorkers) {
    restartWorkers.addEventListener("click", () => {
      const userConfirmed = showConfirmation("This will restart all worker, there maybe a bunch of abundant worker in db, continue?");1
      if (userConfirmed) {
        sendStateUpdate("restart_workers", true);
      }
    });
  }

  if (cleanupDB) {
    cleanupDB.addEventListener("click", () => {
      const userConfirmed = showConfirmation("Clean up workers db from idle worker, continue?");1
      if (userConfirmed) {
        sendStateUpdate("cleanup_db", true);
      }
    });
  }


});
