from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import datetime
import base64
import json
import re
import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AI Provider Configuration
AI_PROVIDER = None  # 'vllm' or 'gemini'
AI_CONFIG = {}

# Check for vLLM (local) first - prioritize local
VLLM_ENABLED = os.getenv('VLLM_ENABLED', 'false').lower() == 'true'
VLLM_HOST = os.getenv('VLLM_HOST', 'http://localhost:8000')
VLLM_MODEL = os.getenv('VLLM_MODEL', 'nvidia/NVIDIA-Nemotron-Parse-v1.1')

# Option 3: llama.cpp (OpenAI-compatible)
LLAMACPP_ENABLED = os.getenv('LLAMACPP_ENABLED', 'false').lower() == 'true'
LLAMACPP_HOST = os.getenv('LLAMACPP_HOST', 'http://localhost:8080')
LLAMACPP_MODEL = os.getenv('LLAMACPP_MODEL', 'Llama-3.2-11B-Vision-Instruct')

# Thinking mode configuration
AI_DISABLE_THINKING = os.getenv('AI_DISABLE_THINKING', 'false').lower() == 'true'

if VLLM_ENABLED:
    # Test vLLM connection (OpenAI-compatible API)
    try:
        response = requests.get(f"{VLLM_HOST}/v1/models", timeout=5)
        if response.status_code == 200:
            AI_PROVIDER = 'vllm'
            AI_CONFIG = {'host': VLLM_HOST, 'model': VLLM_MODEL}
            print(f"✅ vLLM enabled at {VLLM_HOST} with model: {VLLM_MODEL}")
        else:
            print(f"⚠️ vLLM not responding at {VLLM_HOST}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Cannot connect to vLLM at {VLLM_HOST}: {e}")

# Check for llama.cpp if vLLM not available
if AI_PROVIDER is None and LLAMACPP_ENABLED:
    try:
        response = requests.get(f"{LLAMACPP_HOST}/v1/models", timeout=5)
        if response.status_code == 200:
            AI_PROVIDER = 'llamacpp'
            AI_CONFIG = {'host': LLAMACPP_HOST, 'model': LLAMACPP_MODEL}
            print(f"✅ llama.cpp enabled at {LLAMACPP_HOST} with model: {LLAMACPP_MODEL}")
        else:
            print(f"⚠️ llama.cpp not responding at {LLAMACPP_HOST}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Cannot connect to llama.cpp at {LLAMACPP_HOST}: {e}")

# Fall back to Gemini if vLLM not available
if AI_PROVIDER is None:
    try:
        import google.generativeai as genai
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        if GOOGLE_API_KEY and GOOGLE_API_KEY != 'your_gemini_api_key_here':
            genai.configure(api_key=GOOGLE_API_KEY)
            AI_PROVIDER = 'gemini'
            AI_CONFIG = {'genai': genai}
            print("✅ Gemini AI enabled")
        else:
            print("⚠️ No AI provider configured. Set VLLM_ENABLED=true or add GOOGLE_API_KEY")
    except ImportError:
        print("⚠️ google-generativeai not installed, Gemini unavailable")

AI_ENABLED = AI_PROVIDER is not None
print(f"AI Provider: {AI_PROVIDER or 'None'}")
print(f"AI Thinking: {'Disabled' if AI_DISABLE_THINKING else 'Enabled'}")


# Only import win32com if running on Windows with Outlook
try:
    import win32com.client
    OUTLOOK_ENABLED = True
except ImportError:
    OUTLOOK_ENABLED = False

app = Flask(__name__)
DB_NAME = 'vehicle_reports.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if table exists and has correct structure
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vehicle_reports'")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        # Create new table with proper schema
        cursor.execute('''
            CREATE TABLE vehicle_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL,
                sr_no INTEGER,
                vrn TEXT,
                model TEXT,
                entry_date TEXT,
                in_time TEXT,
                out_date TEXT,
                out_time TEXT,
                remarks TEXT
            )
        ''')
        print("Created new vehicle_reports table")
    conn.commit()
    conn.close()

