from behave import *
from services.get_request_pages import DummyMethods

@given(u'que busco os dados de todos os funcionários com GET')
def step_impl(context):
    dados = DummyMethods.dummy_get()
    print(f'Dados de todos os usuários cadastrados:\n{dados}\n')

@given(u'que busco os dados de um único funcionário com GET')
def step_impl(context):
    dados = DummyMethods.dummy_get_unic()
    print(f'Dados de unico usuário cadastrado:\n{dados}\n')