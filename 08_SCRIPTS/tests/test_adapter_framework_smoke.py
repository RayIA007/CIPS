from cips_core.adapters import AdapterAlreadyRegisteredError, AdapterRequest, AdapterResult, AdapterRegistry, BaseAgentAdapter
class EchoAdapter(BaseAgentAdapter):
    adapter_name='EchoAdapter'; capability='echo'; version='1.0.0'
    def validate_request(self,request:AdapterRequest):
        if 'text' not in request.input_data: raise ValueError("Falta input_data['text'].")
    def run(self,request:AdapterRequest):
        return {'echo':request.input_data['text'],'project_id':request.context.project_id,'previous_tasks':sorted(request.task_outputs)}
def run():
    registry=AdapterRegistry(); adapter=registry.register(EchoAdapter())
    assert len(registry)==1 and registry.resolve(capability='echo') is adapter and registry.get('EchoAdapter') is adapter
    payload={'project_id':'cips_adapter_smoke','workflow_id':'workflow_smoke','run_id':'run_smoke','task_id':'task_echo','input':{'text':'Adapter Framework operativo'},'shared_data':{'language':'es'},'task_outputs':{'previous':{'ok':True}},'metadata':{'sprint':'2A'}}
    result=adapter(payload)
    assert isinstance(result,AdapterResult) and result.succeeded
    assert result.output['echo']=='Adapter Framework operativo' and result.output['previous_tasks']==['previous']
    duplicate=False
    try: registry.register(EchoAdapter())
    except AdapterAlreadyRegisteredError: duplicate=True
    assert duplicate
    print('OK: Adapter Framework operativo.')
    print(f'Adaptador: {adapter.adapter_name}')
    print(f'Capability: {adapter.capability}')
    print(f'Estado: {result.status.value}')
    print(f'Result ID: {result.result_id}')
    print(f'Duración ms: {result.duration_ms}')
    print(f'Adaptadores registrados: {len(registry)}')
if __name__=='__main__': run()
