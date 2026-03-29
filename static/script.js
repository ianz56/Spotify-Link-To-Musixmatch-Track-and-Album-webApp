// Highlight active navbar link
document.addEventListener("DOMContentLoaded", () => {
  const currentPath = window.location.pathname;

  const navLinks = document.querySelectorAll(".navbar a");

  console.log("Current Path:", currentPath);

  navLinks.forEach((link) => {
    // Check strict pathname match OR fallback to href comparison
    const isMatch =
      link.pathname === currentPath ||
      link.getAttribute("href") === currentPath;

    if (isMatch) {
      link.classList.add("active");
      // Auto-scroll the active link into view (center it horizontally)
      link.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  });

  // Language FAB Click Handler
  const fabBtn = document.querySelector(".lang-fab-btn");
  const dropdown = document.querySelector(".lang-fab-dropdown");

  if (fabBtn && dropdown) {
    fabBtn.addEventListener("click", (e) => {
      e.stopPropagation(); // Prevent click from bubbling to window
      dropdown.classList.toggle("show");
    });

    // Close dropdown when clicking outside
    window.addEventListener("click", (e) => {
      if (!fabBtn.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove("show");
      }
    });

    // Close dropdown when pressing Escape key
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        dropdown.classList.remove("show");
      }
    });
  }

  // Hide the note element if the current URL contains a query string
  const noteElement = document.querySelector(".note");
  if (noteElement) {
    noteElement.style.display = window.location.href.includes("?")
      ? "none"
      : "block";
  }
});

// Get the form and button elements
const form = document.querySelector("form");
const button = document.querySelector("#process_button");

// Add event listener for form submit
if (form && button) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();

    button.disabled = true;

    const loadingSpinner = document.querySelector("#loading");
    if (loadingSpinner) loadingSpinner.style.display = "block";

    const inputLinkInput = document.querySelector("#input_link");
    const inputLink = inputLinkInput ? inputLinkInput.value.trim() : "";

    if (!inputLink) {
      if (loadingSpinner) loadingSpinner.style.display = "none";
      button.disabled = false;
      return Promise.resolve(); // Resolve with a void value
    }

    if (
      window.location.pathname === "/abstrack" ||
      window.location.pathname === "/history"
    ) {
      window.location.href =
        window.location.href.split("?")[0] +
        "?id=" +
        encodeURIComponent(inputLink);
    } else {
      window.location.href =
        window.location.href.split("?")[0] +
        "?link=" +
        encodeURIComponent(inputLink);
    }
  });
}

// Get the how-to-use link and modal elements
const howToUseLink = document.querySelector("#how_to_use");
const howToUseModal = document.querySelector(".modal:not(#history-modal)");
const howToUseCloseBtn = howToUseModal
  ? howToUseModal.querySelector(".close")
  : null;

// Add click event listener for the how-to-use link
if (howToUseLink && howToUseModal) {
  howToUseLink.addEventListener("click", (event) => {
    event.preventDefault();
    howToUseModal.style.display = "block";
  });
}

// Add click event listener for the close button in the how-to-use modal
if (howToUseCloseBtn && howToUseModal) {
  howToUseCloseBtn.addEventListener("click", () => {
    howToUseModal.style.display = "none";
  });
}

// History modal elements
const historyModal = document.getElementById("history-modal");
const historyModalClose = document.getElementById("history-modal-close");
const historyModalBody = document.getElementById("history-modal-body");
const historyModalLoading = document.getElementById("history-modal-loading");
const historyModalFooter = document.getElementById("history-modal-footer");
const historyModalFullLink = document.getElementById("history-modal-full-link");

if (historyModalClose && historyModal) {
  historyModalClose.addEventListener("click", () => {
    historyModal.style.display = "none";
  });
}

// Close modals on outside click
window.addEventListener("click", (event) => {
  if (howToUseModal && event.target === howToUseModal) {
    howToUseModal.style.display = "none";
  }
  if (historyModal && event.target === historyModal) {
    historyModal.style.display = "none";
  }
});

/**
 * Open the history modal and fetch contribution data for a track.
 * @param {number} commontrackId - The Musixmatch commontrack_id
 */
