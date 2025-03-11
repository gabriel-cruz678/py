import requests
import json
from support.logger import *
from support.ambientes import *
from support.loads import *

class DummyMethods:
    def dummy_put():
        try:
            response = requests.put(f"{BASE_URL_TI}/{USER}", data=UPDATE_USER)
            return json.loads(response.text)
        except Exception as error:
            return logging.error(error)