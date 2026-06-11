# Vehicle Report Application - Complete Project Documentation

## 📋 Project Overview

**Project Name:** Vehicle Report Application  
**Technology Stack:** Flask (Python) + HTML/CSS/JavaScript  
**Database:** SQLite (`vehicle_reports.db`)  
**Primary Purpose:** A web-based vehicle reporting system for tracking vehicle entries/exits across multiple locations

---

## 🏗️ Project Structure

```
TEST_VEHICLE_REPORT/
│
├── app.py                    # Main Flask application (Backend)
├── app.py_BKUP               # Backup of app.py
├── app_windows.py            # Windows-specific version of app
├── app.spec                  # PyInstaller specification file
├── requirements.txt          # Python dependencies
├── render.yaml               # Render deployment configuration
├── START.bat                 # Windows batch file to launch app
├── vehicle_reports.db        # SQLite database file
│
├── static/                   # Static assets
│   ├── script.js             # Main JavaScript file
│   ├── script_BKUP.js        # Backup of script.js
│   ├── script_bkp_srd.js     # Another script backup
│   ├── minimal.js            # Minimal JavaScript version
│   ├── xlsx.full.min.js      # SheetJS library for Excel export
│   └── Vehicle_report_*.xlsx # Sample/generated Excel files
│
└── templates/                # Jinja2 HTML templates
    ├── index.html            # Main entry form page
    ├── index.html_BKP        # Backup of index.html
    ├── index.html_VOICE      # Voice-enabled version
    └── logs.html             # View logs/reports page
```

---

## 🖥️ Backend Details (app.py)

### Flask Application Configuration
- **Port:** 5010 (configurable via `PORT` environment variable)
- **Host:** `0.0.0.0` (accessible from any network interface)
- **Debug Mode:** Enabled (`debug=True`)
- **Auto-Reload:** Disabled (`use_reloader=False`)

### Database Schema

**Table: `vehicle_reports`**

| Column      | Type    | Constraints          | Description                |
|-------------|---------|----------------------|----------------------------|
| id          | INTEGER | PRIMARY KEY, AUTO    | Unique identifier          |
| city        | TEXT    | NOT NULL             | City/location name         |
| sr_no       | INTEGER |                      | Serial number              |
| vrn         | TEXT    |                      | Vehicle Registration Number|
| model       | TEXT    |                      | Vehicle model              |
| entry_date  | TEXT    |                      | Entry date (DD-MM-YYYY)    |
| in_time     | TEXT    |                      | Check-in time              |
| out_date    | TEXT    |                      | Exit date (DD-MM-YYYY)     |
| out_time    | TEXT    |                      | Check-out time             |
| remarks     | TEXT    |                      | Status/notes               |

### API Endpoints

| Route                        | Method | Description                                      |
|------------------------------|--------|--------------------------------------------------|
| `/`                          | GET    | Serves the main entry form (index.html)          |
| `/save_reports`              | POST   | Bulk save vehicle reports to database            |
| `/save_reports_row`          | POST   | Save a single vehicle report row                 |
| `/generate_excel_and_email`  | POST   | Generate Excel file and launch Outlook email     |
| `/view_logs`                 | GET    | View all vehicle reports in tabular format       |
| `/view_by_date/<entry_date>` | GET    | Filter reports by specific entry date            |
| `/convert_existing_dates`    | GET    | Utility to convert dates from YYYY-MM-DD to DD-MM-YYYY |
| `/debug_db`                  | GET    | Debug endpoint showing database structure & data |

### Key Features

1. **Date Format Handling**
   - Stores dates in DD-MM-YYYY format
   - Utility functions: `format_date_for_display()` and `format_date_for_storage()`
   - Automatic conversion from YYYY-MM-DD (HTML date input) to DD-MM-YYYY

2. **Outlook Integration (Windows Only)**
   - Uses `win32com.client` for Outlook automation
   - Automatically creates email with Excel attachment
   - Gracefully disabled on non-Windows systems

3. **Excel Generation**
   - Uses `openpyxl` library
   - Generates timestamped Excel files (`vehicle_report_DD-MM-YYYY.xlsx`)

---

## 🌐 Frontend Details

### Main Entry Form (index.html)

**Features:**
- City selection dropdown with predefined locations:
  - Hailakandi, Karimganj, Kalain, Jhapirbond, Sildubi, Fulertal, Budrail_Yard
- Global entry date picker (applies to all rows)
- Dynamic city sections (add/remove cities)
- Row-by-row data entry
- Export to Excel functionality
- View logs in new tab

**Action Buttons:**
- ➕ Add City - Add new city section
- 📤 Submit to DB - Save all data to database
- 📥 Save & Download Excel - Export data to Excel file
- 📊 View Logs - Open logs page in new tab
- 🔍 View Logs by Date - Filter logs by specific date

### Logs View (logs.html)

**Features:**
- Tabular display of all vehicle records
- Columns: ID, City, Sr No, VRN, Model, Entry Date, In Time, Out Date, Out Time, Remarks
- Optional date filtering via URL parameter
- Jinja2 templating for dynamic data rendering

### JavaScript Functionality (script.js)

**Key Functions:**

