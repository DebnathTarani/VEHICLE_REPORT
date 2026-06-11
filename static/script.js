// Configuration
const remarksOptions = ["Work Done", "Work In Progress"];

// Thinking mode toggle (default: enabled, matching current behavior)
let thinkingEnabled = true;

function setThinkingMode(enabled) {
  thinkingEnabled = enabled;
}

// Utility functions (no regex)
function escapeHtml(s) {
  if (!s) return "";
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    out += map[ch] || ch;
  }
  return out;
}

function safeSheetName(name) {
  // Excel sheet name constraints: <=31 chars, no []:*?/\
  if (!name) return "Sheet";
  const invalid = new Set(["[", "]", ":", "*", "?", "/", "\\"]);
  let cleaned = "";
  for (const ch of name) {
    cleaned += invalid.has(ch) ? " " : ch;
  }
  cleaned = cleaned.trim();
  if (!cleaned) cleaned = "Sheet";
  if (cleaned.length > 31) cleaned = cleaned.slice(0, 31);
  return cleaned;
}

function viewLogsByDate() {
  const date = document.getElementById("entryDateFilter")?.value;
  if (!date) {
    alert("Please select a date.");
    return;
  }
  window.open(`/view_by_date/${date}`, "_blank");
}

function formatTime12(timeStr) {
  if (!timeStr) return "";
  const parts = timeStr.split(":");
  if (parts.length < 2) return "";
  const hour = parts[0], minute = parts[1];
  const h = parseInt(hour, 10);
  if (Number.isNaN(h)) return "";
  const suffix = h >= 12 ? "PM" : "AM";
  const hour12 = h % 12 || 12;
  return `${hour12}:${minute} ${suffix}`;
}

// Serial number management
function updateSerialNumbers(section) {
  const rows = section.querySelectorAll("tbody tr");
  rows.forEach((row, index) => {
    const serialInput = row.querySelector("td:first-child input");
    if (serialInput) {
      serialInput.value = index + 1;
    }
  });
}

// Initialization
window.addEventListener("DOMContentLoaded", () => {
  const addBtn = document.getElementById("addCityBtn");
  const submitBtn = document.getElementById("submitBtn");
  const excelBtn = document.getElementById("downloadExcelBtn")?.addEventListener("click", submitData);
  if (addBtn) addBtn.addEventListener("click", addCitySection);
  if (submitBtn) submitBtn.addEventListener("click", submitData);
  if (excelBtn) excelBtn.addEventListener("click", submitData);

  // Check AI status on page load
  checkAIStatus();
});

// Store extracted data temporarily for import
let pendingImportData = [];

// Check if AI extraction is available
function checkAIStatus() {
  fetch("/check_ai_status")
    .then(res => res.json())
    .then(data => {
      const statusEl = document.getElementById("aiStatus");
      const importBtn = document.getElementById("importImageBtn");
      if (data.ai_enabled) {
        statusEl.textContent = "✅ " + (data.message || "AI Ready");
        statusEl.className = "ai-status enabled";
        // Disable import button if model doesn't support vision
        if (data.vision_supported === false) {
          statusEl.textContent = "⚠️ Model does not support image input";
          statusEl.className = "ai-status disabled";
          importBtn.disabled = true;
        } else {
          importBtn.disabled = false;
        }
        // Sync thinking toggle with server config
        if (data.thinking_disabled !== undefined) {
          const toggle = document.getElementById("thinkingToggle");
          if (toggle) {
            toggle.checked = !data.thinking_disabled;
            thinkingEnabled = toggle.checked;
          }
        }
      } else {
        statusEl.textContent = "⚠️ " + (data.message || "AI Disabled");
        statusEl.className = "ai-status disabled";
        importBtn.disabled = true;
      }
    })
    .catch(err => {
      console.error("AI status check failed:", err);
      const statusEl = document.getElementById("aiStatus");
      statusEl.textContent = "❌ Check Failed";
      statusEl.className = "ai-status disabled";
    });
}

// Processing lock to prevent re-entry
let isProcessingImages = false;

// Handle multiple image file uploads
async function handleMultiImageUpload(input) {
  if (isProcessingImages) return;
  const files = Array.from(input.files);
  if (files.length === 0) return;

  isProcessingImages = true;
  const importBtn = document.getElementById("importImageBtn");
  if (importBtn) importBtn.disabled = true;

  // Show modal with loading spinner
  openImportModal();
  showLoading(true);

  const resultsContainer = document.getElementById("imageResultsContainer");
  resultsContainer.innerHTML = "";

  let imageCounter = 0;

  // Process each image sequentially
  for (const file of files) {
    imageCounter++;
    document.getElementById("processingStatus").textContent =
      `Processing image ${imageCounter} of ${files.length}: ${file.name}`;

    try {
      // Convert image to data URL for preview
      const imageDataUrl = await fileToDataUrl(file);

      const formData = new FormData();
      formData.append("image", file);
      formData.append("disable_thinking", thinkingEnabled ? "false" : "true");

      const response = await fetch("/extract_from_image", {
        method: "POST",
        body: formData
      });

      const data = await response.json();

      if (data.status === "success") {
        // Create a result card for this image with preview
        const cardId = `result-${Date.now()}-${imageCounter}`;
        createImageResultCard(cardId, file.name, data.data, resultsContainer, imageDataUrl);
      } else {
        // Create error card for this image with retry option
        createErrorCard(file.name, data.message || "Unknown error", resultsContainer, file);
      }
    } catch (err) {
      createErrorCard(file.name, err.message, resultsContainer, file);
    }
  }

  showLoading(false);
  resultsContainer.style.display = "block";
  document.getElementById("modalFooter").style.display = "block";

  // Reset file input
  input.value = "";

  // Release processing lock
  isProcessingImages = false;
  // Re-check AI status (vision_supported may have been updated)
  checkAIStatus();
}

