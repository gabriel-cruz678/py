from behave import *
from services.detete_request_pages import DummyMethods

@given(u'que excluo um registro de funcionário com DELETE')
def step_impl(context):
    dados = DummyMethods.dummy_delete()
    print(f'codigo de response de usuários deletado:\n{dados}\n')
    