def format_date_for_display(date_str):
    """Ensure date is in DD-MM-YYYY format for display"""
    if not date_str:
        return ""
    try:
        # If already in DD-MM-YYYY format, return as is
        if len(date_str) == 10 and date_str[2] == '-' and date_str[5] == '-':
            return date_str
        # Convert from YYYY-MM-DD to DD-MM-YYYY
        parts = date_str.split('-')
        if len(parts) == 3 and len(parts[0]) == 4:  # YYYY-MM-DD format
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_str
    except:
        return date_str

def format_date_for_storage(date_str):
    """Ensure date is in DD-MM-YYYY format for storage"""
    if not date_str:
        return ""
    try:
        # If already in DD-MM-YYYY format, return as is
        if len(date_str) == 10 and date_str[2] == '-' and date_str[5] == '-':
            return date_str
        # Convert from YYYY-MM-DD to DD-MM-YYYY
        parts = date_str.split('-')
        if len(parts) == 3 and len(parts[0]) == 4:  # YYYY-MM-DD format
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_str
    except:
        return date_str

def extract_json_from_response(response_text):
    """Extract JSON from AI model response, handling thinking tags and extra text"""
    if not response_text:
        raise ValueError("Empty response from AI model")

    text = response_text

    # Remove <think>...</think> tags and their content
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Remove <reasoning>...</reasoning> tags and their content
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)

    text = text.strip()

    # Remove markdown code block fences
    if text.startswith('```'):
        end_index = text.find('\n', 3)
        if end_index != -1:
            text = text[end_index:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

    # Try direct parse first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Find JSON array or object start
    json_start = -1
    for i, c in enumerate(text):
        if c in '[{':
            json_start = i
            break

    if json_start == -1:
        raise ValueError("No JSON array or object found in AI response")

    json_str = text[json_start:]

    # Try parsing the entire substring
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass

    # Bracket matching for precise JSON extraction
    if json_str[0] == '[':
        depth = 0
        for i, c in enumerate(json_str):
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    result = json_str[:i + 1]
                    json.loads(result)
                    return result
    elif json_str[0] == '{':
        depth = 0
        for i, c in enumerate(json_str):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    result = json_str[:i + 1]
                    json.loads(result)
                    return result

    raise ValueError("Could not extract valid JSON from AI response")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save_reports', methods=['POST'])
def save_reports():
    data = request.json
    print("=== DEBUG save_reports ===")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for entry in data:
        # Convert dates to DD-MM-YYYY format for storage
        entry_date = format_date_for_storage(entry['entry_date'])
        out_date = format_date_for_storage(entry['out_date'])
        
        print(f"Original - Entry: {entry['entry_date']}, Out: {entry['out_date']}")
        print(f"Stored   - Entry: {entry_date}, Out: {out_date}")
        
        cursor.execute('''
            INSERT INTO vehicle_reports 
            (city, sr_no, vrn, model, entry_date, in_time, out_date, out_time, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry['city'],
            int(entry['sr_no']) if entry['sr_no'] and entry['sr_no'].strip() else None,
            entry['vrn'],
            entry['model'],
            entry_date,  # Now stored as DD-MM-YYYY
            entry['in_time'],
            out_date,    # Now stored as DD-MM-YYYY
            entry['out_time'],
            entry['remarks']
        ))
        print(f"Inserted record with ID: {cursor.lastrowid}")
    
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/generate_excel_and_email', methods=['POST'])
def generate_excel_and_email():
    data = request.json
    if not data:
        return jsonify({'status': 'No data received'}), 400

    # Format entry date for filename and display
    raw_entry_date = data[0].get("entry_date", str(datetime.date.today()))
    formatted_entry_date = format_date_for_display(raw_entry_date)
    filename = f"vehicle_report_{formatted_entry_date}.xlsx"
    filepath = os.path.join(os.getcwd(), filename)

    # Generate Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Vehicle Report"
    headers = ["City", "SR No", "VRN", "Model", "Entry Date", "In Time", "Out Date", "Out Time", "Remarks"]
    ws.append(headers)

    for entry in data:
        # Format dates for Excel display (already in DD-MM-YYYY)
        entry_date_display = format_date_for_display(entry['entry_date'])
        out_date_display = format_date_for_display(entry['out_date'])
        
        ws.append([
            entry['city'],
            entry['sr_no'],
            entry['vrn'],
            entry['model'],
            entry_date_display,
            entry['in_time'],
            out_date_display,
            entry['out_time'],
            entry['remarks']
        ])

    wb.save(filepath)

    # Launch Outlook email
    if OUTLOOK_ENABLED:
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = "audit@company.com; manager@company.com"
            mail.Subject = f"Vehicle Report - {formatted_entry_date}"
            mail.Body = f"Hi,\n\nPlease find the attached vehicle report for {formatted_entry_date}.\n\nRegards,\nSushanta"
            mail.Attachments.Add(os.path.abspath(filepath))
            mail.Display()
        except Exception as e:
            print("Outlook launch failed:", e)
            return jsonify({'status': 'Excel generated, but email failed'})

    return jsonify({'status': 'Excel generated and email launched'})

@app.route('/view_logs')
def view_logs():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM vehicle_reports ORDER BY entry_date DESC, city, sr_no')
    rows = cursor.fetchall()
    conn.close()
    
    print("=== DEBUG view_logs ===")
    for row in rows:
        print(f"DB Row: {row}")
    
    # Format dates for display (ensure they're in DD-MM-YYYY)
    formatted_rows = []
    for row in rows:
        row_list = list(row)
        # Format entry_date (index 5) and out_date (index 7)
        row_list[5] = format_date_for_display(row_list[5])  # entry_date
        row_list[7] = format_date_for_display(row_list[7])  # out_date
        formatted_rows.append(tuple(row_list))
        print(f"Formatted: {tuple(row_list)}")
    
    return render_template('logs.html', entries=formatted_rows, filter_date=None)

@app.route('/view_by_date/<entry_date>')
def view_by_date(entry_date):
    # Convert input date to storage format for query (DD-MM-YYYY)
    entry_date_storage = format_date_for_storage(entry_date)
    
    print(f"=== DEBUG view_by_date ===")
    print(f"Input date: {entry_date}, Query date: {entry_date_storage}")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM vehicle_reports
        WHERE entry_date = ?
        ORDER BY city, sr_no
    ''', (entry_date_storage,))
    rows = cursor.fetchall()
    conn.close()
    
    print(f"Found {len(rows)} rows for date {entry_date_storage}")
    
    # Format dates for display
    formatted_rows = []
    for row in rows:
        row_list = list(row)
        # Format entry_date (index 5) and out_date (index 7)
        row_list[5] = format_date_for_display(row_list[5])  # entry_date
        row_list[7] = format_date_for_display(row_list[7])  # out_date
        formatted_rows.append(tuple(row_list))
    
    return render_template('logs.html', entries=formatted_rows, filter_date=entry_date)

@app.route('/save_reports_row', methods=['POST'])
def save_reports_row():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'No data received'}), 400

    # Convert dates to DD-MM-YYYY format for storage
    entry_date = format_date_for_storage(data['entry_date'])
    out_date = format_date_for_storage(data['out_date'])

    print(f"Single row - Raw: {data['entry_date']} -> Stored: {entry_date}")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO vehicle_reports (city, sr_no, vrn, model, entry_date, in_time, out_date, out_time, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['city'],
        data['sr_no'],
        data['vrn'],
        data['model'],
        entry_date,
        data['in_time'],
        out_date,
        data['out_time'],
        data['remarks']
    ))
    conn.commit()
    print(f"Inserted single row with ID: {cursor.lastrowid}")
    conn.close()
    return jsonify({'status': 'Row saved'})