// Convert file to data URL for preview
function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// Format VRN (Vehicle Registration Number) to standard format: XX00 XX 0000
function formatVRN(vrn) {
  if (!vrn) return "";

  // Remove all spaces and special characters, convert to uppercase
  let cleaned = vrn.replace(/[^A-Za-z0-9]/g, "").toUpperCase();

  // Standard Indian VRN format: SS DD CC NNNN (State, District, Series, Number)
  // Examples: AS01TC7803 -> AS01 TC 7803

  // Try to match common patterns
  const match = cleaned.match(/^([A-Z]{2})(\d{2})([A-Z]{1,3})(\d{1,4})$/);

  if (match) {
    const [, state, district, series, number] = match;
    // Pad number to 4 digits if less
    const paddedNumber = number.padStart(4, '0');
    return `${state}${district} ${series} ${paddedNumber}`;
  }

  // If doesn't match standard format, just clean up spaces
  return cleaned;
}

// Create a result card for an image with editable table and preview
function createImageResultCard(cardId, fileName, data, container, imageDataUrl) {
  const cityOptions = ['Hailakandi', 'Karimganj', 'Kalain', 'Jhapirbond', 'Sildubi', 'Fulertal', 'Budrail_Yard'];
  const remarksOptions = ["Work Done", "Work In Progress", "Pending", "Cancelled"];

  const card = document.createElement("div");
  card.className = "image-result-card";
  card.id = cardId;
  card.dataset.entries = JSON.stringify(data);

  card.innerHTML = `
    <div class="image-result-header" style="flex-wrap: wrap; gap: 10px;">
      <span class="image-result-title">📄 ${escapeHtml(fileName)} - <span class="visible-count">${data.length}</span> entries</span>
      <div class="image-result-actions" style="flex-wrap: wrap; gap: 8px;">
        <span style="display: flex; align-items: center; gap: 5px;">
          <label>Entry:</label>
          <input type="date" class="entry-date-filter" style="width: 130px; padding: 4px;" />
          <button type="button" onclick="filterCardByEntryDate('${cardId}')" title="Filter by Entry Date">🔍</button>
        </span>
        <span style="display: flex; align-items: center; gap: 5px;">
          <label>Out:</label>
          <input type="date" class="out-date-filter" style="width: 130px; padding: 4px;" />
          <button type="button" onclick="filterCardByOutDate('${cardId}')" title="Filter by Out Date">🔍</button>
        </span>
        <button type="button" onclick="clearCardFilter('${cardId}')" title="Clear all filters">🔄 Clear</button>
        <span style="border-left: 1px solid #ccc; margin: 0 5px;"></span>
        <label>Import to:</label>
        <select class="city-select-for-import" style="padding: 5px;">
          <option value="">--Select City--</option>
          ${cityOptions.map(c => `<option value="${c}">${c}</option>`).join("")}
        </select>
        <button class="import-btn" onclick="importCardData('${cardId}')">✅ Import</button>
        <button class="import-btn" onclick="validateCardVRNs('${cardId}')" style="background-color: #2196F3;">🛡️ Validate VRNs</button>
        <button class="import-btn" onclick="retryFailedVRNs('${cardId}')" style="background-color: #FF9800; display: none;" class="retry-failed-btn">🔄 Refresh Failed</button>
        <button class="import-btn" onclick="overwriteAllModels('${cardId}')" style="background-color: #9C27B0; display: none;" class="overwrite-all-btn">⚡ Overwrite All Models</button>
      </div>
    </div>
    <div style="display: flex; gap: 15px; flex-wrap: wrap;">
      <!-- Image Preview Panel -->
      <div class="image-preview-container" style="flex: 0 0 300px; max-height: 350px; overflow: visible; border: 1px solid #ddd; border-radius: 4px; background: #f5f5f5;">
        <img src="${imageDataUrl || ''}" alt="Preview of ${escapeHtml(fileName)}" style="width: 100%; display: block; cursor: zoom-in;" onclick="window.open('${imageDataUrl}', '_blank')" title="Hover to zoom, click to open full size" />
      </div>
      <!-- Data Table Panel -->
      <div style="flex: 1; min-width: 500px; overflow-x: auto; max-height: 350px; overflow-y: auto;">
        <table class="preview-table editable-table">
          <thead>
            <tr>
              <th style="width: 50px;">Sr No</th>
              <th style="width: 120px;">VRN</th>
              <th style="width: 100px;">Model</th>
              <th style="width: 100px;">Entry Date</th>
              <th style="width: 70px;">In Time</th>
              <th style="width: 100px;">Out Date</th>
              <th style="width: 70px;">Out Time</th>
              <th style="width: 120px;">Remarks</th>
              <th style="width: 150px;">Fetched Model</th>
              <th style="width: 50px;">Del</th>
            </tr>
          </thead>
          <tbody>
            ${data.map((entry, idx) => `
              <tr data-row-index="${idx}">
                <td><input type="number" value="${entry.sr_no || idx + 1}" /></td>
                <td><input type="text" value="${escapeHtml(formatVRN(entry.vrn))}" /></td>
                <td><input type="text" value="${escapeHtml(entry.model || "")}" /></td>
                <td><input type="text" value="${escapeHtml(entry.entry_date || "")}" placeholder="DD-MM-YYYY" /></td>
                <td><input type="time" value="${entry.in_time || ""}" /></td>
                <td><input type="text" value="${escapeHtml(entry.out_date || "")}" placeholder="DD-MM-YYYY" /></td>
                <td><input type="time" value="${entry.out_time || ""}" /></td>
                <td>
                  <select>
                    ${remarksOptions.map(r => `<option value="${r}" ${r === (entry.remarks || "Work Done") ? "selected" : ""}>${r}</option>`).join("")}
                  </select>
                </td>
                <td class="fetched-model-cell">
                  <span class="fetched-model-text"></span>
                </td>
                <td><button type="button" onclick="this.closest('tr').remove()">🗑️</button></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;

  container.appendChild(card);
}

