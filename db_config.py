# db_config.py
import platform
import mysql.connector

def get_db_connection():
    if platform.system() == 'Darwin' or platform.system() == 'Windows':
        # ជម្រើសទី ១៖ សាកល្បងដោយគ្មានលេខសម្ងាត់ (ធម្មតា)
        try:
            return mysql.connector.connect(
                host="localhost",
                user="root",
                password="",  
                database="mtosb_eps_system"
            )
        except mysql.connector.Error:
            # ជម្រើសទី ២៖ សាកល្បងជាមួយលេខសម្ងាត់ 'root' 
            try:
                return mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password="root", 
                    database="mtosb_eps_system"
                )
            except mysql.connector.Error:
                # ជម្រើសទី ៣៖ សាកល្បងប្រើ unix_socket (សម្រាប់ XAMPP លើ Mac)
                # ពេលនេះ ទោះបីជា Error លេខប៉ុន្មានក៏ដោយ វានឹងរត់មករក Socket ជាជម្រើសចុងក្រោយ
                return mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password="",
                    database="mtosb_eps_system",
                    unix_socket="/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock"
                )
    else:
        # សម្រាប់ VPS (Linux)
        return mysql.connector.connect(
            host="localhost",
            user="eps_user",
            password="HostingerVPS@123",
            database="mtosb_eps_system"
        )