/**
 * AskDB — Main Application Controller
 * Initializes shared layouts, coordinates global theme, help drawer, and dropdown settings.
 */

const App = {
  init() {
    // Initialize global theme
    UI.initTheme();

    // Bind shared UI actions
    this.bindGlobalEvents();
    this.initProfileDropdown();
    this.initHelpDrawer();

    console.log('🚀 AskDB SaaS layout initialized');
  },

  bindGlobalEvents() {
    // Theme toggles (all theme buttons on navbar or dropdown)
    document.querySelectorAll('.theme-toggle-btn').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        UI.toggleTheme();
      });
    });
  },

  initProfileDropdown() {
    const btn = document.getElementById('profileDropdownBtn');
    const menu = document.getElementById('profileDropdownMenu');
    if (!btn || !menu) return;

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.classList.toggle('active');
      btn.classList.toggle('active');
    });

    // Close dropdown on outside click
    document.addEventListener('click', () => {
      menu.classList.remove('active');
      btn.classList.remove('active');
    });

    // Stop click propagation inside menu to prevent self-closing
    menu.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  },

  initHelpDrawer() {
    const btn = document.getElementById('btnHelp');
    const drawer = document.getElementById('helpDrawer');
    const overlay = document.getElementById('helpDrawerOverlay');
    const closeBtn = document.getElementById('closeHelpDrawer');

    if (!drawer || !overlay) return;

    const openDrawer = () => {
      drawer.classList.add('active');
      overlay.classList.add('active');
    };

    const closeDrawer = () => {
      drawer.classList.remove('active');
      overlay.classList.remove('active');
    };

    btn?.addEventListener('click', openDrawer);
    closeBtn?.addEventListener('click', closeDrawer);
    overlay?.addEventListener('click', closeDrawer);

    // Escape key closes drawer
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeDrawer();
      }
    });

    // Help Center drawer tabs switcher
    drawer.querySelectorAll('.drawer-tab-btn').forEach(tabBtn => {
      tabBtn.addEventListener('click', () => {
        const tabId = tabBtn.dataset.helpTab;
        
        drawer.querySelectorAll('.drawer-tab-btn').forEach(b => b.classList.remove('active'));
        drawer.querySelectorAll('.drawer-tab-content').forEach(c => c.classList.remove('active'));
        
        tabBtn.classList.add('active');
        const targetContent = drawer.querySelector('#' + tabId);
        if (targetContent) {
          targetContent.classList.add('active');
        }
      });
    });
  },

  async loadInsights() {
    // Workspace-specific checker for database insights
    try {
      const resp = await fetch('/api/insights');
      const data = await resp.json();
      if (data.success && data.insights) {
        const tableInsight = document.getElementById('insightTables');
        const rowInsight = document.getElementById('insightRows');
        const largestInsight = document.getElementById('insightLargest');
        
        if (tableInsight) tableInsight.textContent = data.insights.total_tables;
        if (rowInsight) rowInsight.textContent = UI.formatNumber(data.insights.total_rows);
        if (largestInsight) largestInsight.textContent = data.insights.largest_table || '—';
      }
    } catch (err) {
      console.error('Failed to load insights:', err);
    }
  }
};

// ── Boot ──
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