// Store files for retry functionality
const pendingRetryFiles = new Map();

// Create error card for failed image with retry option
function createErrorCard(fileName, errorMessage, container, file) {
  const cardId = `error-${Date.now()}`;

  // Store file reference for retry
  if (file) {
    pendingRetryFiles.set(cardId, file);
  }

  const card = document.createElement("div");
  card.className = "image-result-card";
  card.id = cardId;
  card.style.background = "#ffebee";
  card.style.borderColor = "#f44336";

  card.innerHTML = `
    <div class="image-result-header">
      <span class="image-result-title">❌ ${escapeHtml(fileName)} - Failed</span>
      <div class="image-result-actions">
        <button class="import-btn" onclick="retryImage('${cardId}')" style="background: #ff9800;">🔄 Retry</button>
      </div>
    </div>
    <p style="color: #f44336; margin: 10px 0;">${escapeHtml(errorMessage)}</p>
  `;

  container.appendChild(card);
}

// Retry processing a failed image
async function retryImage(cardId) {
  const file = pendingRetryFiles.get(cardId);
  if (!file) {
    alert("Unable to retry - file reference lost. Please re-upload the image.");
    return;
  }

  const card = document.getElementById(cardId);
  if (!card) return;

  // Show loading state
  card.innerHTML = `
    <div class="image-result-header">
      <span class="image-result-title">🔄 ${escapeHtml(file.name)} - Retrying...</span>
    </div>
    <p style="color: #666; margin: 10px 0;">Processing image, please wait...</p>
  `;
  card.style.background = "#fff3e0";
  card.style.borderColor = "#ff9800";

  try {
    const formData = new FormData();
    formData.append("image", file);

    const response = await fetch("/extract_from_image", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (data.status === "success") {
      // Replace error card with success card
      const newCardId = `result-${Date.now()}`;
      const container = card.parentElement;
      card.remove();
      pendingRetryFiles.delete(cardId);
      createImageResultCard(newCardId, file.name, data.data, container);
    } else {
      // Update error card with new error message
      card.style.background = "#ffebee";
      card.style.borderColor = "#f44336";
      card.innerHTML = `
        <div class="image-result-header">
          <span class="image-result-title">❌ ${escapeHtml(file.name)} - Failed</span>
          <div class="image-result-actions">
            <button class="import-btn" onclick="retryImage('${cardId}')" style="background: #ff9800;">🔄 Retry</button>
          </div>
        </div>
        <p style="color: #f44336; margin: 10px 0;">${escapeHtml(data.message || "Unknown error")}</p>
      `;
    }
  } catch (err) {
    card.style.background = "#ffebee";
    card.style.borderColor = "#f44336";
    card.innerHTML = `
      <div class="image-result-header">
        <span class="image-result-title">❌ ${escapeHtml(file.name)} - Failed</span>
        <div class="image-result-actions">
          <button class="import-btn" onclick="retryImage('${cardId}')" style="background: #ff9800;">🔄 Retry</button>
        </div>
      </div>
      <p style="color: #f44336; margin: 10px 0;">${escapeHtml(err.message)}</p>
    `;
  }
}

// Import data from a specific card
function importCardData(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const citySelect = card.querySelector(".city-select-for-import");
  const cityName = citySelect?.value || "";

  if (!cityName) {
    alert("Please select a city to import into");
    return;
  }

  // Clear any previous highlights
  card.querySelectorAll(".validation-error").forEach(el => {
    el.classList.remove("validation-error");
  });

  // Validate and collect data from editable table (only visible rows)
  const rows = card.querySelectorAll("tbody tr");
  const importData = [];
  let hasErrors = false;
  let errorMessages = [];

  rows.forEach((row, rowIndex) => {
    // Skip hidden rows (filtered out)
    if (row.style.display === "none") return;

    const inputs = row.querySelectorAll("input, select");
    const entryDate = inputs[3]?.value?.trim() || "";
    const inTime = inputs[4]?.value?.trim() || "";
    const outDate = inputs[5]?.value?.trim() || "";
    const outTime = inputs[6]?.value?.trim() || "";

    // Validation: Entry Date requires In Time
    if (entryDate && !inTime) {
      hasErrors = true;
      inputs[4].classList.add("validation-error");
      errorMessages.push(`Row ${rowIndex + 1}: Entry Date present but In Time is missing`);
    }

    // Validation: Out Date requires Out Time
    if (outDate && !outTime) {
      hasErrors = true;
      inputs[6].classList.add("validation-error");
      errorMessages.push(`Row ${rowIndex + 1}: Out Date present but Out Time is missing`);
    }

    importData.push({
      sr_no: inputs[0]?.value || "",
      vrn: inputs[1]?.value || "",
      model: inputs[2]?.value || "",
      entry_date: entryDate,
      in_time: inTime,
      out_date: outDate,
      out_time: outTime,
      remarks: inputs[7]?.value || "Work Done"
    });
  });

  if (hasErrors) {
    alert("⚠️ Validation Error:\n\n" + errorMessages.join("\n") + "\n\nPlease fill in the highlighted fields.");
    return;
  }

  if (importData.length === 0) {
    alert("No data to import");
    return;
  }

  // Add to city section
  addDataToCitySection(cityName, importData);

  // Mark card as imported
  card.classList.add("imported");
  const actionsDiv = card.querySelector(".image-result-actions");
  actionsDiv.innerHTML = `<span class="imported-badge">✅ Imported ${importData.length} entries to ${cityName}</span>`;
}

// Filter card rows by Entry Date
function filterCardByEntryDate(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const filterInput = card.querySelector(".entry-date-filter");
  const rawDate = filterInput?.value || "";

  if (!rawDate) {
    alert("Please select an Entry Date to filter");
    return;
  }

  // Convert YYYY-MM-DD to DD-MM-YYYY for comparison
  const [year, month, day] = rawDate.split("-");
  const filterDate = `${day}-${month}-${year}`;

  const rows = card.querySelectorAll("tbody tr");
  let visibleCount = 0;

  rows.forEach(row => {
    const entryDateInput = row.querySelector("td:nth-child(4) input");
    const entryDate = entryDateInput?.value || "";

    if (entryDate.includes(filterDate)) {
      row.style.display = "";
      visibleCount++;
    } else {
      row.style.display = "none";
    }
  });

  updateCardCount(card, visibleCount);
}

// Filter card rows by Out Date
function filterCardByOutDate(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const filterInput = card.querySelector(".out-date-filter");
  const rawDate = filterInput?.value || "";

  if (!rawDate) {
    alert("Please select an Out Date to filter");
    return;
  }

  // Convert YYYY-MM-DD to DD-MM-YYYY for comparison
  const [year, month, day] = rawDate.split("-");
  const filterDate = `${day}-${month}-${year}`;

  const rows = card.querySelectorAll("tbody tr");
  let visibleCount = 0;

  rows.forEach(row => {
    const outDateInput = row.querySelector("td:nth-child(6) input");
    const outDate = outDateInput?.value || "";

    if (outDate.includes(filterDate)) {
      row.style.display = "";
      visibleCount++;
    } else {
      row.style.display = "none";
    }
  });

  updateCardCount(card, visibleCount);
}

// Update visible count display
function updateCardCount(card, count) {
  const countSpan = card.querySelector(".visible-count");
  if (countSpan) {
    countSpan.textContent = count;
  }
}

// Clear filter and show all rows
function clearCardFilter(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const entryFilter = card.querySelector(".entry-date-filter");
  const outFilter = card.querySelector(".out-date-filter");
  if (entryFilter) entryFilter.value = "";
  if (outFilter) outFilter.value = "";

  const rows = card.querySelectorAll("tbody tr");
  rows.forEach(row => {
    row.style.display = "";
  });

  updateCardCount(card, rows.length);
}

// Add data to a city section
function addDataToCitySection(cityName, data) {
  // Ensure city section exists
  let citySection = null;
  let isNewSection = false;
  const existingTitles = document.querySelectorAll(".city-title");
  for (const title of existingTitles) {
    if (title.textContent.replace("City: ", "") === cityName) {
      citySection = title.closest(".city-section");
      break;
    }
  }

  // If city section doesn't exist, create it
  if (!citySection) {
    // Temporarily set dropdown value to create the section
    const citySelect = document.getElementById("citySelect");
    const originalValue = citySelect.value;
    citySelect.value = cityName;
    addCitySection();
    citySelect.value = originalValue;

    const sections = document.querySelectorAll(".city-section");
    citySection = sections[0];
    isNewSection = true;
  }

  const tbody = citySection.querySelector("tbody");

  // Clear empty rows before adding (especially for newly created sections)
  if (isNewSection) {
    tbody.innerHTML = "";
  }

  data.forEach(entry => {
    const row = document.createElement("tr");
    const srNo = entry.sr_no || (tbody.children.length + 1);
    const remarks = entry.remarks || "Work Done";
    const isWIP = remarks === "Work In Progress";

    row.innerHTML = `
      <td><input type="number" value="${srNo}" /></td>
      <td><input type="text" value="${escapeHtml(entry.vrn || "")}" /></td>
      <td><input type="text" value="${escapeHtml(entry.model || "")}" /></td>
      <td><input type="text" value="${entry.entry_date || ""}" placeholder="DD-MM-YYYY" /></td>
      <td><input type="time" value="${entry.in_time || ""}" /></td>
      <td><input type="text" value="${isWIP ? "" : (entry.out_date || "")}" placeholder="DD-MM-YYYY" ${isWIP ? "disabled" : ""} /></td>
      <td><input type="time" value="${isWIP ? "" : (entry.out_time || "")}" ${isWIP ? "disabled" : ""} /></td>
      <td>
        <select>
          ${remarksOptions.map(opt => `<option value="${opt}" ${opt === remarks ? "selected" : ""}>${opt}</option>`).join("")}
        </select>
      </td>
      <td><button type="button" onclick="removeRow(this)">🗑️</button></td>
    `;

    row.querySelectorAll("input, select").forEach(el => {
      el.addEventListener("change", () => handleRemarksChange(row));
    });

    tbody.appendChild(row);
  });

  updateSerialNumbers(citySection);
}

// Modal functions
function openImportModal() {
  document.getElementById("importModal").classList.add("active");
  document.getElementById("imageResultsContainer").style.display = "none";
  document.getElementById("modalFooter").style.display = "none";
  document.getElementById("errorContent").style.display = "none";
}

function closeImportModal() {
  document.getElementById("importModal").classList.remove("active");
}

function showLoading(show) {
  document.getElementById("loadingSpinner").classList.toggle("active", show);
}

function showError(message) {
  document.getElementById("errorMessage").textContent = message;
  document.getElementById("errorContent").style.display = "block";
}

// Convert DD-MM-YYYY to YYYY-MM-DD for date input
function formatDateForInput(dateStr) {
  if (!dateStr) return "";
  // If already in YYYY-MM-DD format
  if (dateStr.length === 10 && dateStr[4] === "-") return dateStr;
  // Convert from DD-MM-YYYY
  const parts = dateStr.split("-");
  if (parts.length === 3 && parts[0].length === 2) {
    return `${parts[2]}-${parts[1]}-${parts[0]}`;
  }
  return dateStr;
}

// Add a new city section from dropdown
function addCitySection() {
  const citySelect = document.getElementById("citySelect");
  const cityName = citySelect?.value || "";
  if (!cityName) {
    alert("Please select a city from the dropdown.");
    return;
  }

  // Prevent duplicate city sections
  const existing = Array.from(document.querySelectorAll(".city-title"))
    .map(el => el.textContent.replace("City: ", ""));
  if (existing.includes(cityName)) {
    alert("City already added.");
    return;
  }

  const section = document.createElement("div");
  section.className = "city-section";
  section.innerHTML = `
    <div class="city-header">
      <div class="city-title">City: ${escapeHtml(cityName)}</div>
      <div class="section-actions">
        <button type="button" onclick="addRow(this)">➕ Add Row</button>
        <button type="button" onclick="clearCityRows(this)">🔄 Clear Rows</button>
        <button type="button" onclick="removeCitySection(this)">🗑️ Remove City</button>
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Sr No</th>
          <th>VRN</th>
          <th>Model</th>
          <th>Entry Date</th>
          <th>In Time</th>
          <th>Out Date</th>
          <th>Out Time</th>
          <th>Remarks</th>
          <th>Remove</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  `;

  const citySectionsContainer = document.getElementById("citySections");

  // Insert the new city section at the beginning (above existing cities)
  if (citySectionsContainer.firstChild) {
    citySectionsContainer.insertBefore(section, citySectionsContainer.firstChild);
  } else {
    citySectionsContainer.appendChild(section);
  }

  createRow(section);
}

function removeCitySection(button) {
  const sectionToRemove = button.closest(".city-section");
  sectionToRemove?.remove();

  // Update serial numbers for all remaining sections to maintain consistency
  document.querySelectorAll(".city-section").forEach(section => {
    updateSerialNumbers(section);
  });
}

function addRow(button) {
  const section = button.closest(".city-section");
  createRow(section);
}

function createRow(section) {
  const tbody = section.querySelector("tbody");
  const rows = tbody.querySelectorAll("tr");
  const nextSerial = rows.length + 1;

  const row = document.createElement("tr");
  row.innerHTML = `
    <td><input type="number" value="${nextSerial}" /></td>
    <td><input type="text" /></td>
    <td><input type="text" /></td>
    <td><input type="text" placeholder="DD-MM-YYYY" /></td>
    <td><input type="time" /></td>
    <td><input type="text" placeholder="DD-MM-YYYY" /></td>
    <td><input type="time" /></td>
    <td>
      <select>
        ${remarksOptions.map(opt => `<option value="${opt}">${opt}</option>`).join("")}
      </select>
    </td>
    <td><button type="button" onclick="removeRow(this)">🗑️</button></td>
  `;

  // Bind input change handlers
  row.querySelectorAll("input, select").forEach(el => {
    el.addEventListener("change", () => {
      handleRemarksChange(row);
      checkLastRow(section);
    });
  });

  // Apply remarks logic initially
  handleRemarksChange(row);

  const globalDate = document.getElementById("globalEntryDate")?.value;
  if (globalDate) {
    const entryDateInput = row.querySelector("td:nth-child(4) input[type='date']");
    const outDateInput = row.querySelector("td:nth-child(6) input[type='date']");
    if (entryDateInput) entryDateInput.value = globalDate;
    if (outDateInput && !outDateInput.disabled) outDateInput.value = globalDate;
  }

  tbody.appendChild(row);
}

function removeRow(button) {
  const row = button.closest("tr");
  const tbody = row.closest("tbody");
  const section = tbody.closest(".city-section");

  row.remove();

  // Update serial numbers after removal
  updateSerialNumbers(section);

  // Only create new row if this was the last row
  if (tbody.children.length === 0) {
    createRow(section);
  }
}

// Clear all rows from a city section
function clearCityRows(button) {
  const section = button.closest(".city-section");
  const tbody = section.querySelector("tbody");
  const cityTitle = section.querySelector(".city-title")?.textContent || "this city";

  if (!confirm(`Clear all rows from ${cityTitle}?`)) {
    return;
  }

  tbody.innerHTML = "";
  // Add one empty row
  createRow(section);
}

function checkLastRow(section) {
  const rows = section.querySelectorAll("tbody tr");
  if (!rows.length) return;
  const last = rows[rows.length - 1];

  // Consider Sr No, VRN, Model, Entry Date, In Time as minimal required to auto-add next row
  const indices = [1, 2, 3, 4, 5];
  let requiredFilled = true;
  for (const idx of indices) {
    const input = last.querySelector(`td:nth-child(${idx}) input`);
    if (!input || !String(input.value).trim()) {
      requiredFilled = false;
      break;
    }
  }
  if (requiredFilled) {
    createRow(section);
    // Serial numbers will be automatically updated in createRow
  }
}

// Validate VRNs for a specific card
async function validateCardVRNs(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const rows = card.querySelectorAll("tbody tr");
  const vrns = [];
  const rowMap = new Map(); // Map VRN to list of rows (in case of duplicates)

  rows.forEach(row => {
    // formatting VRN first to match with user input if needed, 
    // but the backend cleans it anyway. Let's send what is in the input.
    const vrnInput = row.querySelector("td:nth-child(2) input");
    const vrn = vrnInput?.value?.trim();

    if (vrn) {
      vrns.push(vrn);
      if (!rowMap.has(vrn)) {
        rowMap.set(vrn, []);
      }
      rowMap.get(vrn).push(row);
    }
  });

  if (vrns.length === 0) {
    alert("No VRNs found to validate.");
    return;
  }

  // Show loading indication
  const btn = card.querySelector("button[onclick^='validateCardVRNs']");
  const originalText = btn.innerHTML;
  btn.innerHTML = "⏳ Validating...";
  btn.disabled = true;

  try {
    const response = await fetch('/validate_vrn', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ vrns })
    });

    const data = await response.json();

    if (data.status === 'success') {
      const results = data.results;

      // Clear previous validation styles
      card.querySelectorAll(".validation-error").forEach(el => el.classList.remove("validation-error"));
      card.querySelectorAll(".fetched-model-cell").forEach(el => el.innerHTML = "");

      // Apply results
      for (const [vrn, result] of Object.entries(results)) {
        const rows = rowMap.get(vrn);
        if (!rows) continue;

        rows.forEach(row => {
          const vrnInput = row.querySelector("td:nth-child(2) input");
          const modelInput = row.querySelector("td:nth-child(3) input");
          const fetchedModelCell = row.querySelector(".fetched-model-cell");

          if (result.valid) {
            // Valid VRN
            vrnInput.style.backgroundColor = "#e8f5e9"; // Light green
            vrnInput.title = "Valid VRN";

            const fetchedModel = result.model || "Unknown Model";
            const currentModel = modelInput.value.trim();

            let cellContent = `<span class="fetched-model-text" title="${escapeHtml(JSON.stringify(result.details))}">${escapeHtml(fetchedModel)}</span>`;

            // If models differ, show overwrite button
            if (fetchedModel && fetchedModel.toLowerCase() !== currentModel.toLowerCase()) {
              cellContent += `
                 <button type="button" class="overwrite-btn" 
                   onclick="overwriteModel(this, '${escapeHtml(fetchedModel)}')"
                   style="margin-left: 5px; padding: 2px 6px; background: #2196F3; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 11px;">
                   Overwrite
                 </button>
               `;
            }

            fetchedModelCell.innerHTML = cellContent;

          } else {
            // Invalid VRN
            vrnInput.classList.add("validation-error");
            vrnInput.title = result.error || "Invalid VRN";
            fetchedModelCell.innerHTML = `<span style="color: red;">❌ Invalid</span> <button type="button" class="retry-btn" onclick="retrySingleVRN(this)" title="Retry this VRN">🔄</button>`;

            // Show refresh failed button
            const refreshBtn = card.querySelector(".retry-failed-btn");
            if (refreshBtn) refreshBtn.style.display = "inline-block";
          }
        });
      }

      // Check if we should show "Overwrite All" button
      checkOverwriteAllVisibility(card);
    } else {
      alert("Validation failed: " + data.message);
    }

  } catch (error) {
    console.error("Validation error:", error);
    alert("An error occurred during validation.");
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

// Check if "Overwrite All" button should be visible
function checkOverwriteAllVisibility(card) {
  const overwriteBtn = card.querySelector(".overwrite-all-btn");
  if (!overwriteBtn) return;

  const individualOverwriteBtns = card.querySelectorAll(".overwrite-btn");
  if (individualOverwriteBtns.length > 1) {
    overwriteBtn.style.display = "inline-block";
    overwriteBtn.textContent = `⚡ Overwrite All Models (${individualOverwriteBtns.length})`;
  } else {
    overwriteBtn.style.display = "none";
  }
}

// Overwrite all models in the card
function overwriteAllModels(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const buttons = card.querySelectorAll(".overwrite-btn");
  if (buttons.length === 0) {
    alert("No models to overwrite.");
    return;
  }

  if (!confirm(`Overwrite ${buttons.length} models with fetched data?`)) {
    return;
  }

  buttons.forEach(btn => {
    // The onClick handler of the button contains the model string: overwriteModel(this, 'Model Name')
    // We can extract it or simpler: we know the structure.
    // The button is inside .fetched-model-cell, which contains .fetched-model-text
    // Actually, looking at the button generation: onclick="overwriteModel(this, '${escapeHtml(fetchedModel)}')"
    // We can just simulate a click on each button!
    btn.click();
  });

  // Update visibility after clicking
  checkOverwriteAllVisibility(card);
}

// Retry a single failed VRN
async function retrySingleVRN(btn) {
  const row = btn.closest("tr");
  const vrnInput = row.querySelector("td:nth-child(2) input");
  const vrn = vrnInput?.value?.trim();
  const fetchedModelCell = row.querySelector(".fetched-model-cell");

  if (!vrn) return;

  // UI Loading state
  btn.disabled = true;
  btn.classList.add("spinning"); // Add CSS for spinning if desired, or just use text

  try {
    const response = await fetch('/validate_vrn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vrns: [vrn] })
    });

    const data = await response.json();

    if (data.status === 'success' && data.results[vrn]) {
      const result = data.results[vrn];

      if (result.valid) {
        // Success! Update UI
        vrnInput.classList.remove("validation-error");
        vrnInput.style.backgroundColor = "#e8f5e9";
        vrnInput.title = "Valid VRN";

        const modelInput = row.querySelector("td:nth-child(3) input");
        const fetchedModel = result.model || "Unknown Model";
        const currentModel = modelInput.value.trim();

        let cellContent = `<span class="fetched-model-text" title="${escapeHtml(JSON.stringify(result.details))}">${escapeHtml(fetchedModel)}</span>`;

        if (fetchedModel && fetchedModel.toLowerCase() !== currentModel.toLowerCase()) {
          cellContent += `
             <button type="button" class="overwrite-btn" 
               onclick="overwriteModel(this, '${escapeHtml(fetchedModel)}')"
               style="margin-left: 5px; padding: 2px 6px; background: #2196F3; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 11px;">
               Overwrite
             </button>
           `;
        }
        fetchedModelCell.innerHTML = cellContent;
      } else {
        // Still failed
        // Keep the retry button but maybe flash check connectivity/error
        btn.disabled = false;
        btn.classList.remove("spinning");
        vrnInput.title = result.error || "Invalid VRN";
      }
    }
  } catch (error) {
    console.error("Retry error:", error);
    btn.disabled = false;
    btn.classList.remove("spinning");
    alert("Retry failed to connect.");
  }
}

