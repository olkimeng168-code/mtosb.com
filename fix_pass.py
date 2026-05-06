from flask_bcrypt import generate_password_hash
# បង្កើតកូដ Hash ត្រឹមត្រូវសម្រាប់ពាក្យ "123"
new_hash = generate_password_hash("123") 
print(new_hash) # រួចយកអាដែល Print ចេញនេះ ទៅ Copy ដាក់ក្នុង Database ត្រង់កន្លែង password_hash