@app.route('/convert_existing_dates')
def convert_existing_dates():
    """Route to convert existing YYYY-MM-DD dates to DD-MM-YYYY format"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get all records
    cursor.execute('SELECT * FROM vehicle_reports')
    rows = cursor.fetchall()
    
    updated_count = 0
    for row in rows:
        row_id, city, sr_no, vrn, model, entry_date, in_time, out_date, out_time, remarks = row
        
        # Check if dates are in YYYY-MM-DD format and convert them
        new_entry_date = format_date_for_storage(entry_date)
        new_out_date = format_date_for_storage(out_date)
        
        if entry_date != new_entry_date or out_date != new_out_date:
            cursor.execute('''
                UPDATE vehicle_reports 
                SET entry_date = ?, out_date = ?
                WHERE id = ?
            ''', (new_entry_date, new_out_date, row_id))
            updated_count += 1
            print(f"Updated row {row_id}: {entry_date} -> {new_entry_date}, {out_date} -> {new_out_date}")
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': f'Updated {updated_count} records to DD-MM-YYYY format'})

@app.route('/debug_db')
def debug_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get table structure
    cursor.execute("PRAGMA table_info(vehicle_reports)")
    table_info = cursor.fetchall()
    
    # Get recent entries
    cursor.execute('SELECT * FROM vehicle_reports ORDER BY id DESC LIMIT 5')
    recent_entries = cursor.fetchall()
    
    # Count total records
    cursor.execute('SELECT COUNT(*) FROM vehicle_reports')
    total_records = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'table_structure': table_info,
        'recent_entries': recent_entries,
        'total_records': total_records,
        'db_exists': os.path.exists(DB_NAME)
    })

@app.route('/extract_from_image', methods=['POST'])
def extract_from_image():
    """Extract vehicle data from uploaded image using AI"""
    if not AI_ENABLED:
        return jsonify({
            'status': 'error',
            'message': 'AI extraction not configured. Enable Ollama or add GOOGLE_API_KEY in .env file.'
        }), 400

    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': 'No image file provided'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'status': 'error', 'message': 'No image selected'}), 400

    # Read per-request thinking toggle from frontend (overrides env default)
    disable_thinking = request.form.get('disable_thinking', '').lower() == 'true'
    if not disable_thinking:
        disable_thinking = AI_DISABLE_THINKING

    try:
        image_data = image_file.read()
        image_b64 = base64.b64encode(image_data).decode('utf-8')

        prompt = """Analyze this image of a vehicle register/log and extract all vehicle entries.

