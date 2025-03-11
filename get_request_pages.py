import requests, json
from support.logger import *
from support.ambientes import *
from support.loads import *

class DummyMethods:  
    def dummy_get():
        try:
            response = requests.get(f"{BASE_URL_TI}/")
            print(response.text)
        except Exception as error:
            return logging.error(error)

    def dummy_get_unic():
        try:
            response = requests.get(f"{BASE_URL_TI}/{USER}")
            return json.loads(response.text)
        except Exception as error:
            return logging.error(error)