from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import base64
import time
import subprocess
import threading

app = Flask(__name__)
CORS(app) 

OS_TYPE = sys.platform

# ==========================================
# 📂 មុខងារលោតផ្ទាំងរើស Folder
# ==========================================
selected_folder_path = ""

def open_folder_dialog_windows():
    global selected_folder_path
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    selected_folder_path = filedialog.askdirectory(title="ជ្រើសរើសទីតាំងរក្សាទុកឯកសារស្កេន")
    root.destroy()

@app.route('/choose_folder', methods=['GET'])
def choose_folder():
    global selected_folder_path
    selected_folder_path = ""
    
    if OS_TYPE == 'darwin':
        # 🍏 សម្រាប់ Mac: ប្រើ AppleScript ជំនួស tkinter ដើម្បីកុំឱ្យគាំង (Crash)
        script = 'tell application "System Events" to activate\ntell application "System Events" to return POSIX path of (choose folder with prompt "ជ្រើសរើសទីតាំងរក្សាទុកឯកសារស្កេន")'
        try:
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            if result.returncode == 0:
                selected_folder_path = result.stdout.strip()
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    else:
        # 🪟 សម្រាប់ Windows: រក្សាកូដដើមរបស់លោកអ្នកដែលដើរល្អស្រាប់
        t = threading.Thread(target=open_folder_dialog_windows)
        t.start()
        t.join()
    
    if selected_folder_path:
        return jsonify({'status': 'success', 'path': os.path.normpath(selected_folder_path)})
    else:
        return jsonify({'status': 'error', 'message': 'បោះបង់ការជ្រើសរើស'})

# ==========================================
# 🖨️ មុខងារស្កេនឯកសារ
# ==========================================
@app.route('/scan', methods=['POST'])
def scan_document():
    data = request.json
    app_no = data.get('application_no', 'Unknown')
    custom_save_dir = data.get('save_dir', '')
    
    if custom_save_dir and os.path.isdir(custom_save_dir):
        final_save_dir = custom_save_dir
    else:
        final_save_dir = r"D:\EPS_Scanned_Passports" if OS_TYPE == 'win32' else os.path.expanduser("~/Desktop/EPS_Scanned_Passports")
        if not os.path.exists(final_save_dir):
            os.makedirs(final_save_dir)
            
    # ស្វែងរកបន្ទាត់ filename រួចកែដូចខាងក្រោម៖
    filename = f"{app_no}.jpg"  # 👈 យកតែលេខកូដប្រឡងជាឈ្មោះ File
    save_path = os.path.join(final_save_dir, filename)

    try:
        if OS_TYPE == 'win32':
            # 🪟 កូដ Windows ដើមរបស់លោកអ្នក (រក្សាទុកដដែល)
            import pythoncom              # type: ignore
            pythoncom.CoInitialize()      
            try:
                import win32com.client  # type: ignore
            except ImportError:
                return jsonify({'status': 'error', 'message': 'សូមដំឡើង pywin32 លើកុំព្យូទ័រ Windows នេះសិន!'})
                
            devManager = win32com.client.Dispatch("WIA.DeviceManager")
            scanner = None
            for info in devManager.DeviceInfos:
                if info.Type == 1:
                    scanner = info.Connect()
                    break
            if not scanner:
                return jsonify({'status': 'error', 'message': 'រកមិនឃើញម៉ាស៊ីនស្កេន Windows ទេ!'})
                
            item = scanner.Items[1]
            image = item.Transfer("{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}") 
            image.SaveFile(save_path)
            pythoncom.CoUninitialize()    

        elif OS_TYPE == 'darwin':
            # 🍏 កូដសម្រាប់ Mac
            command = ['scanimage', '--format=jpeg', '--resolution', '300', '-o', save_path]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                return jsonify({'status': 'error', 'message': f'ម៉ាស៊ីនស្កេន Mac មានបញ្ហា៖ {result.stderr}'})

        with open(save_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            base64_image = f"data:image/jpeg;base64,{encoded_string}"

        return jsonify({'status': 'success', 'file_path': save_path, 'image_base64': base64_image})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    print("="*60)
    print(f"🚀 កម្មវិធី Local Bridge កំពុងដំណើរការលើប្រព័ន្ធ៖ {OS_TYPE.upper()}")
    print("🌐 Port ទំនាក់ទំនង៖ http://127.0.0.1:5005")
    print("="*60)
    
    # 💡 គន្លឹះសំខាន់៖ បើលើ Mac ប្រើ threaded=False ដើម្បីការពារការ Crash
    is_threaded = False if OS_TYPE == 'darwin' else True
    app.run(host='127.0.0.1', port=5005, threaded=is_threaded)