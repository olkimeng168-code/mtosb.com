from flask import Flask, jsonify
from flask_cors import CORS
from pyzkfp import ZKFP2
import base64
import time

app = Flask(__name__)
# អនុញ្ញាតឱ្យ Web Browser (JavaScript) អាចហៅមកកាន់ API នេះបាន
CORS(app) 

# បង្កើត Object សម្រាប់ម៉ាស៊ីន ZKTeco
zkfp2 = ZKFP2()

# អថេរសម្រាប់កំណត់ស្ថានភាពម៉ាស៊ីន
device_connected = False

def init_scanner():
    global device_connected
    try:
        zkfp2.Init()
        device_count = zkfp2.GetDeviceCount()
        
        if device_count > 0:
            zkfp2.OpenDevice(0)
            print("✅ ភ្ជាប់ម៉ាស៊ីន ZKTeco SLK20R ជោគជ័យ!")
            device_connected = True
        else:
            print("❌ រកមិនឃើញម៉ាស៊ីនស្កែនទេ។ សូមដោតម៉ាស៊ីនទៅកាន់ USB!")
            device_connected = False
    except Exception as e:
        print(f"❌ បរាជ័យក្នុងការតភ្ជាប់ម៉ាស៊ីន: {e}")
        device_connected = False

# ហៅមុខងារភ្ជាប់ម៉ាស៊ីនពេលកម្មវិធីចាប់ផ្តើមដំណើរការ
init_scanner()

# ============================================================
# API Endpoint សម្រាប់ឱ្យ Web (JavaScript) បាញ់មកសួររៀងរាល់ ១វិនាទី
# ============================================================
@app.route('/api/check_finger', methods=['GET'])
def check_finger():
    global device_connected
    
    # បើម៉ាស៊ីនរបូត USB ព្យាយាមភ្ជាប់ឡើងវិញ
    if not device_connected:
        init_scanner()
        if not device_connected:
            return jsonify({"has_finger": False, "error": "មិនទាន់បានតភ្ជាប់ម៉ាស៊ីន"})

    try:
        # AcquireFingerprint គឺជា Function របស់ ZKTeco សម្រាប់ចាប់យករូបភាព និងទិន្នន័យ
        # វានឹង Return ទិន្នន័យ លុះត្រាតែមានម្រាមដៃពិតប្រាកដ និងមានគុណភាពគ្រប់គ្រាន់
        capture = zkfp2.AcquireFingerprint()
        
        if capture:
            # tmp គឺជា Byte Array នៃ Template ក្រយៅដៃ, img គឺជារូបភាព
            tmp, img = capture
            
            # បំប្លែង Byte Array ទៅជា Base64 String ដើម្បីងាយស្រួលបញ្ជូនទៅ Web
            template_b64 = base64.b64encode(tmp).decode('utf-8')
            
            return jsonify({
                "has_finger": True,
                "template": template_b64,
                "message": "ចាប់បានម្រាមដៃ"
            })
        else:
            # កញ្ចក់ទំនេរ ឬ មានតែស្នាមញើសចាស់ (គុណភាពមិនគ្រប់គ្រាន់)
            return jsonify({
                "has_finger": False,
                "template": None,
                "message": "គ្មានម្រាមដៃ ឬ ព្រិលពេក"
            })
            
    except Exception as e:
        return jsonify({"has_finger": False, "error": str(e)})

if __name__ == '__main__':
    # ដំណើរការ Local API លើ Port 8080 (កុំឱ្យជាន់ជាមួយ Web Server របស់អ្នក)
    print("🚀 កម្មវិធី ZKTeco Local Agent កំពុងដំណើរការលើ http://127.0.0.1:8080")
    app.run(host='127.0.0.1', port=8080, debug=False)