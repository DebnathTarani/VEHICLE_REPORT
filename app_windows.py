from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import datetime
import base64
import json
import re
import requests
from openpyxl import Workbook
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Only import win32com if running on Windows with Outlook
try:
    import win32com.client
    OUTLOOK_ENABLED = True
except ImportError:
    OUTLOOK_ENABLED = False

# AI Provider Configuration
AI_PROVIDER = None
AI_CONFIG = {}

VLLM_ENABLED = os.getenv('VLLM_ENABLED', 'false').lower() == 'true'
VLLM_HOST = os.getenv('VLLM_HOST', 'http://localhost:8000')
VLLM_MODEL = os.getenv('VLLM_MODEL', 'nvidia/NVIDIA-Nemotron-Parse-v1.1')

LLAMACPP_ENABLED = os.getenv('LLAMACPP_ENABLED', 'false').lower() == 'true'
LLAMACPP_HOST = os.getenv('LLAMACPP_HOST', 'http://localhost:8080')
LLAMACPP_MODEL = os.getenv('LLAMACPP_MODEL', 'Llama-3.2-11B-Vision-Instruct')

AI_DISABLE_THINKING = os.getenv('AI_DISABLE_THINKING', 'false').lower() == 'true'

if VLLM_ENABLED:
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

if AI_PROVIDER is None and LLAMACPP_ENABLED:
    try:
        response = requests.get(f"{LLAMACPP_HOST}/v1/models", timeout=5)
        if response.status_code == 200:
            models_data = response.json()
            actual_model = LLAMACPP_MODEL
            if isinstance(models_data, dict) and 'data' in models_data:
                data_list = models_data['data']
                if data_list and isinstance(data_list, list) and len(data_list) > 0:
                    model_entry = data_list[0]
                    if isinstance(model_entry, dict):
                        actual_model = model_entry.get('id', LLAMACPP_MODEL)
                    elif isinstance(model_entry, str):
                        actual_model = model_entry
            AI_PROVIDER = 'llamacpp'
            AI_CONFIG = {'host': LLAMACPP_HOST, 'model': actual_model}
            print(f"✅ llama.cpp enabled at {LLAMACPP_HOST} with model: {actual_model}")
        else:
            print(f"⚠️ llama.cpp not responding at {LLAMACPP_HOST}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Cannot connect to llama.cpp at {LLAMACPP_HOST}: {e}")

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
            print("⚠️ No AI provider configured. Set LLAMACPP_ENABLED=true or add GOOGLE_API_KEY")
    except ImportError:
        print("⚠️ google-generativeai not installed, Gemini unavailable")

AI_ENABLED = AI_PROVIDER is not None
AI_VISION_SUPPORTED = None  # None=untested, True/False=cached result
AI_IMAGE_FORMAT = None  # Cached successful image format name
print(f"AI Provider: {AI_PROVIDER or 'None'}")
print(f"AI Thinking: {'Disabled' if AI_DISABLE_THINKING else 'Enabled'}")

app = Flask(__name__)
DB_NAME = 'vehicle_reports.db'

# Initialize database if it doesn't exist
def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_reports (
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
        conn.commit()
        conn.close()

def extract_json_from_response(response_text):
    """Extract JSON from AI model response, handling thinking tags and extra text"""
    if not response_text:
        raise ValueError("Empty response from AI model")

    text = response_text

    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)

    text = text.strip()

    if text.startswith('```'):
        end_index = text.find('\n', 3)
        if end_index != -1:
            text = text[end_index:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    json_start = -1
    for i, c in enumerate(text):
        if c in '[{':
            json_start = i
            break

    if json_start == -1:
        raise ValueError("No JSON array or object found in AI response")

    json_str = text[json_start:]

    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass

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


def get_image_mime_type(image_data):
    """Detect image MIME type from image bytes (more reliable than form content-type)"""
    if image_data[:2] == b'\xff\xd8':
        return 'image/jpeg'
    if image_data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if image_data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
        return 'image/webp'
    if image_data[:2] == b'BM':
        return 'image/bmp'
    return 'image/jpeg'


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save_reports', methods=['POST'])
def save_reports():
    data = request.json
    print("Received data:", data)  # Debug log
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for entry in data:
        cursor.execute('''
            INSERT INTO vehicle_reports 
            (city, sr_no, vrn, model, entry_date, in_time, out_date, out_time, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry['city'],
            int(entry['sr_no']) if entry['sr_no'] else None,
            entry['vrn'],
            entry['model'],
            entry['entry_date'],
            entry['in_time'],
            entry['out_date'],
            entry['out_time'],
            entry['remarks']
        ))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/generate_excel_and_email', methods=['POST'])
def generate_excel_and_email():
    data = request.json
    if not data:
        return jsonify({'status': 'No data received'}), 400

    entry_date = data[0].get("entry_date", str(datetime.date.today()))
    filename = f"vehicle_report_{entry_date}.xlsx"
    filepath = os.path.join(os.getcwd(), filename)

    # Generate Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Vehicle Report"
    headers = ["City", "SR No", "VRN", "Model", "Entry Date", "In Time", "Out Date", "Out Time", "Remarks"]
    ws.append(headers)

    for entry in data:
        ws.append([
            entry['city'],
            entry['sr_no'],
            entry['vrn'],
            entry['model'],
            entry['entry_date'],
            entry['in_time'],
            entry['out_date'],
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
            mail.Subject = f"Vehicle Report - {entry_date}"
            mail.Body = f"Hi,\n\nPlease find the attached vehicle report for {entry_date}.\n\nRegards,\nSushanta"
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
    return render_template('logs.html', entries=rows, filter_date=None)

@app.route('/view_by_date/<entry_date>')
def view_by_date(entry_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM vehicle_reports
        WHERE entry_date = ?
        ORDER BY city, sr_no
    ''', (entry_date,))
    rows = cursor.fetchall()
    conn.close()
    return render_template('logs.html', entries=rows, filter_date=entry_date)

@app.route('/save_reports_row', methods=['POST'])
def save_reports_row():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'No data received'}), 400

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
        data['entry_date'],
        data['in_time'],
        data['out_date'],
        data['out_time'],
        data['remarks']
    ))
    conn.commit()
    conn.close()
    return jsonify({'status': 'Row saved'})

