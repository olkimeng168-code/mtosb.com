import platform
import mysql.connector
from flask import Flask
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)

# 💡 កំណត់ឈ្មោះ និងលេខសម្ងាត់ Admin ដែលបងចង់បាននៅទីនេះ
USERNAME = 'admin'
PASSWORD = '123456'
FULL_NAME = 'System Admin'

# អនុគមន៍ភ្ជាប់ Database ឆ្លាតវៃ (ស្គាល់ទាំង Mac និង VPS)
def get_db_connection():
    if platform.system() == 'Darwin' or platform.system() == 'Windows':
        try:
            return mysql.connector.connect(host="localhost", user="root", password="", database="mtosb_eps_system")
        except mysql.connector.Error as err:
            if err.errno == 1045:
                try:
                    return mysql.connector.connect(host="localhost", user="root", password="root", database="mtosb_eps_system")
                except mysql.connector.Error:
                     return mysql.connector.connect(host="localhost", user="root", password="", database="mtosb_eps_system", unix_socket="/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock")
            else:
                raise err
    else:
        return mysql.connector.connect(host="localhost", user="eps_user", password="HostingerVPS@123", database="mtosb_eps_system")

try:
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # បំប្លែងលេខសម្ងាត់ទៅជាទម្រង់ Bcrypt ស្តង់ដារ
    hashed_pw = bcrypt.generate_password_hash(PASSWORD).decode('utf-8')
    
    # ឆែកមើលថាតើមានគណនីឈ្មោះនេះរួចហើយឬនៅ
    cursor.execute("SELECT id FROM users WHERE username = %s", (USERNAME,))
    user = cursor.fetchone()
    
    if user:
        # បើមានហើយ Update តែលេខសម្ងាត់ឱ្យត្រូវស្តង់ដារ
        cursor.execute("UPDATE users SET password_hash = %s WHERE username = %s", (hashed_pw, USERNAME))
        print(f"\n✅ ជោគជ័យ! បាន Update លេខសម្ងាត់ថ្មីឱ្យគណនី '{USERNAME}' រួចរាល់។\n")
    else:
        # បើមិនទាន់មានទេ បង្កើតគណនី Admin ថ្មីតែម្តង
        # ចំណាំ: សន្មតថា role_id = 1 គឺ Admin នៅក្នុងតារាង roles របស់បង
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, role_id, is_active) VALUES (%s, %s, %s, 1, True)", 
            (USERNAME, hashed_pw, FULL_NAME)
        )
        print(f"\n✅ ជោគជ័យ! បានបង្កើតគណនី Admin ថ្មីឈ្មោះ '{USERNAME}' រួចរាល់។\n")
        
    conn.commit()
    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n❌ មានបញ្ហា: {e}\n")