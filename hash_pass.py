import bcrypt

# បង្កើត Hash ពិតប្រាកដសម្រាប់លេខសម្ងាត់ "123456"
hashed = bcrypt.hashpw(b"123456", bcrypt.gensalt())
print("\nនេះគឺជាកូដ Hash របស់អ្នក សូម Copy វា៖\n")
print(hashed.decode('utf-8'))
print("\n")