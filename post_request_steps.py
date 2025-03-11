from behave import *
from services.post_request_pages import DummyMethods

@given(u'que crio um novo registro no banco de dados com POST')
def step_impl(context):
    dados = DummyMethods.dummy_post()
    print(f'Dados de usuário criado:\n{dados}\n')
    
