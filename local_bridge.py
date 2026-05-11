from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import base64
import tempfile
import subprocess
import threading
import io
import time
from PIL import Image

# 🌟 វះកាត់ជាន់ទី ១៖ ទាញបណ្ណាល័យ OS-Specific និង GUI មកប្រកាសជា Global ទាំងអស់
# ដើម្បីបង្ខំឱ្យ PyInstaller វេចខ្ចប់វាចូល .exe ជាដាច់ខាត (ការពារការគាំងបិទស្ងាត់ៗ)
if sys.platform == 'win32':
    import pythoncom
    import win32com.client
    import tkinter as tk
    from tkinter import filedialog

app = Flask(__name__)
# 🌟 អនុញ្ញាត CORS គ្រប់ប្រភពទាំងអស់ដើម្បីកុំឱ្យ Browser ប្លុក
CORS(app, resources={r"/*": {"origins": "*"}}) 

OS_TYPE = sys.platform

# ==========================================
# 📂 មុខងារលោតផ្ទាំងរើស Folder (Windows 11 Native)
# ==========================================
selected_folder_path = ""

def open_folder_dialog_windows():
    global selected_folder_path
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected_folder_path = filedialog.askdirectory(title="ជ្រើសរើសទីតាំងរក្សាទុកឯកសារស្កេន")
        root.destroy()
    except Exception as e:
        print(f"Error opening folder dialog: {e}")
        selected_folder_path = ""

@app.route('/choose_folder', methods=['GET'])
def choose_folder():
    global selected_folder_path
    selected_folder_path = ""
    
    if OS_TYPE == 'darwin':
        script = 'tell application "System Events" to activate\ntell application "System Events" to return POSIX path of (choose folder with prompt "ជ្រើសរើសទីតាំងរក្សាទុកឯកសារស្កេន")'
        try:
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            if result.returncode == 0:
                selected_folder_path = result.stdout.strip()
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    else:
        t = threading.Thread(target=open_folder_dialog_windows)
        t.start()
        t.join()
    
    if selected_folder_path:
        return jsonify({'status': 'success', 'path': os.path.normpath(selected_folder_path)})
    else:
        return jsonify({'status': 'error', 'message': 'បោះបង់ការជ្រើសរើស'})


# ==========================================
# 🖨️ ១. មុខងារស្កេនទាញយករូប (Pure Hardware Scan)
# ==========================================
@app.route('/scan', methods=['POST', 'OPTIONS'])
def scan_document():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'success'}), 200

    data = request.json or {}
    app_no = data.get('application_no', 'Unknown')
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"temp_eps_scan_{int(time.time())}.jpg")

    scan_success = False
    error_msg = ""

    try:
        if OS_TYPE == 'win32':
            try:
                pythoncom.CoInitialize()      
                devManager = win32com.client.Dispatch("WIA.DeviceManager")
                scanner = None
                for info in devManager.DeviceInfos:
                    if info.Type == 1:
                        scanner = info.Connect()
                        break
                if scanner:
                    item = scanner.Items[1]
                    image = item.Transfer("{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}") 
                    image.SaveFile(temp_path)
                    scan_success = True
                else:
                    error_msg = "រកមិនឃើញម៉ាស៊ីនស្កេនទេ! សូមពិនិត្យមើលខ្សែ USB និងភ្លើងម៉ាស៊ីន។"
                pythoncom.CoUninitialize()
            except Exception as e:
                error_msg = f"កំហុសម៉ាស៊ីនស្កេន៖ {str(e)}"

        elif OS_TYPE == 'darwin':
            try: 
                command = ['scanimage', '--format=jpeg', '--resolution', '300', '-o', temp_path]
                result = subprocess.run(command, capture_output=True, text=True)
                if result.returncode == 0:
                    scan_success = True
                else:
                    error_msg = "ម៉ាស៊ីនស្កេនមិនឆ្លើយតប! សូមប្រាកដថាម៉ាស៊ីនបានបើក និងភ្ជាប់ត្រឹមត្រូវ។"
            except Exception as e:
                error_msg = str(e)

        # 🌟 វះកាត់ជាន់ទី ២៖ លុប Mock Mode ចោលទាំងស្រុង (បើស្កេនពិតបរាជ័យ បោះ Error ភ្លាមៗ)
        if not scan_success:
            print(f"❌ ស្កេនបរាជ័យ៖ {error_msg}")
            return jsonify({
                'status': 'error', 
                'message': f"⚠️ ស្កេនបរាជ័យ៖ {error_msg or 'សូមពិនិត្យមើលការតភ្ជាប់ម៉ាស៊ីនស្កេនឡើងវិញ!'}"
            })

        with open(temp_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            base64_image = f"data:image/jpeg;base64,{encoded_string}"

        if os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify({'status': 'success', 'image_base64': base64_image})

    except Exception as e:
        return jsonify({'status': 'error', 'message': f"System Error: {str(e)}"})


# ==========================================
# 💾 ២. មុខងាររក្សាទុករូបភាពជាផ្លូវការ (Save + Dynamic Compression)
# ==========================================
@app.route('/save', methods=['POST', 'OPTIONS'])
def save_document():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'success'}), 200

    data = request.json or {}
    app_no = data.get('application_no')
    save_dir = data.get('save_dir')
    base64_data = data.get('image_base64')
    
    max_size_kb = int(data.get('max_size_kb', 1000)) 
    
    if not app_no or not save_dir or not base64_data:
        return jsonify({'status': 'error', 'message': 'ទិន្នន័យមិនគ្រប់គ្រាន់សម្រាប់ការរក្សាទុក!'})
        
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    filename = f"{app_no}.jpg"
    final_save_path = os.path.join(save_dir, filename)
    
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
            
        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        if image.mode != 'RGB':
            image = image.convert('RGB')

        quality = 100    
        min_quality = 70 
        step = 3         
        
        while True:
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=quality)
            size_kb = len(img_byte_arr.getvalue()) / 1024
            
            if size_kb <= max_size_kb or quality <= min_quality:
                with open(final_save_path, 'wb') as f:
                    f.write(img_byte_arr.getvalue())
                break
            
            quality -= step 
            
        final_size_kb = round(os.path.getsize(final_save_path) / 1024, 2)
        final_size_mb = round(final_size_kb / 1024, 2)
        
        return jsonify({
            'status': 'success', 
            'message': 'រក្សាទុកជោគជ័យ', 
            'file_path': final_save_path,
            'final_size': f"{final_size_mb} MB"
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f"បញ្ហាក្នុងការរក្សាទុក៖ {str(e)}"})


if __name__ == '__main__':
    print("="*60)
    print(f"🚀 កម្មវិធី Local Bridge (Production) កំពុងដំណើរការលើប្រព័ន្ធ៖ {OS_TYPE.upper()}")
    print("🌐 Port ទំនាក់ទំនង៖ http://127.0.0.1:5005")
    print("="*60)
    
    is_threaded = False if OS_TYPE == 'darwin' else True
    app.run(host='127.0.0.1', port=5005, threaded=is_threaded)