@app.route('/extract_from_image', methods=['POST'])
def extract_from_image():
    """Extract vehicle data from uploaded image using AI"""
    if not AI_ENABLED:
        return jsonify({
            'status': 'error',
            'message': 'AI extraction not configured. Enable LLM or add GOOGLE_API_KEY in .env file.'
        }), 400

    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': 'No image file provided'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'status': 'error', 'message': 'No image selected'}), 400

    disable_thinking = request.form.get('disable_thinking', '').lower() == 'true'
    if not disable_thinking:
        disable_thinking = AI_DISABLE_THINKING

    global AI_VISION_SUPPORTED, AI_IMAGE_FORMAT
    if AI_VISION_SUPPORTED is False:
        return jsonify({
            'status': 'error',
            'message': 'This model does not support image input. Use a vision-capable model or switch AI provider.'
        }), 400

    try:
        image_data = image_file.read()
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        mime_type = get_image_mime_type(image_data)

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

        data_uri = f"data:{mime_type};base64,{image_b64}"

        image_formats = [
            {
                "name": "text_then_image_url",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}}
                ]
            },
            {
                "name": "image_url_then_text",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": prompt}
                ]
            },
            {
                "name": "images_raw",
                "content": prompt,
                "images": [image_b64]
            },
            {
                "name": "images_data_uri",
                "content": prompt,
                "images": [data_uri]
            },
        ]

        if AI_IMAGE_FORMAT is not None:
            ordered = [f for f in image_formats if f["name"] == AI_IMAGE_FORMAT]
            ordered += [f for f in image_formats if f["name"] != AI_IMAGE_FORMAT]
        else:
            ordered = image_formats

        response_text = None
        last_error = None
        used_format = None

        if AI_PROVIDER in ('vllm', 'llamacpp'):
            for fmt in ordered:
                try:
                    msg = {"role": "user"}
                    msg.update(fmt)

                    body = {
                        "model": AI_CONFIG['model'],
                        "messages": [msg],
                        "max_tokens": 4096
                    }
                    if disable_thinking:
                        body["enable_thinking"] = False

                    resp = requests.post(
                        f"{AI_CONFIG['host']}/v1/chat/completions",
                        json=body,
                        timeout=120
                    )

                    if resp.status_code == 200:
                        response_text = resp.json()['choices'][0]['message']['content'].strip()
                        used_format = fmt["name"]
                        break
                    else:
                        err_text = resp.text.lower()
                        last_error = resp.text
                        if 'does not support image' in err_text or 'image input' in err_text:
                            continue
                        raise Exception(f"{AI_PROVIDER} error: {resp.text}")

                except Exception as e:
                    last_error = str(e)
                    if 'does not support image' in str(e).lower() or 'image input' in str(e).lower():
                        continue
                    raise

        elif AI_PROVIDER == 'gemini':
            genai = AI_CONFIG['genai']
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([
                prompt,
                {"mime_type": mime_type, "data": image_b64}
            ])
            response_text = response.text.strip()

        if response_text is None:
            if last_error and ('does not support image' in last_error.lower() or 'image input' in last_error.lower()):
                AI_VISION_SUPPORTED = False
                return jsonify({
                    'status': 'error',
                    'message': 'This model does not support image input. Use a vision-capable model or switch AI provider.'
                }), 400
            raise Exception(last_error or "AI provider returned no response")

        cleaned_json = extract_json_from_response(response_text)
        extracted_data = json.loads(cleaned_json)
        AI_VISION_SUPPORTED = True
        AI_IMAGE_FORMAT = used_format

        return jsonify({
            'status': 'success',
            'data': extracted_data,
            'count': len(extracted_data),
            'provider': AI_PROVIDER,
            'thinking_disabled': disable_thinking,
            'image_format': used_format
        })

    except json.JSONDecodeError as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to parse AI response: {str(e)}',
            'raw_response': response_text if response_text else None
        }), 500
    except Exception as e:
        err_msg = str(e)
        if 'does not support image' in err_msg.lower() or 'image input' in err_msg.lower():
            AI_VISION_SUPPORTED = False
            return jsonify({
                'status': 'error',
                'message': 'This model does not support image input. Use a vision-capable model or switch AI provider.'
            }), 400
        return jsonify({
            'status': 'error',
            'message': f'Image processing failed: {err_msg}'
        }), 500

@app.route('/check_ai_status')
def check_ai_status():
    """Check if AI extraction is available"""
    vision_msg = ''
    if AI_VISION_SUPPORTED is False:
        vision_msg = ' (vision not supported by model)'
    elif AI_VISION_SUPPORTED is True:
        vision_msg = ' (vision ready)'
    return jsonify({
        'ai_enabled': AI_ENABLED,
        'provider': AI_PROVIDER,
        'model': AI_CONFIG.get('model', 'gemini-1.5-flash') if AI_PROVIDER else None,
        'thinking_disabled': AI_DISABLE_THINKING,
        'vision_supported': AI_VISION_SUPPORTED,
        'message': f'AI Ready ({AI_PROVIDER}){vision_msg}' if AI_ENABLED else 'Enable LLM or add GOOGLE_API_KEY in .env'
    })

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

