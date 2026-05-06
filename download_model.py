import urllib.request
import os
import ssl

# 💡 បន្ថែមកូដ១បន្ទាត់នេះ ដើម្បីដោះស្រាយបញ្ហា SSL នៅលើ MacBook
ssl._create_default_https_context = ssl._create_unverified_context

# បង្កើត Folder ឈ្មោះ 'models' នៅក្នុង 'static' ដោយស្វ័យប្រវត្តិ
os.makedirs('static/models', exist_ok=True)

# Link សុវត្ថិភាពពីក្រុមហ៊ុន Intel ផ្ទាល់
url = "https://storage.openvinotoolkit.org/repositories/open_model_zoo/public/2022.1/anti-spoof-mn3/anti-spoof-mn3.onnx"
filename = "static/models/liveness_model.onnx"

print("⏳ កំពុងទាញយក AI Model ពី Intel (ទំហំ 11.7MB) សូមរង់ចាំបន្តិច...")

try:
    urllib.request.urlretrieve(url, filename)
    print(f"✅ ទាញយកបានជោគជ័យ! File ត្រូវបានរក្សាទុកនៅ៖ {filename}")
except Exception as e:
    print(f"❌ កំហុសក្នុងការទាញយក៖ {e}")