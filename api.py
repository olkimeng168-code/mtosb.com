from flask import Flask, request, jsonify
import face_recognition

app = Flask(__name__)

@app.route('/verify-face', methods=['POST'])
def verify_face():
    # ១. ត្រួតពិនិត្យថាតើមាន File រូបភាពបញ្ជូនមកឬអត់
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "មិនមានរូបភាពត្រូវបានបញ្ជូនមកទេ!"}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({"success": False, "message": "ឈ្មោះរូបភាពមិនត្រឹមត្រូវ!"}), 400

    try:
        # ២. អានរូបភាពដែលបញ្ជូនមក (ដោយមិនចាំបាច់ Save ចូលម៉ាស៊ីន)
        image = face_recognition.load_image_file(file)
        
        # ៣. ស្វែងរកទីតាំងមុខ
        face_locations = face_recognition.face_locations(image)
        faces_count = len(face_locations)
        
        # ៤. បោះលទ្ធផលត្រឡប់ទៅ Website វិញ
        if faces_count > 0:
            return jsonify({
                "success": True, 
                "faces_found": faces_count,
                "message": f"ជោគជ័យ! រកឃើញផ្ទៃមុខចំនួន {faces_count}"
            }), 200
        else:
            return jsonify({
                "success": False, 
                "faces_found": 0,
                "message": "បរាជ័យ! មិនមានផ្ទៃមុខត្រូវបានរកឃើញក្នុងរូបភាពនេះទេ"
            }), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"មានបញ្ហា Server: {str(e)}"}), 500

if __name__ == '__main__':
    # ដំណើរការ API នៅលើ Port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)