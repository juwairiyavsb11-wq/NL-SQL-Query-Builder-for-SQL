/**
 * AskDB — UI Module
 * Theme management, toast notifications, modals, and microinteractions.
 */

const UI = {
  // ── Theme ──
  initTheme() {
    const saved = localStorage.getItem('askdb-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    this.updateThemeButton(saved);
  },

  toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('askdb-theme', next);
    this.updateThemeButton(next);

    // Sync theme selection cards in profile settings if present
    const lightCard = document.getElementById('themeSelectLight');
    const darkCard = document.getElementById('themeSelectDark');
    if (lightCard && darkCard) {
      if (next === 'dark') {
        darkCard.classList.add('active');
        lightCard.classList.remove('active');
      } else {
        lightCard.classList.add('active');
        darkCard.classList.remove('active');
      }
    }
  },

  updateThemeButton(theme) {
    const icons = document.querySelectorAll('.theme-icon, .theme-icon-dropdown');
    icons.forEach(icon => {
      icon.setAttribute('data-lucide', theme === 'dark' ? 'sun' : 'moon');
    });
    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }
  },

  // ── Toast Notifications ──
  toast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const icons = { success: 'check-circle', error: 'alert-triangle', info: 'info' };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon"><i data-lucide="${icons[type] || 'info'}"></i></span>
      <span class="toast-message">${message}</span>
      <button class="toast-close" onclick="this.parentElement.remove()"><i data-lucide="x"></i></button>
    `;
    container.appendChild(toast);
    
    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }

    setTimeout(() => {
      toast.classList.add('removing');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  // ── Modals ──
  openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('active');
  },

  closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('active');
  },

  // ── Panel Toggles ──
  initPanelToggles() {
    document.querySelectorAll('.panel-header').forEach(header => {
      header.addEventListener('click', () => {
        const section = header.closest('.panel-section');
        section.classList.toggle('collapsed');
      });
    });
  },

  // ── Sidebar Toggles (mobile/tablet) ──
  initSidebarToggles() {
    const leftToggle = document.getElementById('toggleLeftSidebar');
    const rightToggle = document.getElementById('toggleRightSidebar');
    const sidebarLeft = document.getElementById('sidebarLeft');
    const sidebarRight = document.getElementById('sidebarRight');

    if (leftToggle) {
      leftToggle.addEventListener('click', () => {
        sidebarLeft.classList.toggle('open');
        sidebarRight.classList.remove('open');
      });
    }

    if (rightToggle) {
      rightToggle.addEventListener('click', () => {
        sidebarRight.classList.toggle('open');
        sidebarLeft.classList.remove('open');
      });
    }

    // Close sidebars when clicking on main workspace on mobile
    document.getElementById('mainWorkspace')?.addEventListener('click', () => {
      if (window.innerWidth <= 1024) {
        sidebarLeft?.classList.remove('open');
        sidebarRight?.classList.remove('open');
      }
    });
  },

  // ── Loading Animation ──
  showLoading() {
    const section = document.getElementById('loadingSection');
    const results = document.getElementById('resultsSection');
    if (results) results.style.display = 'none';
    section.classList.add('active');

    const stages = section.querySelectorAll('.loading-stage');
    stages.forEach(s => {
      s.classList.remove('active', 'done');
    });

    // Animate stages sequentially
    const stageNames = ['schema', 'intent', 'generate', 'validate', 'execute', 'render'];
    let delay = 0;
    stageNames.forEach((name, i) => {
      const stage = section.querySelector(`[data-stage="${name}"]`);
      setTimeout(() => {
        // Mark previous as done
        if (i > 0) {
          const prev = section.querySelector(`[data-stage="${stageNames[i-1]}"]`);
          prev.classList.remove('active');
          prev.classList.add('done');
        }
        stage.classList.add('active');
      }, delay);
      delay += 350 + Math.random() * 200;
    });

    return delay;
  },

  hideLoading() {
    const section = document.getElementById('loadingSection');
    const stages = section.querySelectorAll('.loading-stage');
    stages.forEach(s => {
      s.classList.remove('active');
      s.classList.add('done');
    });
    setTimeout(() => {
      section.classList.remove('active');
    }, 400);
  },

  // ── Format Helpers ──
  formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return parseFloat((bytes / Math.pow(1024, i)).toFixed(1)) + ' ' + sizes[i];
  },

  formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  },

  timeAgo(date) {
    const seconds = Math.floor((new Date() - new Date(date)) / 1000);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
    return Math.floor(seconds / 86400) + 'd ago';
  }
};