function openHistoryModal(commontrackId) {
  if (!historyModal || !historyModalBody) return;

  // Show modal with loading state
  historyModal.style.display = "block";
  historyModalBody.innerHTML = "";
  historyModalLoading.style.display = "block";
  historyModalFooter.style.display = "none";

  // Set the full history link
  historyModalFullLink.href = "/history?id=" + commontrackId;

  fetch("/api/history/" + commontrackId)
    .then((res) => res.json())
    .then((data) => {
      historyModalLoading.style.display = "none";

      if (data.error) {
        historyModalBody.innerHTML =
          '<p style="text-align:center;color:var(--danger-color);">' +
          data.error +
          "</p>";
        return;
      }

      const groups = data.grouped_history || [];
      if (groups.length === 0) {
        historyModalBody.innerHTML =
          '<p style="text-align:center;">No contributions found.</p>';
        return;
      }

      // Summary line
      let html =
        '<p class="history-summary">' +
        "<strong>" +
        data.total_contributions +
        "</strong> contributions, <strong>" +
        groups.length +
        "</strong> contributors</p>";

      html += '<div class="history-timeline">';

      for (const group of groups) {
        const user = group.user || {};
        const entries = group.entries || [];
        const userName = user.user_name || "Unknown";
        const initial = userName.charAt(0).toUpperCase();

        html += '<div class="history-user-group">';
        html += '<div class="history-user-group-header">';
        html += '<div class="history-user">';

        // Avatar
        if (user.user_profile_photo) {
          html +=
            '<img src="' +
            user.user_profile_photo +
            '" alt="' +
            userName +
            '" class="history-avatar" loading="lazy" onerror="this.style.display=\'none\'" />';
        } else {
          html +=
            '<div class="history-avatar-placeholder">' + initial + "</div>";
        }

        html += '<div class="history-user-info">';
        html += '<span class="history-username">' + userName + "</span>";
        html += '<div class="history-user-badges">';

        // Rank badge
        if (user.rank_name) {
          const bgColor =
            user.rank_colors && user.rank_colors.rank_color_10
              ? user.rank_colors.rank_color_10
              : "f0f0f0";
          const textColor = user.rank_color || "888";
          const borderColor =
            user.rank_colors && user.rank_colors.rank_color_50
              ? user.rank_colors.rank_color_50
              : "ddd";
          html +=
            '<span class="history-rank-badge" style="background-color:#' +
            bgColor +
            ";color:#" +
            textColor +
            ";border-color:#" +
            borderColor +
            ';">';
          if (user.rank_image_url) {
            html +=
              '<img src="' +
              user.rank_image_url +
              '" alt="' +
              user.rank_name +
              '" class="history-rank-icon" loading="lazy" />';
          }
          html +=
            user.rank_name.charAt(0).toUpperCase() +
            user.rank_name.slice(1) +
            "</span>";
        }

        if (user.admin) {
          html +=
            '<span class="history-role-badge history-role-admin">Admin</span>';
        }
        if (user.moderator) {
          html +=
            '<span class="history-role-badge history-role-mod">Mod</span>';
        }

        html += "</div></div></div>"; // badges, user-info, user

        // Stats
        html += '<div class="history-user-stats">';
        html +=
          '<span class="history-contribution-count">' +
          entries.length +
          " contributions</span>";
        if (user.score) {
          html +=
            '<span class="history-score">★ ' +
            user.score.toLocaleString() +
            "</span>";
        }
        html += "</div>"; // user-stats

        html += "</div>"; // group-header

        // Entries
        html += '<div class="history-entries-list">';
        for (const entry of entries) {
          html += '<div class="history-entry">';
          html += '<div class="history-entry-body">';
          html +=
            '<span class="history-type-badge history-type-' +
            (entry.type_id || "unknown") +
            '">' +
            (entry.friendly_type_id || entry.type_id || "Unknown") +
            "</span>";
          if (entry.description && entry.description !== "") {
            html +=
              '<span class="history-description">' +
              entry.description +
              "</span>";
          }
          html += "</div>"; // entry-body

          html += '<div class="history-entry-footer">';
          if (entry.created_date) {
            html +=
              '<span class="history-date">' + entry.created_date + "</span>";
          }
          if (entry.app_id) {
            html += '<span class="history-app">' + entry.app_id + "</span>";
          }
          html += "</div>"; // entry-footer
          html += "</div>"; // entry
        }
        html += "</div>"; // entries-list
        html += "</div>"; // user-group
      }

      html += "</div>"; // timeline

      historyModalBody.innerHTML = html;
      historyModalFooter.style.display = "block";
    })
    .catch((err) => {
      historyModalLoading.style.display = "none";
      historyModalBody.innerHTML =
        '<p style="text-align:center;color:var(--danger-color);">Failed to load history: ' +
        err.message +
        "</p>";
    });
}

window.addEventListener("load", () => {
  const offlineDiv = document.getElementById("offline-div");

  function handleOnlineStatus() {
    const elements = document.querySelectorAll(
      "body > *:not(head):not(script):not(meta)",
    );

    if (offlineDiv) {
      if (navigator.onLine) {
        for (const element of elements) {
          element.style.removeProperty("display");
        }
        offlineDiv.style.display = "none";
      } else {
        for (const element of elements) {
          element.style.display = "none";
        }
        offlineDiv.style.display = "block";
      }
    }
  }

  handleOnlineStatus(); // Initial check

  // Standard removal after everything loads
  setTimeout(() => {
    document.body.classList.remove("preload");
  }, 100);

  // Listen for online/offline events
  window.addEventListener("online", () => {
    location.reload();
  });
  window.addEventListener("offline", handleOnlineStatus);
});

// Safety fallback: If window.load takes too long (e.g., slow ads/analytics), force show content
setTimeout(() => {
  document.body.classList.remove("preload");
}, 2000);
