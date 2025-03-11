import requests
import json
from support.logger import *
from support.ambientes import *
from support.loads import *

class DummyMethods:
    def dummy_delete():
        try:
            response = requests.delete(f"{BASE_URL_TI}/{USER}")
            return response.status_code
        except Exception as error:
            return logging.error(error)