from behave import *
from services.put_request_pages import DummyMethods

@given(u'que atualizo um registro de funcionário com PUT')
def step_impl(context):
    dados = DummyMethods.dummy_put()
    print(f'Dados de usuário alterado:\n{dados}\n')
    