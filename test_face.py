import face_recognition

# សូមដាក់រូបភាពដែលមានមុខមនុស្សមួយសន្លឹកទៅក្នុង Folder នេះ
# រួចប្តូរឈ្មោះ 'test_image.jpg' ទៅតាមឈ្មោះរូបភាពរបស់អ្នក
image_path = "test_image.jpg" 

try:
    print("កំពុងដំណើរការស្វែងរកទម្រង់មុខ...")
    
    # ផ្ទុករូបភាពចូលទៅក្នុងប្រព័ន្ធ
    image = face_recognition.load_image_file(image_path)
    
    # ស្វែងរកទីតាំងមុខទាំងអស់ដែលមានក្នុងរូបភាព
    face_locations = face_recognition.face_locations(image)
    
    print(f"✅ រកឃើញផ្ទៃមុខចំនួន {len(face_locations)} នៅក្នុងរូបភាពនេះ។")
    
    if len(face_locations) > 0:
        print("🎉 ជោគជ័យ! Library សម្គាល់មុខរបស់អ្នកដំណើរការបានយ៉ាងល្អឥតខ្ចោះ។")
    else:
        print("⚠️ មិនមានផ្ទៃមុខត្រូវបានរកឃើញទេ។ សូមសាកល្បងជាមួយរូបភាពផ្សេងដែលច្បាស់ជាងនេះ។")

except FileNotFoundError:
    print(f"❌ រកមិនឃើញរូបភាពឈ្មោះ '{image_path}' ទេ។ សូមប្រាកដថាអ្នកបានដាក់រូបភាពក្នុង Folder ត្រឹមត្រូវ។")
except Exception as e:
    print(f"❌ មានបញ្ហាផ្សេងៗកើតឡើង: {e}")