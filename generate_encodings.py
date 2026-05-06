import os
import json
import face_recognition
import numpy as np
from app import get_db_connection  # 💡 ទាញយកមុខងារភ្ជាប់ Database ពី app.py របស់បង

# 💡 កំណត់ទីតាំង Folder ដែលផ្ទុករូបភាពដើមរបស់បេក្ខជន (សូមកែប្រែបើបងដាក់ទីតាំងផ្សេង)
REFERENCE_PHOTO_DIR = 'static/uploads/reference_photos'

def process_all_candidates():
    print("="*50)
    print("🚀 ចាប់ផ្តើមដំណើរការបំប្លែងរូបភាពទៅជា Face Encodings...")
    print("="*50)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ១. ទាញយកតែបេក្ខជនណាដែលមានរូបដើម តែមិនទាន់មាន face_encoding ប៉ុណ្ណោះ
        # (ចំណាំ៖ បើ Column រូបដើមរបស់បងឈ្មោះផ្សេង សូមកែពាក្យ reference_photos នេះ)
        cursor.execute("""
            SELECT application_no, original_photo_path 
            FROM candidates 
            WHERE face_encoding IS NULL 
            AND original_photo_path IS NOT NULL 
            AND original_photo_path != ''
        """)
        candidates = cursor.fetchall()
        
        total = len(candidates)
        if total == 0:
            print("✅ មិនមានបេក្ខជនដែលត្រូវបំប្លែងទិន្នន័យទេ (គ្រប់គ្នាមាន Encoding អស់ហើយ)!")
            return

        print(f"រកឃើញបេក្ខជនចំនួន {total} នាក់ ដែលត្រូវដំណើរការ...\n")
        
        success_count = 0
        fail_count = 0
        
        for idx, cand in enumerate(candidates, 1):
            app_no = cand['application_no']
            photo_name = cand['original_photo_path']
            photo_path = os.path.join(REFERENCE_PHOTO_DIR, photo_name)
            
            # ឆែកមើលថាតើ File រូបភាពពិតជាមានមែនឬអត់
            if not os.path.exists(photo_path):
                print(f"[{idx}/{total}] ❌ បរាជ័យ ({app_no}): រកមិនឃើញ File រូបភាព '{photo_name}'")
                fail_count += 1
                continue
                
            try:
                # ឱ្យ AI អានរូបភាព
                image = face_recognition.load_image_file(photo_path)
                encodings = face_recognition.face_encodings(image)
                
                if len(encodings) > 0:
                    # យករូបមុខទី១ (ករណីមានមុខច្រើនក្នុងរូប)
                    face_encoding = encodings[0]
                    # បំប្លែង Array ទៅជា JSON String
                    encoding_json = json.dumps(face_encoding.tolist())
                    
                    # Update ចូល Database
                    cursor.execute("""
                        UPDATE candidates 
                        SET face_encoding = %s 
                        WHERE application_no = %s
                    """, (encoding_json, app_no))
                    conn.commit()
                    
                    print(f"[{idx}/{total}] ✅ ជោគជ័យ ({app_no})")
                    success_count += 1
                else:
                    print(f"[{idx}/{total}] ⚠️ បរាជ័យ ({app_no}): AI រកមិនឃើញផ្ទៃមុខក្នុងរូបភាពនេះទេ!")
                    fail_count += 1
                    
            except Exception as e:
                print(f"[{idx}/{total}] ❌ Error ({app_no}): {str(e)}")
                fail_count += 1

        print("\n" + "="*50)
        print(f"🎉 ដំណើរការចប់សព្វគ្រប់!")
        print(f"   - ជោគជ័យ: {success_count} នាក់")
        print(f"   - បរាជ័យ: {fail_count} នាក់")
        print("="*50)

    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    process_all_candidates()