/**
 * AskDB — Database Module
 * Database upload, schema tree rendering, and table search.
 */

const Database = {
  schema: null,
  dbInfo: null,

  // ── Upload ──
  initUpload() {
    const zone = document.getElementById('uploadZone');
    const input = document.getElementById('uploadInput');

    if (!zone || !input) return;

    // Click to browse
    zone.addEventListener('click', () => input.click());

    // File selected
    input.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        this.uploadFile(e.target.files[0]);
      }
    });

    // Drag and drop
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
      zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        this.uploadFile(e.dataTransfer.files[0]);
      }
    });
  },

  async uploadFile(file) {
    const validExts = ['.db', '.sqlite', '.sqlite3'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!validExts.includes(ext)) {
      UI.toast('Invalid file type. Please upload .db, .sqlite, or .sqlite3', 'error');
      return;
    }

    // Show progress
    const progress = document.getElementById('uploadProgress');
    const uploadZone = document.getElementById('uploadZone');
    const progressFill = document.getElementById('progressBarFill');
    const statusText = document.getElementById('uploadStatusText');

    uploadZone.style.display = 'none';
    progress.classList.add('active');
    progressFill.style.width = '20%';
    statusText.textContent = 'Uploading ' + file.name + '...';

    const formData = new FormData();
    formData.append('file', file);

    try {
      progressFill.style.width = '50%';
      statusText.textContent = 'Processing database...';

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (data.success) {
        progressFill.style.width = '100%';
        statusText.textContent = 'Database loaded successfully!';
        this.dbInfo = data.database;

        setTimeout(() => {
          if (window.location.pathname === '/databases') {
            window.location.reload();
          } else {
            this.onDatabaseLoaded();
          }
        }, 600);

        UI.toast(`Database "${data.database.name}" loaded with ${data.database.table_count} tables`, 'success');
      } else {
        throw new Error(data.error || 'Upload failed');
      }
    } catch (err) {
      progress.classList.remove('active');
      uploadZone.style.display = '';
      UI.toast('Upload failed: ' + err.message, 'error');
    }
  },

  async onDatabaseLoaded() {
    // Fetch schema
    try {
      const resp = await fetch('/api/schema');
      const data = await resp.json();
      if (data.success) {
        this.schema = data.schema;
        this.renderSchemaTree();
        this.updateDbInfo();
        this.showWorkspace();
        Query.loadSuggestions();
        if (typeof App !== 'undefined' && App.loadInsights) {
          App.loadInsights();
        }
      }
    } catch (err) {
      UI.toast('Failed to load schema: ' + err.message, 'error');
    }
  },

  showWorkspace() {
    const layout = document.getElementById('appLayout');
    const emptyState = document.getElementById('emptyState');
    const workspace = document.getElementById('activeWorkspace');

    if (layout) layout.classList.remove('no-database');
    if (emptyState) emptyState.style.display = 'none';
    if (workspace) workspace.style.display = 'flex';

    // Update status
    const status = document.getElementById('dbStatus');
    const statusText = document.getElementById('dbStatusText');
    if (status) status.classList.add('connected');
    if (statusText) statusText.textContent = this.schema?.database_name || 'Connected';
  },

  updateDbInfo() {
    const card = document.getElementById('dbInfoCard');
    if (!this.schema || !card) return;

    card.style.display = 'block';
    document.getElementById('dbInfoName').textContent = this.schema.database_name;
    document.getElementById('dbInfoTables').textContent = this.schema.table_count;
    document.getElementById('dbInfoColumns').textContent = this.schema.total_columns;
    document.getElementById('dbInfoRows').textContent = UI.formatNumber(this.schema.total_rows);
    document.getElementById('dbInfoSize').textContent = UI.formatBytes(this.schema.file_size);
  },

  renderSchemaTree() {
    const tree = document.getElementById('tableTree');
    if (!this.schema || !tree) return;

    tree.innerHTML = '';
    this.schema.tables.forEach(table => {
      const li = document.createElement('li');
      li.className = 'table-item';
      li.dataset.tableName = table.name.toLowerCase();

      // Foreign key columns for this table
      const fkCols = new Set(table.foreign_keys.map(fk => fk.from_column));

      li.innerHTML = `
        <div class="table-header">
          <span class="table-toggle"><i data-lucide="chevron-right"></i></span>
          <span class="table-icon"><i data-lucide="table"></i></span>
          <span class="table-name">${table.name}</span>
          <span class="table-row-count">${UI.formatNumber(table.row_count)}</span>
        </div>
        <ul class="column-list">
          ${table.columns.map(col => {
            let keyBadge = '';
            if (col.primary_key) keyBadge = '<span class="column-key pk">PK</span>';
            else if (fkCols.has(col.name)) keyBadge = '<span class="column-key fk">FK</span>';
            return `
              <li class="column-item">
                ${keyBadge}
                <span class="column-name">${col.name}</span>
                <span class="column-type">${col.type}</span>
              </li>
            `;
          }).join('')}
        </ul>
      `;

      // Toggle expand/collapse
      const header = li.querySelector('.table-header');
      header.addEventListener('click', () => {
        li.classList.toggle('expanded');
      });

      tree.appendChild(li);
    });

    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }
  },

  // ── Table Search ──
  initSearch() {
    const input = document.getElementById('tableSearch');
    if (!input) return;

    input.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase();
      document.querySelectorAll('.table-item').forEach(item => {
        const name = item.dataset.tableName || '';
        item.style.display = name.includes(query) ? '' : 'none';
      });
    });
  },

  // ── Check for existing database on load ──
  async checkExisting() {
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      if (data.success && data.connected) {
        await this.onDatabaseLoaded();
      }
    } catch (err) {
      // No existing database, stay in empty state
    }
  }
};