| Function                | Description                                           |
|-------------------------|-------------------------------------------------------|
| `addCitySection()`      | Creates new city section from dropdown selection      |
| `removeCitySection()`   | Removes a city section                                |
| `createRow()`           | Adds a new data entry row to a city section           |
| `removeRow()`           | Removes a specific row and updates serial numbers     |
| `updateSerialNumbers()` | Re-numbers rows after additions/deletions             |
| `submitData()`          | Collects all data and POSTs to `/save_reports`        |
| `generateExcel()`       | Client-side Excel generation using SheetJS            |
| `formatTime12()`        | Converts 24-hour time to 12-hour AM/PM format         |
| `handleRemarksChange()` | Disables out date/time when "Work In Progress"        |
| `applyGlobalEntryDate()`| Applies global date to all rows                       |
| `viewLogsByDate()`      | Opens filtered logs view by date                      |

**Remarks Options:**
- "Work Done" - Out date/time fields enabled
- "Work In Progress" - Out date/time fields disabled and cleared

**Auto-Features:**
- Auto-add new row when required fields are filled
- Auto-save on field changes
- Serial number auto-management

---

## 📦 Dependencies (requirements.txt)

### Core Dependencies
| Package   | Purpose                           |
|-----------|-----------------------------------|
| flask     | Web framework                     |
| openpyxl  | Excel file generation (server)   |
| sqlite3   | Database (built-in Python)       |

### Windows-Specific (Optional)
| Package      | Purpose                        |
|--------------|--------------------------------|
| pywin32      | Outlook automation (win32com)  |

### Client-Side Libraries
| Library          | Purpose                        |
|------------------|--------------------------------|
| xlsx.full.min.js | SheetJS - Client-side Excel    |

---

## 🚀 Deployment Options

### 1. Local Development
```bash
# Run directly
python app.py

# Or use the Windows batch file
START.bat
```
Server runs at: `http://localhost:5010`

### 2. Render Cloud Platform
Configuration in `render.yaml`:
- **Type:** Web service
- **Name:** vehicle-report
- **Environment:** Python
- **Start Command:** `python app.py`
- **Plan:** Free tier

### 3. PyInstaller Executable
The `app.spec` file allows building a standalone Windows executable:
```bash
pyinstaller app.spec
```

---

## 🔧 Configuration

### Port Configuration
The application port can be configured via environment variable:
```bash
export PORT=5010  # Default: 5010
```

### SSL Configuration (Commented)
SSL support is available but commented out:
```python
# app.run(host='0.0.0.0', port=5010, ssl_context=('cert.pem', 'key.pem'))
```

---

## 📊 Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   User Input    │────▶│   JavaScript     │────▶│   Flask API     │
│   (HTML Form)   │     │   (script.js)    │     │   (app.py)      │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Excel Download │◀────│  SheetJS/OpenPyXL│◀────│   SQLite DB     │
│   (.xlsx file)  │     │                  │     │ (vehicle_reports)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

---

## 🛠️ Debug Endpoints

### `/debug_db` - Database Diagnostics
Returns JSON with:
- `table_structure` - Column definitions
- `recent_entries` - Last 5 records
- `total_records` - Total count
- `db_exists` - Database file existence check

### `/convert_existing_dates` - Date Migration
Converts any dates stored in YYYY-MM-DD format to DD-MM-YYYY format.

---

## 📝 Usage Instructions

### Adding a Vehicle Entry
1. Select a date using "Entry Date" picker (optional - applies globally)
2. Choose a city from the dropdown
3. Click "➕ Add City" to create a city section
4. Fill in vehicle details:
   - Sr No (auto-generated)
   - VRN (Vehicle Registration Number)
   - Model
   - Entry Date
   - In Time
   - Out Date (disabled if "Work In Progress")
   - Out Time (disabled if "Work In Progress")
   - Remarks (Work Done / Work In Progress)
5. Click "📤 Submit to DB" to save data
6. Click "📥 Save & Download Excel" to export

### Viewing Reports
1. Click "📊 View Logs" to see all entries
2. Use date filter and "🔍 View Logs by Date" for specific dates

---

## 📁 Backup Files

The project maintains backup copies of critical files:
- `app.py_BKUP` - Backend backup
- `script_BKUP.js` - JavaScript backup
- `script_bkp_srd.js` - Another JavaScript backup (SRD version)
- `index.html_BKP` - Template backup
- `index.html_VOICE` - Voice-enabled experimental version

---

## 🔒 Security Considerations

1. **Debug Mode Warning:** Debug mode is enabled (`debug=True`), which should be disabled in production
2. **No Authentication:** The application has no user authentication
3. **SQL Injection:** The app uses parameterized queries, which is secure
4. **CORS:** No CORS restrictions configured
5. **Input Validation:** Minimal input validation on the backend

---

## 📈 Future Enhancements (Suggested)

1. Add user authentication
2. Implement data validation on backend
3. Add edit/delete functionality for existing records
4. Add pagination for logs view
5. Implement data export in multiple formats (PDF, CSV)
6. Add search functionality
7. Disable debug mode in production
8. Add logging for error tracking

---

*Documentation generated on: February 7, 2026*
