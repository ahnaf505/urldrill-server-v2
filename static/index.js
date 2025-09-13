document.addEventListener("DOMContentLoaded", () => {
   const logoutBtn = document.querySelector("#logout-btn");
   function clearAllCookies() {
       document.cookie.split(";").forEach(cookie => {
           const eqPos = cookie.indexOf("=");
           const name = eqPos > -1 ? cookie.substr(0, eqPos) : cookie;
           document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
       });
   }
   if (logoutBtn) {
       logoutBtn.addEventListener("click", async (e) => {
           e.preventDefault(); // Prevent navigating anywhere
           // Clear all cookies
           clearAllCookies();
           try {
               // Send logout request to server
               const response = await fetch("/logout", {
                   method: "POST",
                   credentials: "same-origin"
               });
               // Always redirect to home page
               window.location.href = "/";
           } catch (err) {
               console.error("Logout error:", err);
               alert("An error occurred. Check console.");
           }
       });
   }
});

function showAlert(message, type = "info") {
  // Create overlay
  const overlay = document.createElement("div");
  overlay.style.position = "fixed";
  overlay.style.top = "0";
  overlay.style.left = "0";
  overlay.style.width = "100%";
  overlay.style.height = "100%";
  overlay.style.backgroundColor = "rgba(0,0,0,0.5)";
  overlay.style.zIndex = "1055";
  overlay.style.display = "flex";
  overlay.style.alignItems = "center";
  overlay.style.justifyContent = "center";

  // Create alert box
  const alertDiv = document.createElement("div");
  alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
  alertDiv.role = "alert";
  alertDiv.style.maxWidth = "600px";
  alertDiv.style.width = "80%";
  alertDiv.style.fontSize = "1.5rem";
  alertDiv.style.textAlign = "center";
  alertDiv.innerHTML = `
    <div>${message}</div>
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  `;

  // Close handler to also remove overlay
  alertDiv.querySelector(".btn-close").addEventListener("click", () => {
    overlay.remove();
  });

  overlay.appendChild(alertDiv);
  document.body.appendChild(overlay);

  // Auto-dismiss after 5s
  setTimeout(() => {
    overlay.remove();
  }, 25000);
}
window.showAlert = showAlert;

let sortTimeout = null;



// Sort worker cards by CPU usage (desc)
function sortWorkerCards() {
    const container = document.querySelector(".worker-grid");
    if (!container) return;

    const cards = Array.from(container.querySelectorAll(".card"));

    cards.sort((a, b) => {
        const cpuA = parseInt(
            a.querySelector(".progress-cpu .progress-bar")
                ?.getAttribute("aria-valuenow") || "0"
        );
        const cpuB = parseInt(
            b.querySelector(".progress-cpu .progress-bar")
                ?.getAttribute("aria-valuenow") || "0"
        );
        return cpuB - cpuA;
    });

    cards.forEach((card) => container.appendChild(card));
}

// Apply current filter and then sort
function applyFilterAndSort() {
    const activeButton = document.querySelector(".filter-btn.active");
    const status = activeButton
        ? activeButton.textContent.trim().toLowerCase()
        : "all";

    const cards = document.querySelectorAll(".worker-grid .card");
    cards.forEach((card) => {
        const badge = card.querySelector(".badge");
        const cardStatus = badge.textContent.trim().toLowerCase();
        card.style.display =
            status === "all" || cardStatus === status ? "block" : "none";
    });

    sortWorkerCards();
}

// Initialize filtering & sorting system
function initWorkerCardSystem() {
    applyFilterAndSort();

    // Filter button functionality
    const filterButtons = document.querySelectorAll(".filter-btn");
    filterButtons.forEach((button) => {
        button.addEventListener("click", function () {
            filterButtons.forEach((btn) => btn.classList.remove("active"));
            this.classList.add("active");

            applyFilterAndSort();
        });
    });

    // Watch for DOM changes (cards added/removed or CPU updated)
    const container = document.querySelector(".worker-grid");
    if (!container) return;

    const observer = new MutationObserver(() => {
        // Debounce to avoid infinite loop
        clearTimeout(sortTimeout);
        sortTimeout = setTimeout(() => {
            applyFilterAndSort();
        }, 200);
    });

    observer.observe(container, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["aria-valuenow", "class"], // catch CPU + status changes
    });
}

// Run once DOM is ready
document.addEventListener("DOMContentLoaded", initWorkerCardSystem);
