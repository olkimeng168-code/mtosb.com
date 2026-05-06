from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
# អនុញ្ញាតឱ្យ Web Browser ហៅទាញទិន្នន័យបាន (ការពារ Error CORS)
CORS(app)

# អថេរសម្រាប់រាប់ជុំ ដើម្បីក្លែងធ្វើសកម្មភាពដាក់ដៃ និងលើកដៃ
counter = 0

@app.route('/api/check_finger', methods=['GET'])
def check_finger():
    global counter
    counter += 1
    
    # 💡 ឡូជីខលក្លែងក្លាយ (Mock Logic):
    # យើងធ្វើឱ្យវាលោតឆ្លាស់គ្នា ដើម្បីឱ្យ UI ដឹងថាបេក្ខជនបាន "ដាក់ម្រាមដៃ" និង "លើកម្រាមដៃចេញ"
    # ជុំទី 1, 2 = ធ្វើពុតថាមានម្រាមដៃ
    # ជុំទី 3 = ធ្វើពុតថាគ្មានម្រាមដៃ (លើកចេញ) ដើម្បីឱ្យកូដ JS ដោះសោរ
    cycle = counter % 3
    
    if cycle in [1, 2]:
        return jsonify({
            "has_finger": True,
            "template": f"FAKE_BASE64_TEMPLATE_DATA_AUTO_TEST_{counter}",
            "message": "ចាប់បានម្រាមដៃ (Mock)"
        })
    else:
        return jsonify({
            "has_finger": False,
            "template": None,
            "message": "គ្មានម្រាមដៃ កញ្ចក់ទំនេរ (Mock)"
        })

if __name__ == '__main__':
    print("==================================================")
    print("🤖 ម៉ាស៊ីន ZKTeco ក្លែងក្លាយ (Mock) កំពុងដំណើរការ...")
    print("🌐 អាសយដ្ឋាន: http://127.0.0.1:8080")
    print("✅ ឥឡូវនេះអ្នកអាចបើកវេបសាយដើម្បីតេស្តស្កែនបានហើយ!")
    print("==================================================")
    # រត់នៅលើ Port 8080 ដើម្បីកុំឱ្យជាន់គ្នាជាមួយ Web Server ធំរបស់អ្នក (Port 5000)
    app.run(host='127.0.0.1', port=8080, debug=False)