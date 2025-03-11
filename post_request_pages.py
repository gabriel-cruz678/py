import requests
import json
from support.logger import *
from support.ambientes import *
from support.loads import *

class DummyMethods:
    def dummy_post():
        try:
            response = requests.post(f"{BASE_URL_TI}/{USER}", data=DATA)
            return json.loads(response.text)
        except Exception as error:
            return logging.error(error)
        