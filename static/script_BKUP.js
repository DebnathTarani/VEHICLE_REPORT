// Configuration
const remarksOptions = ["Work Done", "Work In Progress"];

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

// Initialization
window.addEventListener("DOMContentLoaded", () => {
  const addBtn = document.getElementById("addCityBtn");
  const submitBtn = document.getElementById("submitBtn");
  //const excelBtn = document.getElementById("downloadExcelBtn")?.addEventListener("click", generateExcel);
 const excelBtn = document.getElementById("downloadExcelBtn")?.addEventListener("click", submitData);
  if (addBtn) addBtn.addEventListener("click", addCitySection);
  if (submitBtn) submitBtn.addEventListener("click", submitData);
  //if (excelBtn) excelBtn.addEventListener("click", generateExcel);
  if (excelBtn) excelBtn.addEventListener("click", submitData);
});

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
  document.getElementById("citySections").appendChild(section);
  createRow(section);
}

function removeCitySection(button) {
  button.closest(".city-section")?.remove();
}

function addRow(button) {
  const section = button.closest(".city-section");
  createRow(section);
}

function createRow(section) {
  const tbody = section.querySelector("tbody");
  const row = document.createElement("tr");
  row.innerHTML = `
    <td><input type="number" /></td>
    <td><input type="text" /></td>
    <td><input type="text" /></td>
    <td><input type="date" /></td>
    <td><input type="time" /></td>
    <td><input type="date" /></td>
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
  row.remove();
  if (tbody.children.length === 0) createRow(tbody.closest(".city-section"));
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
  if (requiredFilled) createRow(section);
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
     // alert(data.status || "Submitted");
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

      const entryDateEl = cells[3].querySelector("input[type='date']");
      const entryDate = entryDateEl?.value || "";
      if (!firstEntryDate && entryDate) firstEntryDate = entryDate;

      const inTimeRaw = cells[4].querySelector("input[type='time']")?.value || "";
      const inTime = formatTime12(inTimeRaw);

      const outDateEl = cells[5].querySelector("input[type='date']");
      const outTimeEl = cells[6].querySelector("input[type='time']");
      const outDate = outDateEl && !outDateEl.disabled ? (outDateEl.value || "") : "";
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

