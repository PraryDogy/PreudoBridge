from datetime import datetime

new = datetime.now().replace(microsecond=0)
new = new.timestamp()
print(new)