/**
 * AskDB — Results Module
 * Data grid rendering, sorting, filtering, pagination, and export.
 */

const Results = {
  columns: [],
  allRows: [],
  filteredRows: [],
  currentPage: 1,
  pageSize: 25,
  sortColumn: -1,
  sortDirection: 'asc',

  init() {
    this.bindEvents();
  },

  bindEvents() {
    // Search/filter
    const search = document.getElementById('resultSearch');
    search?.addEventListener('input', (e) => {
      this.filterRows(e.target.value);
    });

    // Export CSV
    document.getElementById('btnExportCSV')?.addEventListener('click', () => {
      this.exportCSV();
    });

    // Export Excel
    document.getElementById('btnExportExcel')?.addEventListener('click', () => {
      this.exportExcel();
    });
  },

  render(columns, rows, execTime, rowCount) {
    this.columns = columns;
    this.allRows = rows;
    this.filteredRows = [...rows];
    this.currentPage = 1;
    this.sortColumn = -1;

    // Show results section and hide ready placeholder
    const section = document.getElementById('resultsSection');
    const readyState = document.getElementById('resultsReadyState');
    if (section) section.style.display = 'block';
    if (readyState) readyState.style.display = 'none';

    // Auto-activate the Results tab
    document.getElementById('resultsTabBtn')?.click();

    // Update stats
    document.getElementById('resultRowCount').textContent = rowCount;
    document.getElementById('resultExecTime').textContent = execTime + 'ms';

    // Clear search
    const search = document.getElementById('resultSearch');
    if (search) search.value = '';

    this.renderTable();
    this.renderPagination();
  },

  renderTable() {
    const thead = document.getElementById('resultsTableHead');
    const tbody = document.getElementById('resultsTableBody');
    if (!thead || !tbody) return;

    // Headers
    thead.innerHTML = '<tr>' + this.columns.map((col, i) => {
      let sortIcon = '⇅';
      let sortClass = '';
      if (i === this.sortColumn) {
        sortIcon = this.sortDirection === 'asc' ? '↑' : '↓';
        sortClass = ' sorted';
      }
      return `<th class="${sortClass}" data-col="${i}">
        ${col}<span class="sort-icon">${sortIcon}</span>
      </th>`;
    }).join('') + '</tr>';

    // Sort click handlers
    thead.querySelectorAll('th').forEach(th => {
      th.addEventListener('click', () => {
        const col = parseInt(th.dataset.col);
        this.sort(col);
      });
    });

    // Page rows
    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;
    const pageRows = this.filteredRows.slice(start, end);

    // Body
    if (pageRows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="${this.columns.length}" style="text-align:center;padding:32px;color:var(--text-muted);">No results found</td></tr>`;
      return;
    }

    tbody.innerHTML = pageRows.map(row => {
      return '<tr>' + row.map(cell => {
        const display = cell === null ? '<span style="color:var(--text-light);font-style:italic;">NULL</span>' : this.escapeHtml(String(cell));
        return `<td title="${cell !== null ? this.escapeHtml(String(cell)) : 'NULL'}">${display}</td>`;
      }).join('') + '</tr>';
    }).join('');
  },

  sort(colIndex) {
    if (this.sortColumn === colIndex) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = colIndex;
      this.sortDirection = 'asc';
    }

    this.filteredRows.sort((a, b) => {
      let valA = a[colIndex];
      let valB = b[colIndex];

      // Handle nulls
      if (valA === null && valB === null) return 0;
      if (valA === null) return 1;
      if (valB === null) return -1;

      // Try numeric comparison
      const numA = parseFloat(valA);
      const numB = parseFloat(valB);
      if (!isNaN(numA) && !isNaN(numB)) {
        return this.sortDirection === 'asc' ? numA - numB : numB - numA;
      }

      // String comparison
      const strA = String(valA).toLowerCase();
      const strB = String(valB).toLowerCase();
      const cmp = strA.localeCompare(strB);
      return this.sortDirection === 'asc' ? cmp : -cmp;
    });

    this.currentPage = 1;
    this.renderTable();
    this.renderPagination();
  },

  filterRows(query) {
    if (!query) {
      this.filteredRows = [...this.allRows];
    } else {
      const q = query.toLowerCase();
      this.filteredRows = this.allRows.filter(row =>
        row.some(cell => cell !== null && String(cell).toLowerCase().includes(q))
      );
    }
    this.currentPage = 1;
    this.renderTable();
    this.renderPagination();
  },

  renderPagination() {
    const totalRows = this.filteredRows.length;
    const totalPages = Math.ceil(totalRows / this.pageSize);
    const info = document.getElementById('paginationInfo');
    const controls = document.getElementById('paginationControls');

    if (!info || !controls) return;

    const start = (this.currentPage - 1) * this.pageSize + 1;
    const end = Math.min(this.currentPage * this.pageSize, totalRows);
    info.textContent = totalRows > 0
      ? `Showing ${start}–${end} of ${totalRows}`
      : 'No results';

    // Build page buttons
    let html = '';

    // Previous
    html += `<button class="page-btn" data-page="prev" ${this.currentPage <= 1 ? 'disabled' : ''}><i data-lucide="chevron-left"></i></button>`;

    // Page numbers (show max 7)
    const maxButtons = 7;
    let startPage = Math.max(1, this.currentPage - 3);
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    if (endPage - startPage < maxButtons - 1) {
      startPage = Math.max(1, endPage - maxButtons + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      html += `<button class="page-btn ${i === this.currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
    }

    // Next
    html += `<button class="page-btn" data-page="next" ${this.currentPage >= totalPages ? 'disabled' : ''}><i data-lucide="chevron-right"></i></button>`;

    controls.innerHTML = html;
    
    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }

    // Click handlers
    controls.querySelectorAll('.page-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        let page = btn.dataset.page;
        if (page === 'prev') page = this.currentPage - 1;
        else if (page === 'next') page = this.currentPage + 1;
        else page = parseInt(page);

        if (page >= 1 && page <= totalPages) {
          this.currentPage = page;
          this.renderTable();
          this.renderPagination();

          // Scroll table to top
          document.getElementById('resultsTableWrapper')?.scrollTo(0, 0);
        }
      });
    });
  },

  // ── Export CSV ──
  exportCSV() {
    if (this.columns.length === 0) {
      UI.toast('No data to export', 'info');
      return;
    }

    // Build CSV client-side
    const escape = (val) => {
      if (val === null || val === undefined) return '';
      const str = String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return '"' + str.replace(/"/g, '""') + '"';
      }
      return str;
    };

    let csv = this.columns.map(escape).join(',') + '\n';
    this.filteredRows.forEach(row => {
      csv += row.map(escape).join(',') + '\n';
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'askdb_export.csv';
    link.click();
    URL.revokeObjectURL(link.href);

    UI.toast('CSV exported successfully', 'success');
  },

  // ── Export Excel ──
  async exportExcel() {
    if (this.columns.length === 0) {
      UI.toast('No data to export', 'info');
      return;
    }

    try {
      const resp = await fetch('/api/export/excel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          columns: this.columns,
          rows: this.filteredRows
        })
      });

      if (resp.ok) {
        const blob = await resp.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'askdb_export.xlsx';
        link.click();
        URL.revokeObjectURL(link.href);
        UI.toast('Excel exported successfully', 'success');
      } else {
        throw new Error('Export failed');
      }
    } catch (err) {
      UI.toast('Excel export failed: ' + err.message, 'error');
    }
  },

  // ── Utils ──
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
};