// Retry all failed VRNs in a card
async function retryFailedVRNs(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  // Find all rows with validation errors or explicitly marked failed
  const failedRows = [];
  card.querySelectorAll("tbody tr").forEach(row => {
    if (row.querySelector(".validation-error") || row.querySelector(".retry-btn")) {
      failedRows.push(row);
    }
  });

  if (failedRows.length === 0) {
    alert("No failed rows to retry.");
    return;
  }

  const btn = card.querySelector(".retry-failed-btn");
  const originalText = btn.innerHTML;
  btn.innerHTML = "⏳ Retrying...";
  btn.disabled = true;

  const vrns = [];
  const rowMap = new Map();

  failedRows.forEach(row => {
    const vrnInput = row.querySelector("td:nth-child(2) input");
    const vrn = vrnInput?.value?.trim();
    if (vrn) {
      vrns.push(vrn);
      if (!rowMap.has(vrn)) rowMap.set(vrn, []);
      rowMap.get(vrn).push(row);
    }
  });

  try {
    const response = await fetch('/validate_vrn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vrns })
    });

    const data = await response.json();

    if (data.status === 'success') {
      const results = data.results;
      let stillHasErrors = false;

      for (const [vrn, result] of Object.entries(results)) {
        const rows = rowMap.get(vrn);
        if (!rows) continue;

        rows.forEach(row => {
          const vrnInput = row.querySelector("td:nth-child(2) input");
          const modelInput = row.querySelector("td:nth-child(3) input");
          const fetchedModelCell = row.querySelector(".fetched-model-cell");

          if (result.valid) {
            vrnInput.classList.remove("validation-error");
            vrnInput.style.backgroundColor = "#e8f5e9";
            vrnInput.title = "Valid VRN";

            const fetchedModel = result.model || "Unknown Model";
            const currentModel = modelInput.value.trim();

            let cellContent = `<span class="fetched-model-text" title="${escapeHtml(JSON.stringify(result.details))}">${escapeHtml(fetchedModel)}</span>`;

            if (fetchedModel && fetchedModel.toLowerCase() !== currentModel.toLowerCase()) {
              cellContent += `
                 <button type="button" class="overwrite-btn" 
                   onclick="overwriteModel(this, '${escapeHtml(fetchedModel)}')"
                   style="margin-left: 5px; padding: 2px 6px; background: #2196F3; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 11px;">
                   Overwrite
                 </button>
               `;
            }
            fetchedModelCell.innerHTML = cellContent;
          } else {
            // Still invalid
            stillHasErrors = true;
            // Ensure it looks failed
            vrnInput.classList.add("validation-error");
            fetchedModelCell.innerHTML = `<span style="color: red;">❌ Invalid</span> <button type="button" class="retry-btn" onclick="retrySingleVRN(this)" title="Retry this VRN">🔄</button>`;
          }
        });
      }

      // Toggle refresh button visibility based on if errors remain
      if (!stillHasErrors) {
        btn.style.display = "none";
      }
      checkOverwriteAllVisibility(card); // Update overwrite all button visibility
    }

  } catch (error) {
    console.error("Bulk retry error:", error);
    alert("Error retrying failed validations.");
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

// Overwrite model with fetched value
function overwriteModel(btn, newModel) {
  const row = btn.closest("tr");
  const modelInput = row.querySelector("td:nth-child(3) input");
  if (modelInput) {
    modelInput.value = newModel;
    // Highlight change
    modelInput.style.backgroundColor = "#fff3e0";
    setTimeout(() => {
      modelInput.style.backgroundColor = "";
    }, 2000);

    // Remove the button
    btn.remove();

    // Check if we need to hide the main button (if this was triggered individually)
    const card = row.closest(".image-result-card");
    if (card) checkOverwriteAllVisibility(card);
  }
}

function handleRemarksChange(row) {
  const remarksSel = row.querySelector("td:nth-child(8) select");
  const remarks = remarksSel ? remarksSel.value : "";
  const outDate = row.querySelector("td:nth-child(6) input[type='date']");
  const outTime = row.querySelector("td:nth-child(7) input[type='time']");
  const disable = remarks === "Work In Progress";

  if (outDate) {
    outDate.disabled = disable;
    if (disable) outDate.value = "";
  }
  if (outTime) {
    outTime.disabled = disable;
    if (disable) outTime.value = "";
  }
}

function submitData() {
  const allData = [];

  document.querySelectorAll(".city-section").forEach(section => {
    const cityTitle = section.querySelector(".city-title");
    const city = cityTitle ? cityTitle.textContent.replace("City: ", "") : "";
    section.querySelectorAll("tbody tr").forEach(row => {
      const cells = row.querySelectorAll("td");
      const sr = cells[0].querySelector("input")?.value.trim();
      const vrn = cells[1].querySelector("input")?.value.trim();
      const model = cells[2].querySelector("input")?.value.trim();
      const entryDate = cells[3].querySelector("input")?.value || "";
      const inTime = cells[4].querySelector("input")?.value || "";
      const outDateEl = cells[5].querySelector("input");
      const outTimeEl = cells[6].querySelector("input");
      const remarks = cells[7].querySelector("select")?.value || "";

      // Skip entirely empty rows
      if (!sr && !vrn && !model && !entryDate && !inTime) return;

      allData.push({
        city,
        sr_no: sr || "",
        vrn: vrn || "",
        model: model || "",
        entry_date: entryDate,
        in_time: inTime,
        out_date: outDateEl && !outDateEl.disabled ? (outDateEl.value || "") : "",
        out_time: outTimeEl && !outTimeEl.disabled ? (outTimeEl.value || "") : "",
        remarks
      });
    });
  });

  if (allData.length === 0) {
    alert("No valid rows to submit.");
    return;
  }

  fetch("/save_reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(allData)
  })
    .then(res => res.json())
    .then(data => {
      generateExcel(); // Auto-download Excel after successful submission
    })
    .catch(err => {
      console.error(err);
      alert("Submission failed");
    });
}

