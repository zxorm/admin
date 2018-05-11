import os

debug = os.getenv("APP_DEBUG", "True") == "True"
dbName=os.getenv("DB_NAME", "")
dbUrl=os.getenv("DB_URL", f"mysql:///{dbName}?charset=utf8")

secretKey=os.getenv("APP_SECRET", "")