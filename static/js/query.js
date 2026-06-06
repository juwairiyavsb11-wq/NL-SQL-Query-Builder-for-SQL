/**
 * AskDB — Query Module
 * Natural language query input, SQL display with syntax highlighting,
 * confidence visualization, explanation, and query bookmark saving.
 */

const Query = {
  lastQuery: "",
  lastSQL: "",

  init() {
    this.bindEvents();
  },

  bindEvents() {
    const input = document.getElementById('queryInput');
    const sendBtn = document.getElementById('btnSend');
    const clearBtn = document.getElementById('btnClear');
    const copyBtn = document.getElementById('btnCopySQL');
    const saveBtn = document.getElementById('btnSaveQuery');

    // Send on button click
    sendBtn?.addEventListener('click', () => this.submit());

    // Send on Ctrl+Enter
    input?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.submit();
      }
    });

    // Auto-resize textarea
    input?.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    });

    // Clear
    clearBtn?.addEventListener('click', () => {
      input.value = '';
      input.style.height = 'auto';
      input.focus();
    });

    // Copy SQL
    copyBtn?.addEventListener('click', () => {
      const sqlEl = document.getElementById('sqlCode');
      const text = sqlEl?.textContent || '';
      if (text && text !== '-- Your SQL will appear here after running a query') {
        navigator.clipboard.writeText(text).then(() => {
          copyBtn.innerHTML = '<i data-lucide="check"></i> Copied!';
          if (typeof lucide !== 'undefined') lucide.createIcons();
          setTimeout(() => {
            copyBtn.innerHTML = '<i data-lucide="copy"></i> Copy';
            if (typeof lucide !== 'undefined') lucide.createIcons();
          }, 1500);
          UI.toast('SQL copied to clipboard', 'success', 2000);
        });
      }
    });

    // Save/Bookmark Query
    saveBtn?.addEventListener('click', () => {
      if (!this.lastQuery || !this.lastSQL) {
        UI.toast('Execute a query first before bookmarking it.', 'info');
        return;
      }
      const nameInput = document.getElementById('bookmarkName');
      if (nameInput) nameInput.value = '';
      UI.openModal('saveQueryModal');
    });

    document.getElementById('btnConfirmSaveQuery')?.addEventListener('click', () => {
      this.confirmSaveQuery();
    });
  },

  async submit() {
    const input = document.getElementById('queryInput');
    const query = input?.value?.trim();
    if (!query) {
      UI.toast('Please enter a query', 'info');
      return;
    }

    // Show loading animation
    const loadingDelay = UI.showLoading();

    try {
      const resp = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      const data = await resp.json();

      // Wait for loading animation to finish
      const elapsed = Date.now();
      const minWait = Math.max(0, loadingDelay + 400 - (Date.now() - elapsed));

      setTimeout(() => {
        UI.hideLoading();

        if (data.success) {
          this.lastQuery = query;
          this.lastSQL = data.sql;

          this.displaySQL(data.sql);
          this.displayExplanation(data.explanation);
          this.displayConfidence(data.confidence);
          this.displayValidation('safe', 'Query is safe — SELECT only');
          
          Results.render(data.columns, data.rows, data.execution_time, data.row_count);

          // Update last query time in insights if bar exists
          const lastTimeInsight = document.getElementById('insightLastTime');
          if (lastTimeInsight) {
            lastTimeInsight.textContent = data.execution_time + 'ms';
          }

          if (data.warnings && data.warnings.length > 0) {
            data.warnings.forEach(w => UI.toast(w, 'info', 5000));
          }
        } else {
          const errorMsg = data.error || 'Failed to process query';
          UI.toast(errorMsg, 'error', 6000);

          if (data.sql) {
            this.displaySQL(data.sql);
          }
          if (data.confidence) {
            this.displayConfidence(data.confidence);
          }
          this.displayValidation('blocked', errorMsg);
        }
      }, minWait);

    } catch (err) {
      UI.hideLoading();
      UI.toast('Network error: ' + err.message, 'error');
    }
  },

  // Save bookmarked query to backend API
  async confirmSaveQuery() {
    const nameInput = document.getElementById('bookmarkName');
    const name = nameInput?.value?.trim();
    if (!name) {
      UI.toast('Please enter a name for the bookmark', 'info');
      return;
    }

    try {
      const response = await fetch('/api/query/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          nl_query: this.lastQuery,
          sql: this.lastSQL
        })
      });

      const data = await response.json();
      if (data.success) {
        UI.closeModal('saveQueryModal');
        UI.toast('Query successfully saved to Bookmarks!', 'success');
      } else {
        UI.toast('Failed to bookmark query: ' + data.error, 'error');
      }
    } catch (err) {
      UI.toast('Failed to bookmark query: ' + err.message, 'error');
    }
  },

  // ── SQL Syntax Highlighting ──
  highlightSQL(sql) {
    if (!sql) return '';

    const keywords = new Set([
      'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'BETWEEN',
      'LIKE', 'IS', 'NULL', 'AS', 'ON', 'JOIN', 'LEFT', 'RIGHT', 'INNER',
      'OUTER', 'CROSS', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET',
      'UNION', 'ALL', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
      'ASC', 'DESC', 'WITH', 'EXISTS', 'TRUE', 'FALSE'
    ]);

    const functions = new Set([
      'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'COALESCE', 'IFNULL',
      'UPPER', 'LOWER', 'LENGTH', 'TRIM', 'SUBSTR', 'REPLACE',
      'DATE', 'TIME', 'DATETIME', 'STRFTIME', 'ROUND', 'ABS',
      'CAST', 'TYPEOF', 'GROUP_CONCAT', 'TOTAL'
    ]);

    // Tokenize the SQL and build highlighted HTML in one pass
    const tokens = sql.match(/--[^\n]*|'[^']*'|\b\d+(?:\.\d+)?\b|\b\w+\b|[^\s\w]+|\s+/g) || [];
    let result = '';

    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i];

      // Comment
      if (token.startsWith('--')) {
        result += '<span class="sql-comment">' + this._esc(token) + '</span>';
      }
      // String literal
      else if (token.startsWith("'")) {
        result += '<span class="sql-string">' + this._esc(token) + '</span>';
      }
      // Number
      else if (/^\d+(?:\.\d+)?$/.test(token)) {
        result += '<span class="sql-number">' + token + '</span>';
      }
      // Word token
      else if (/^\w+$/.test(token)) {
        const upper = token.toUpperCase();
        // Check if it's a function (followed by a paren)
        const next = tokens[i + 1];
        if (functions.has(upper) && next && next.trim().startsWith('(')) {
          result += '<span class="sql-function">' + upper + '</span>';
        } else if (keywords.has(upper)) {
          result += '<span class="sql-keyword">' + upper + '</span>';
        } else {
          result += this._esc(token);
        }
      }
      // Operators / punctuation
      else if (/^[^\s\w]+$/.test(token)) {
        result += '<span class="sql-operator">' + this._esc(token) + '</span>';
      }
      // Whitespace
      else {
        result += token;
      }
    }

    return result;
  },

  _esc(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  },

  displaySQL(sql) {
    const el = document.getElementById('sqlCode');
    if (el) {
      el.innerHTML = this.highlightSQL(sql);
    }
  },

  displayExplanation(text) {
    const el = document.getElementById('explanationText');
    if (el) el.textContent = text || 'No explanation available.';
  },

  displayConfidence(score) {
    const ring = document.getElementById('confidenceRing');
    const value = document.getElementById('confidenceValue');
    const level = document.getElementById('confidenceLevel');

    if (!ring || !value || !level) return;

    // Animate the ring
    const circumference = 2 * Math.PI * 24; // r=24
    const offset = circumference - (score / 100) * circumference;
    ring.style.strokeDashoffset = offset;

    value.textContent = score + '%';

    if (score >= 80) {
      level.textContent = 'High';
      level.className = 'confidence-level high';
      ring.style.stroke = 'var(--success-text)';
    } else if (score >= 50) {
      level.textContent = 'Medium';
      level.className = 'confidence-level medium';
      ring.style.stroke = 'var(--warning-text)';
    } else {
      level.textContent = 'Low';
      level.className = 'confidence-level low';
      ring.style.stroke = 'var(--danger-text)';
    }
  },

  displayValidation(status, message) {
    const badge = document.getElementById('validationBadge');
    const text = document.getElementById('validationText');
    if (!badge || !text) return;

    badge.className = 'validation-badge ' + status;
    badge.innerHTML = status === 'safe'
      ? '<i data-lucide="shield-check"></i> <span id="validationText">Query is safe</span>'
      : '<i data-lucide="alert-triangle"></i> <span id="validationText">Blocked</span>';
    text.textContent = message;

    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }
  },

  // ── Suggestions ──
  async loadSuggestions() {
    try {
      const resp = await fetch('/api/suggestions');
      const data = await resp.json();
      if (data.success && data.suggestions) {
        this.renderSuggestions(data.suggestions);
      }
    } catch (err) {
      console.error('Failed to load suggestions:', err);
    }
  },

  renderSuggestions(suggestions) {
    const container = document.getElementById('suggestionsSection');
    if (!container) return;

    const icons = {
      explore: 'search', count: 'hash', ranking: 'award',
      aggregation: 'bar-chart-2', time: 'calendar', grouping: 'folder', join: 'link'
    };

    container.innerHTML = suggestions.map(s => `
      <button class="suggestion-chip" data-query="${s.text}">
        <span class="chip-icon"><i data-lucide="${icons[s.category] || 'sparkles'}"></i></span>
        ${s.text}
      </button>
    `).join('');

    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }

    // Click to use suggestion
    container.querySelectorAll('.suggestion-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const input = document.getElementById('queryInput');
        if (input) {
          input.value = chip.dataset.query;
          input.style.height = 'auto';
          input.style.height = Math.min(input.scrollHeight, 200) + 'px';
          input.focus();
        }
      });
    });
  }
};
