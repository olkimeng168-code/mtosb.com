# ocr_matching.py
import os
import io
import pandas as pd
import pytesseract
from flask import Blueprint, render_template, request, jsonify
from werkzeug.utils import secure_filename
from google.cloud import vision

# បង្កើត Blueprint
ocr_sync_bp = Blueprint('ocr_sync', __name__)

# កំណត់ទីតាំង Tesseract សម្រាប់ Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# កំណត់ Folder សម្រាប់ File បណ្តោះអាសន្ន
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# បញ្ជាក់៖ លោកអ្នកត្រូវដាក់ file JSON key របស់ Google ក្នុង folder project
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google_key.json'

def call_google_vision(image_path):
    """មុខងារអានអក្សរដោយប្រើ Google Cloud Vision"""
    client = vision.ImageAnnotatorClient()
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

def call_tesseract(image_path):
    """មុខងារអានអក្សរដោយប្រើ Tesseract (Free)"""
    # ប្រើ lang='eng' សម្រាប់ Passport
    return pytesseract.image_to_string(image_path, lang='eng')

@ocr_sync_bp.route('/document-matching', methods=['GET', 'POST'])
def document_matching():
    if request.method == 'GET':
        return render_template('document_matching.html')
    
    if request.method == 'POST':
        try:
            excel_file = request.files.get('excel_file')
            id_image = request.files.get('id_image')
            ocr_option = request.form.get('ocr_option') # 'free' ឬ 'google'

            if not excel_file or not id_image:
                return jsonify({"status": "error", "message": "សូមបញ្ចូលឯកសារឱ្យបានគ្រប់គ្រាន់"}), 400

            # រក្សាទុក File បណ្តោះអាសន្ន
            img_path = os.path.join(UPLOAD_FOLDER, secure_filename(id_image.filename))
            id_image.save(img_path)
            
            excel_path = os.path.join(UPLOAD_FOLDER, secure_filename(excel_file.filename))
            excel_file.save(excel_path)

            # 1. អានទិន្នន័យពី Excel
            df = pd.read_csv(excel_path) if excel_path.endswith('.csv') else pd.read_excel(excel_path)
            # ឧបមាថាផ្ទៀងផ្ទាត់បេក្ខជនជួរទី ១ សិន (លោកអ្នកអាចកែតម្រូវតាម ID ជាក់ស្តែង)
            ex_name = str(df.iloc[0]['Name']).upper().strip()
            ex_id = str(df.iloc[0]['ID Number']).upper().strip()

            # 2. ដំណើរការ OCR
            if ocr_option == 'google':
                ocr_result = call_google_vision(img_path)
            else:
                ocr_result = call_tesseract(img_path)
            
            ocr_result_upper = ocr_result.upper()

            # 3. Logic ផ្ទៀងផ្ទាត់ (Matching Logic)
            # ពិនិត្យមើលថា តើឈ្មោះ និងលេខ ID ក្នុង Excel មាននៅក្នុងអត្ថបទដែលស្កេនបានឬទេ
            name_match = ex_name in ocr_result_upper
            id_match = ex_id in ocr_result_upper

            # លុប file ចោលវិញក្រោយប្រើរួច
            os.remove(img_path)
            os.remove(excel_path)

            return jsonify({
                "status": "success",
                "excel_data": {"name": ex_name, "id": ex_id},
                "matching_result": {
                    "name_verified": name_match,
                    "id_verified": id_match,
                    "is_all_correct": name_match and id_match
                },
                "raw_ocr": ocr_result[:200] + "..." # បង្ហាញតែ ២០០ តួដំបូង
            })

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500