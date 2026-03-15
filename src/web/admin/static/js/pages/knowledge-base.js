(() => {
  const tableBody = document.querySelector("#kbTable tbody");
  const statusSpan = document.querySelector("#kbUploadStatus");
  const categoryList = document.querySelector("#kb-category-list");
  const topicsList = document.querySelector("#kb-topics-list");
  const ageGroupsList = document.querySelector("#kb-age-groups-list");
  const taxonomyTableBody = document.querySelector("#kbTaxonomyTable tbody");
  let statusCache = {};
  let taxonomyRows = [];
  const taxonomyFilter = document.querySelector("#kbTaxonomyFilter");
  const taxonomyFilterClear = document.querySelector("#kbTaxonomyFilterClear");
  const statusEndpoint = (id) => `/api/v1/knowledge/${id}/status`;
  const previewEndpoint = (id) => `/api/v1/knowledge/${id}`;
  const taxonomyEndpoint = "/api/v1/knowledge/taxonomy";

  async function fetchDocs() {
    const res = await fetch("/api/v1/knowledge/documents");
    if (!res.ok) return;
    const rows = await res.json();
    tableBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      const statusBadge =
        r.status === "indexed"
          ? '<span class="badge bg-success">indexed</span>'
          : r.status === "processing"
          ? '<span class="badge bg-warning text-dark">processing</span>'
          : r.status === "error"
          ? '<span class="badge bg-danger">error</span>'
          : `<span class="badge bg-secondary">${r.status || "unknown"}</span>`;
      tr.innerHTML = `
        <td>${r.title}</td>
        <td>${r.category || ""}</td>
        <td>${r.visibility}</td>
        <td>${statusBadge}</td>
        <td>${r.chunk_count}</td>
        <td>${r.organization_id || ""}</td>
        <td>${r.indexed_at || ""}</td>
        <td>
          <button class="btn btn-sm btn-outline-secondary" data-preview-id="${r.id}">Preview</button>
          <button class="btn btn-sm btn-outline-danger" data-id="${r.id}">Delete</button>
        </td>
      `;
      tableBody.appendChild(tr);
      statusCache[r.id] = r.status;
    });
  }

  async function deleteDoc(id) {
    const res = await fetch(`/api/v1/knowledge/${id}`, { method: "DELETE" });
    if (res.ok) await fetchDocs();
  }

  document.addEventListener("click", (e) => {
    if (e.target.matches("button[data-id]")) {
      deleteDoc(e.target.getAttribute("data-id"));
    } else if (e.target.matches("button[data-preview-id]")) {
      showPreview(e.target.getAttribute("data-preview-id"));
    } else if (e.target.matches("button[data-tax-delete]")) {
      const id = e.target.getAttribute("data-tax-delete");
      deleteTaxonomy(id);
    } else if (e.target.matches("button[data-tax-edit]")) {
      const id = e.target.getAttribute("data-tax-edit");
      const current = e.target.getAttribute("data-tax-value");
      editTaxonomy(id, current);
    }
  });

  document.getElementById("kbRefreshBtn").addEventListener("click", fetchDocs);

  // Poll statuses for docs still processing
  async function pollStatuses() {
    const ids = Object.keys(statusCache).filter((id) => statusCache[id] === "processing");
    if (!ids.length) return;
    for (const id of ids) {
      try {
        const res = await fetch(statusEndpoint(id));
        if (!res.ok) continue;
        const data = await res.json();
        statusCache[id] = data.status;
      } catch (_) {}
    }
    fetchDocs();
  }

  document.getElementById("kbUploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    statusSpan.textContent = "Uploading...";
    const formData = new FormData(e.target);
    const autoTag = document.getElementById("kbAutoTag");
    const autoSummary = document.getElementById("kbAutoSummary");
    formData.set("auto_tag", autoTag && autoTag.checked ? "true" : "false");
    formData.set("auto_summary", autoSummary && autoSummary.checked ? "true" : "false");
    const res = await fetch("/api/v1/knowledge/upload", { method: "POST", body: formData });
    if (res.ok) {
      const data = await res.json();
      statusSpan.textContent = `Done (status: ${data.status})`;
      await fetchDocs();
      await fetchTaxonomy();
    } else {
      const text = await res.text();
      statusSpan.textContent = `Error: ${text}`;
    }
  });

  fetchDocs();
  fetchTaxonomy();
  // Auto-refresh every 20s and poll statuses
  setInterval(() => { fetchDocs(); pollStatuses(); }, 20000);

  async function showPreview(id) {
    const res = await fetch(previewEndpoint(id));
    if (!res.ok) return;
    const data = await res.json();
    const snippet = (data.content || "").substring(0, 400);
    alert(`Title: ${data.title}\n\nPreview:\n${snippet}`);
  }

  function populateDatalist(listEl, items) {
    if (!listEl) return;
    listEl.innerHTML = "";
    items.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item.value;
      listEl.appendChild(opt);
    });
  }

  async function fetchTaxonomy() {
    const res = await fetch(taxonomyEndpoint);
    if (!res.ok) return;
    const data = await res.json();
    const categories = data.categories || [];
    const topics = data.topics || [];
    const ageGroups = data.age_groups || [];
    populateDatalist(categoryList, categories);
    populateDatalist(topicsList, topics);
    populateDatalist(ageGroupsList, ageGroups);
    taxonomyRows = []
      .concat(categories.map((c) => ({ ...c, type: "category" })))
      .concat(topics.map((t) => ({ ...t, type: "topic" })))
      .concat(ageGroups.map((a) => ({ ...a, type: "age_group" })));
    renderTaxonomyTable();
  }

  function renderTaxonomyTable() {
    if (!taxonomyTableBody) return;
    const rawFilterText = taxonomyFilter && taxonomyFilter.value ? taxonomyFilter.value.trim() : "";
    const filterText = rawFilterText.toLowerCase();
    const rows = taxonomyRows
      .filter((r) => {
        if (!filterText) return true;
        const hay = `${r.type} ${r.value} ${r.source || ""}`.toLowerCase();
        return hay.includes(filterText);
      })
      .slice()
      .sort((a, b) => {
      if (a.type !== b.type) return a.type.localeCompare(b.type);
      if ((b.count || 0) !== (a.count || 0)) return (b.count || 0) - (a.count || 0);
      return (a.value || "").localeCompare(b.value || "");
    });
    taxonomyTableBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      const canEdit = r.source === "manual" && r.id && r.type !== "age_group";
      const typeCell = renderHighlight(r.type, rawFilterText);
      const valueCell = renderHighlight(r.value, rawFilterText);
      const sourceCell = renderHighlight(r.source || "document", rawFilterText);
      tr.innerHTML = `
        <td>${typeCell}</td>
        <td>${valueCell}</td>
        <td>${r.count || 0}</td>
        <td>${sourceCell}</td>
        <td>
          ${canEdit ? `<button class="btn btn-sm btn-outline-secondary" data-tax-edit="${r.id}" data-tax-value="${r.value}">Edit</button>` : ""}
          ${canEdit ? `<button class="btn btn-sm btn-outline-danger ms-1" data-tax-delete="${r.id}">Delete</button>` : ""}
        </td>
      `;
      taxonomyTableBody.appendChild(tr);
    });
  }

  function escapeHtml(text) {
    return (text || "")
      .toString()
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function renderHighlight(text, filterText) {
    const safeText = escapeHtml(text);
    if (!filterText) return safeText;
    const re = new RegExp(escapeRegExp(filterText), "ig");
    return safeText.replace(re, (match) => `<mark>${match}</mark>`);
  }

  async function addTaxonomy(type, value) {
    if (!value) return;
    const fd = new FormData();
    fd.append("taxonomy_type", type);
    fd.append("value", value.trim());
    const res = await fetch(taxonomyEndpoint, { method: "POST", body: fd });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || "Failed to add taxonomy entry.");
      return;
    }
    await fetchTaxonomy();
  }

  async function deleteTaxonomy(id) {
    if (!id) return;
    if (!confirm("Delete this taxonomy entry?")) return;
    const res = await fetch(`${taxonomyEndpoint}/${id}`, { method: "DELETE" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || "Delete failed.");
      return;
    }
    await fetchTaxonomy();
  }

  async function editTaxonomy(id, current) {
    if (!id) return;
    const value = prompt("New value:", current || "");
    if (!value) return;
    const fd = new FormData();
    fd.append("value", value.trim());
    const res = await fetch(`${taxonomyEndpoint}/${id}`, { method: "PATCH", body: fd });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || "Update failed.");
      return;
    }
    await fetchTaxonomy();
  }

  document.getElementById("kbTaxonomyRefresh").addEventListener("click", fetchTaxonomy);
  if (taxonomyFilter) {
    taxonomyFilter.addEventListener("input", renderTaxonomyTable);
  }
  if (taxonomyFilterClear) {
    taxonomyFilterClear.addEventListener("click", () => {
      if (taxonomyFilter) taxonomyFilter.value = "";
      renderTaxonomyTable();
    });
  }
  document.getElementById("kbTaxCategoryAdd").addEventListener("click", () => {
    const val = document.getElementById("kbTaxCategory").value;
    addTaxonomy("category", val);
    document.getElementById("kbTaxCategory").value = "";
  });
  document.getElementById("kbTaxTopicAdd").addEventListener("click", () => {
    const val = document.getElementById("kbTaxTopic").value;
    addTaxonomy("topic", val);
    document.getElementById("kbTaxTopic").value = "";
  });
})();