For each vehicle entry found, extract:
- sr_no: Serial number
- vrn: Vehicle Registration Number
- model: Vehicle model/make
- entry_date: Entry date (convert to DD-MM-YYYY format)
- in_time: Check-in time (24-hour format like 10:30)
- out_date: Exit date if visible (DD-MM-YYYY format)
- out_time: Check-out time if visible (24-hour format)
- remarks: Any notes/status (use "Work Done" if vehicle has exited, "Work In Progress" if still there)

Return the data as a JSON array. Example format:
[
  {"sr_no": "1", "vrn": "AS-01-AB-1234", "model": "Maruti Swift", "entry_date": "07-02-2026", "in_time": "10:30", "out_date": "07-02-2026", "out_time": "16:00", "remarks": "Work Done"},
  {"sr_no": "2", "vrn": "AS-02-CD-5678", "model": "Honda City", "entry_date": "07-02-2026", "in_time": "11:15", "out_date": "", "out_time": "", "remarks": "Work In Progress"}
]

IMPORTANT: Return ONLY the JSON array, no other text or markdown formatting."""

        response_text = None

        if AI_PROVIDER == 'vllm':
            body = {
                "model": AI_CONFIG['model'],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_file.content_type or 'image/jpeg'};base64,{image_b64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 4096
            }
            if disable_thinking:
                body["enable_thinking"] = False

            vllm_response = requests.post(
                f"{AI_CONFIG['host']}/v1/chat/completions",
                json=body,
                timeout=120
            )

            if vllm_response.status_code != 200:
                raise Exception(f"vLLM error: {vllm_response.text}")

            response_text = vllm_response.json()['choices'][0]['message']['content'].strip()

        elif AI_PROVIDER == 'llamacpp':
            body = {
                "model": AI_CONFIG['model'],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_file.content_type or 'image/jpeg'};base64,{image_b64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 4096
            }
            if disable_thinking:
                body["enable_thinking"] = False

            llamacpp_response = requests.post(
                f"{AI_CONFIG['host']}/v1/chat/completions",
                json=body,
                timeout=120
            )

            if llamacpp_response.status_code != 200:
                raise Exception(f"llama.cpp error: {llamacpp_response.text}")

            response_text = llamacpp_response.json()['choices'][0]['message']['content'].strip()

        elif AI_PROVIDER == 'gemini':
            genai = AI_CONFIG['genai']
            model = genai.GenerativeModel('gemini-1.5-flash')

            response = model.generate_content([
                prompt,
                {
                    "mime_type": image_file.content_type or "image/jpeg",
                    "data": image_b64
                }
            ])
            response_text = response.text.strip()

        # Robust JSON extraction (handles thinking tags, markdown, extra text)
        cleaned_json = extract_json_from_response(response_text)
        extracted_data = json.loads(cleaned_json)

        return jsonify({
            'status': 'success',
            'data': extracted_data,
            'count': len(extracted_data),
            'provider': AI_PROVIDER,
            'thinking_disabled': disable_thinking
        })

    except json.JSONDecodeError as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to parse AI response: {str(e)}',
            'raw_response': response_text if response_text else None
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Image processing failed: {str(e)}'
        }), 500

def check_vrn_details(rc_number):
    """
    Fetch vehicle details from vahanx.in for a given RC number.
    Returns a dictionary with status and details.
    """
    try:
        home_url = 'https://vahanx.in/rc-search'
        # Clean the RC number
        clean_rc = rc_number.replace(" ", "").replace("-", "").replace(".", "").upper()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # The site structure suggests a GET request to /rc-search/{number}
        r = requests.get(url=f'{home_url}/{clean_rc}', headers=headers, timeout=10)
        
        if r.status_code != 200:
            return {'valid': False, 'error': f'HTTP {r.status_code}'}
            
        soup = BeautifulSoup(r.content, 'html.parser')
        details = {}
        
        # Check if we got a valid result page
        # The user's script checks for ownership_section. 
        # If it's missing, it prints "No ownership details found"
        
        ownership_section = soup.find('h3', string='Ownership Details')
        if not ownership_section:
            return {'valid': False, 'error': 'No details found'}

        # Scrape details as per user's script
        
        # Header/Summary Info
        header_card = soup.find('div', class_='hrc-details-card')
        if header_card:
            code_elem = header_card.find('span', string='Code')
            if code_elem:
                details['Code'] = code_elem.find_previous_sibling('p').text.strip()
            city_elem = header_card.find('span', string='City Name')
            if city_elem:
                details['City Name'] = city_elem.find_previous_sibling('p').text.strip()

        # Ownership Details
        if ownership_section:
            ownership_card = ownership_section.find_parent('div', class_='hrc-details-card')
            if ownership_card:
                 for item in ownership_card.find_all('div', class_='col-sm-6'):
                    label = item.find('span', class_='text-muted')
                    value = item.find('p', class_='fw-semibold')
                    if label and value:
                        details[label.text.strip()] = value.text.strip()

        # Vehicle Details
        vehicle_section = soup.find('h3', string='Vehicle Details')
        if vehicle_section:
            vehicle_card = vehicle_section.find_parent('div', class_='hrc-details-card')
            if vehicle_card:
                 for item in vehicle_card.find_all('div', class_='col-sm-6'):
                    label = item.find('span', class_='text-muted')
                    value = item.find('p', class_='fw-semibold')
                    if label and value:
                        details[label.text.strip()] = value.text.strip()
        
        # Extract model specifically
        model = details.get('Maker Model', '')
        
        return {
            'valid': True, 
            'model': model, 
            'details': details
        }
        
    except Exception as e:
        print(f"Error checking VRN {rc_number}: {e}")
        return {'valid': False, 'error': str(e)}

@app.route('/validate_vrn', methods=['POST'])
def validate_vrn():
    data = request.json
    if not data or 'vrns' not in data:
        return jsonify({'status': 'error', 'message': 'No VRNs provided'}), 400
        
    vrns = data['vrns'] # List of VRN strings
    results = {}
    
    for vrn in vrns:
        if not vrn:
            continue
        results[vrn] = check_vrn_details(vrn)
        
    return jsonify({
        'status': 'success',
        'results': results
    })

@app.route('/check_ai_status')
def check_ai_status():
    """Check if AI extraction is available"""
    return jsonify({
        'gemini_enabled': AI_ENABLED,  # Keep for backward compatibility
        'ai_enabled': AI_ENABLED,
        'provider': AI_PROVIDER,
        'model': AI_CONFIG.get('model', 'gemini-1.5-flash') if AI_PROVIDER else None,
        'thinking_disabled': AI_DISABLE_THINKING,
        'message': f'AI Ready ({AI_PROVIDER})' if AI_ENABLED else 'Enable LLM or add GOOGLE_API_KEY in .env'
    })

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5010))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
    #app.run(host='0.0.0.0', port=5010, ssl_context=('cert.pem', 'key.pem'))
