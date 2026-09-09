// KSHAN V2 Global Utility Functions

function getCsrfToken() {
  const name = 'csrftoken';
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function authFetch(url, options = {}) {
  options.headers = options.headers || {};
  const token = getCsrfToken();
  if (token) {
    if (options.headers instanceof Headers) {
      options.headers.set('X-CSRFToken', token);
    } else {
      options.headers['X-CSRFToken'] = token;
    }
  }
  return fetch(url, options);
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "kshan-toast";
  
  let iconName = "info";
  if (type === "success") iconName = "check-circle";
  if (type === "danger") iconName = "alert-circle";
  if (type === "warning") iconName = "alert-triangle";

  toast.innerHTML = `
    <i data-lucide="${iconName}" style="width: 16px; height: 16px; color: var(--gold);"></i>
    <span>${message}</span>
  `;

  container.appendChild(toast);
  if (window.lucide) {
    lucide.createIcons();
  }

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(12px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
