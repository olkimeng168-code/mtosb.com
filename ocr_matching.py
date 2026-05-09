import os
import io
import pandas as pd
import pytesseract
import platform
import re
from flask import Blueprint, render_template, request, jsonify
from werkzeug.utils import secure_filename
from google.cloud import vision

ocr_sync_bp = Blueprint('ocr_sync', __name__)

# --- ១. កំណត់ទីតាំង Tesseract ---
if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# បង្កើតអថេរ Global សម្រាប់ទុកទិន្នន័យ Excel បណ្តោះអាសន្ន
excel_data_store = []

def call_google_vision(image_path):
    try:
        if not os.path.exists('google_key.json'):
            return "ERROR: Missing google_key.json"
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google_key.json'
        client = vision.ImageAnnotatorClient()
        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        return response.text_annotations[0].description if response.text_annotations else ""
    except Exception as e:
        return f"ERROR: Google API {str(e)}"

def call_tesseract(image_path):
    try:
        # បន្ថែម config ដើម្បីឱ្យអានលេខបានច្បាស់ជាងមុន
        return pytesseract.image_to_string(image_path, lang='eng')
    except Exception as e:
        return f"ERROR: Tesseract {str(e)}"

# --- ២. Route សម្រាប់ Upload Excel ---
# ក្នុង ocr_matching.py ត្រង់ Route /api/upload_excel
@ocr_sync_bp.route('/api/upload_excel', methods=['POST'])
def upload_excel():
    global excel_data_store
    try:
        file = request.files.get('excel_file')
        if not file:
            return jsonify({"status": "error", "message": "មិនមានឯកសារ"}), 400
        
        # --- ដំណោះស្រាយ៖ បន្ថែម dtype=str ដើម្បីរក្សាលេខ 0 នៅខាងមុខ ---
        if file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file, dtype=str) # កំណត់ឱ្យអានគ្រប់ជួរជា String ទាំងអស់
        else:
            df = pd.read_csv(file, dtype=str, encoding='utf-8-sig')
        
        df.columns = [c.strip() for c in df.columns]
        excel_data_store = df.to_dict('records')
        
        return jsonify({"status": "success", "total_records": len(excel_data_store)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ៣. Route ចម្បងសម្រាប់ Scan (ស៊ីគ្នាជាមួយ UI ថ្មី) ---
# ក្នុង ocr_matching.py ត្រង់ Route /api/scan

@ocr_sync_bp.route('/api/scan', methods=['POST'])
def scan_document():
    global excel_data_store
    try:
        files = request.files.getlist('document_images')
        results = []

        for file in files:
            filename = file.filename # ឈ្មោះរូបភាព ឧទាហរណ៍: 0022026C50200002_PP.png
            img_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
            file.save(img_path)

            # ១. ដំណើរការ OCR (អានអត្ថបទពីរូបភាព)
            ocr_text = call_tesseract(img_path).upper()

            # ២. ស្វែងរកទិន្នន័យក្នុង Excel តាមរយៈ "ឈ្មោះ File" (ល្បិចថ្មី)
            # យើងកាត់យកតែលេខកូដពីឈ្មោះ File (យក ១៥ តួដំបូង)
            file_code = filename[:15] 
            
            matched_row = None
            for row in excel_data_store:
                excel_code = str(row.get('Code', '')).strip()
                if excel_code in filename: # បើលេខកូដក្នុង Excel មាននៅក្នុងឈ្មោះរូបភាព
                    matched_row = row
                    break

            # ៣. Logic ផ្ទៀងផ្ទាត់ (Verification)
            status = "Warning"
            error_msg = "រកមិនឃើញទិន្នន័យក្នុង Excel"
            
            if matched_row:
                ex_id = str(matched_row.get('ID Number', '')).strip().upper()
                ex_id_clean = re.sub(r'\s*\(\d+\)', '', ex_id) # កាត់វង់ក្រចកចេញ
                ex_name = str(matched_row.get('Name', '')).strip().upper()

                # ឆែកមើលថាត្រូវនឹង OCR អត់
                id_match = ex_id_clean in ocr_text or ex_id in ocr_text
                name_match = ex_name in ocr_text
                
                if id_match and name_match:
                    status = "Success"
                    error_msg = ""
                elif id_match or name_match:
                    status = "Mismatch"
                    error_msg = "ឈ្មោះ ឬ លេខកាត មិនត្រូវគ្នា ១០០%"
                else:
                    status = "Mismatch"
                    error_msg = "OCR អានមិនត្រូវនឹងទិន្នន័យ Excel"

            # ៤. បន្ថែមចូលក្នុងលទ្ធផល (ទោះរកមិនឃើញ ក៏ត្រូវបង្ហាញជួរក្នុងតារាងដែរ)
            results.append({
                "Filename": filename,
                "Document Number": matched_row.get('ID Number', 'Unknown') if matched_row else "Unknown",
                "Full Name": matched_row.get('Name', 'Unknown') if matched_row else "Unknown",
                "Gender": str(matched_row.get('Sex') or matched_row.get('Gender') or '-').strip().upper(),
                "Date of Birth": matched_row.get('DOB', '-') if matched_row else "-",
                "Status": status,
                "Error": error_msg,
                "Excel_Data": matched_row
            })
            
            if os.path.exists(img_path): os.remove(img_path)

        return jsonify({"status": "success", "data": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@ocr_sync_bp.route('/document-matching')
def document_matching_page():
    return render_template('document_matching.html')

# ថែមក្នុង ocr_matching.py
from flask import send_file

import io
from datetime import date
from flask import send_file, request, jsonify
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

@ocr_sync_bp.route('/api/export_report', methods=['POST'])
def export_report():
    try:
        report_data = request.json.get('report_data', [])
        if not report_data:
            return jsonify({"status": "error", "message": "មិនមានទិន្នន័យ"}), 400

        wb = Workbook()
        ws = wb.active
        ws.title = "OCR Verification Report"

        # --- ១. រៀបចំ Header និងទិន្នន័យ ---
        headers = ["#", "ឈ្មោះរូបភាព", "លេខឯកសារ", "ឈ្មោះពេញ", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត", "ស្ថានភាព"]
        
        # បញ្ចូលចំណងជើងធំៗ (Row 1-3)
        ws.append(["របាយការណ៍ផ្ទៀងផ្ទាត់ទិន្នន័យបេក្ខជន (OCR System)"])
        ws.append([f"កាលបរិច្ឆេទបញ្ចេញរបាយការណ៍៖ {date.today().strftime('%d-%m-%Y')}"])
        ws.append(["ប្រព័ន្ធគ្រប់គ្រងទិន្នន័យ៖ MTOSB Smart OCR Enterprise"])
        ws.append(headers) # Row 4

        # បញ្ចូលទិន្នន័យ (ចាប់ពី Row 5)
        for idx, item in enumerate(report_data, 1):
            ws.append([
                idx,
                item.get("Filename", "-"),
                item.get("Document Number", "-"),
                item.get("Full Name", "-"),
                item.get("Gender", "-"),
                item.get("Date of Birth", "-"),
                item.get("Status", "-")
            ])

        # --- ២. ការកំណត់ Styles តាមលំនាំដែលលោកអ្នកចង់បាន ---
        font_title = Font(name='Khmer OS Siemreap', size=15, bold=True, color="0f172a")
        font_subtitle = Font(name='Khmer OS Siemreap', size=12, color="475569")
        font_header = Font(name='Khmer OS Siemreap', size=13, bold=True, color="ffffff")
        font_data = Font(name='Khmer OS Siemreap', size=11)
        
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                             top=Side(style='thin'), bottom=Side(style='thin'))
        align_center = Alignment(horizontal='center', vertical='center', wrap_text=False)
        align_left = Alignment(horizontal='left', vertical='center', wrap_text=False)
        header_fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")

        # កំណត់កម្ពស់ជួរ
        ws.row_dimensions[1].height = 35 
        ws.row_dimensions[2].height = 25 
        ws.row_dimensions[3].height = 25
        ws.row_dimensions[4].height = 35 

        # អនុវត្ត Styles ទៅលើគ្រប់ Cell
        for row_idx, row in enumerate(ws.iter_rows(), start=1):
            if row_idx > 4:
                ws.row_dimensions[row_idx].height = 28
            for cell in row:
                if row_idx == 1: 
                    cell.font = font_title
                    cell.alignment = align_center
                elif row_idx in [2, 3]: 
                    cell.font = font_subtitle
                    cell.alignment = align_center
                elif row_idx == 4: 
                    cell.font = font_header
                    cell.alignment = align_center
                    cell.border = thin_border
                    cell.fill = header_fill
                else: 
                    cell.font = font_data
                    cell.border = thin_border
                    # កំណត់ឱ្យតម្រឹមនៅកណ្តាលសម្រាប់ជួរខ្លីៗ
                    if cell.column in [1, 5, 7]: 
                        cell.alignment = align_center
                    else:
                        cell.alignment = align_left

        # កំណត់ប្រវែង Column ឱ្យលោតតាមទិន្នន័យ (Auto Width)
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                if cell.row < 4: continue
                try:
                    if cell.value:
                        cell_length = len(str(cell.value))
                        if cell_length > max_length: max_length = cell_length
                except: pass
            
            adjusted_width = (max_length * 1.5) + 2
            ws.column_dimensions[column].width = min(max(adjusted_width, 10), 50)

        # Merge Header
        max_col_letter = get_column_letter(ws.max_column)
        ws.merge_cells(f'A1:{max_col_letter}1')
        ws.merge_cells(f'A2:{max_col_letter}2')
        ws.merge_cells(f'A3:{max_col_letter}3')

        # បញ្ជូន File ទៅកាន់ Browser
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        filename = f"OCR_Verification_Report_{date.today().strftime('%Y%m%d')}.xlsx"
        return send_file(out, download_name=filename, as_attachment=True, 
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500