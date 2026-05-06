# db_config.py
import platform
import mysql.connector

def get_db_connection():
    if platform.system() == 'Darwin' or platform.system() == 'Windows':
        try:
            # ជម្រើសទី ១៖ សាកល្បងដោយគ្មានលេខសម្ងាត់ (ធម្មតា)
            return mysql.connector.connect(
                host="localhost",
                user="root",
                password="",  
                database="mtosb_eps_system"
            )
        except mysql.connector.Error as err:
            if err.errno == 1045: # បើ Error លេខសម្ងាត់ខុស
                try:
                    # ជម្រើសទី ២៖ សាកល្បងជាមួយលេខសម្ងាត់ 'root' 
                    return mysql.connector.connect(
                        host="localhost",
                        user="root",
                        password="root", 
                        database="mtosb_eps_system"
                    )
                except mysql.connector.Error as err2:
                     # ជម្រើសទី ៣៖ សាកល្បងប្រើ unix_socket 
                     return mysql.connector.connect(
                        host="localhost",
                        user="root",
                        password="",
                        database="mtosb_eps_system",
                        unix_socket="/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock"
                    )
            else:
                raise err
    else:
        # សម្រាប់ VPS (Linux)
        return mysql.connector.connect(
            host="localhost",
            user="eps_user",
            password="HostingerVPS@123",
            database="mtosb_eps_system"
        )