function applyGlobalEntryDate() {
  const globalDate = document.getElementById("globalEntryDate")?.value;
  if (!globalDate) return;

  // Update all existing rows
  document.querySelectorAll(".city-section tbody tr").forEach(row => {
    const entryDateInput = row.querySelector("td:nth-child(4) input[type='date']");
    const outDateInput = row.querySelector("td:nth-child(6) input[type='date']");
    if (entryDateInput) entryDateInput.value = globalDate;
    if (outDateInput && !outDateInput.disabled) outDateInput.value = globalDate;
  });
}

function submitAndDownload() {
  const allData = [];

  document.querySelectorAll(".city-section").forEach(section => {
    const city = section.querySelector(".city-title").textContent.replace("City: ", "");
    section.querySelectorAll("tbody tr").forEach(row => {
      const cells = row.querySelectorAll("td");
      const sr = cells[0].querySelector("input")?.value.trim();
      const vrn = cells[1].querySelector("input")?.value.trim();
      const model = cells[2].querySelector("input")?.value.trim();
      const entryDate = cells[3].querySelector("input")?.value;
      const inTime = cells[4].querySelector("input")?.value;
      const outDateEl = cells[5].querySelector("input");
      const outTimeEl = cells[6].querySelector("input");
      const remarks = cells[7].querySelector("select")?.value;

      if (!sr && !vrn && !model && !entryDate && !inTime) return;

      allData.push({
        city,
        sr_no: sr,
        vrn,
        model,
        entry_date: entryDate,
        in_time: inTime,
        out_date: outDateEl && !outDateEl.disabled ? outDateEl.value : "",
        out_time: outTimeEl && !outTimeEl.disabled ? outTimeEl.value : "",
        remarks
      });
    });
  });

  if (allData.length === 0) {
    alert("No valid rows to submit.");
    return;
  }

  // Submit to DB first
  fetch("/save_reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(allData)
  })
    .then(res => res.json())
    .then(data => {
      alert(data.status || "Submitted");
      generateExcel(); // Then trigger Excel download
    })
    .catch(err => {
      console.error(err);
      alert("Submission failed");
    });
}

// Auto-save functionality for individual row changes
row.querySelectorAll("input, select").forEach(el => {
  el.addEventListener("change", () => {
    const cells = row.querySelectorAll("td");
    const city = section.querySelector(".city-title").textContent.replace("City: ", "");
    const sr = cells[0].querySelector("input")?.value.trim();
    const vrn = cells[1].querySelector("input")?.value.trim();
    const model = cells[2].querySelector("input")?.value.trim();
    const entryDate = cells[3].querySelector("input")?.value;
    const inTime = cells[4].querySelector("input")?.value;
    const outDateEl = cells[5].querySelector("input");
    const outTimeEl = cells[6].querySelector("input");
    const remarks = cells[7].querySelector("select")?.value;

    if (!sr && !vrn && !model && !entryDate && !inTime) return;

    const payload = {
      city,
      sr_no: sr,
      vrn,
      model,
      entry_date: entryDate,
      in_time: inTime,
      out_date: outDateEl && !outDateEl.disabled ? outDateEl.value : "",
      out_time: outTimeEl && !outTimeEl.disabled ? outTimeEl.value : "",
      remarks
    };

    fetch("/save_reports_row", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => console.log("Auto-saved:", data.status))
      .catch(err => console.error("Auto-save failed:", err));
  });
});

function generateExcel() {
  const wb = XLSX.utils.book_new();
  const rows = [["Sr No", "VRN", "Model", "Entry Date", "In Time", "Out Date", "Out Time", "Remarks"]];

  let firstEntryDate = "";
  const allData = [];

  document.querySelectorAll(".city-section").forEach(section => {
    const city = section.querySelector(".city-title").textContent.replace("City: ", "");
    const cityRows = [];

    section.querySelectorAll("tbody tr").forEach(row => {
      const cells = row.querySelectorAll("td");

      const sr = cells[0].querySelector("input")?.value.trim() || "";
      const vrn = cells[1].querySelector("input")?.value.trim() || "";
      const model = cells[2].querySelector("input")?.value.trim() || "";

      // Entry date is now a text input, not date type
      const entryDate = cells[3].querySelector("input")?.value.trim() || "";
      if (!firstEntryDate && entryDate) firstEntryDate = entryDate;

      const inTimeRaw = cells[4].querySelector("input[type='time']")?.value || "";
      const inTime = formatTime12(inTimeRaw);

      // Out date and time are now text/time inputs
      const outDateEl = cells[5].querySelector("input");
      const outTimeEl = cells[6].querySelector("input[type='time']");
      const outDate = outDateEl && !outDateEl.disabled ? (outDateEl.value.trim() || "") : "";
      const outTimeRaw = outTimeEl && !outTimeEl.disabled ? (outTimeEl.value || "") : "";
      const outTime = formatTime12(outTimeRaw);

      const remarks = cells[7].querySelector("select")?.value || "";

      if (!sr && !vrn && !model && !entryDate && !inTimeRaw) return;

      cityRows.push([sr, vrn, model, entryDate, inTime, outDate, outTime, remarks]);
    });

    if (cityRows.length > 0) {
      rows.push([city]); // City label row
      rows.push(...cityRows); // Data rows
    }
  });

  const ws = XLSX.utils.aoa_to_sheet(rows);
  XLSX.utils.book_append_sheet(wb, ws, "Vehicle Reports");

  let formattedDate = "unknown";
  if (firstEntryDate) {
    const parts = firstEntryDate.split("-");
    if (parts.length === 3) {
      formattedDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
    }
  }

  const filename = `Vehicle_report_${formattedDate}.xlsx`;
  XLSX.writeFile(wb, filename);
}
