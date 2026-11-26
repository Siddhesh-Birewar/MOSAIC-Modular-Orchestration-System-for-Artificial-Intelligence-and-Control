import asyncio
import base64
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.voice.audio import VoiceError, encode_wav
from app.voice.neural import KokoroWorker, VoiceEngine, cached_model
from app.voice.text import Segmenter, language_for, normalize_speech

WAV = encode_wav(b'\0\0'*1600)
AUTH = {'Authorization':'Bearer '+'n'*40}


@pytest.mark.parametrize('source,expected', [
    ('# Hello **world**! 👋','Hello world!'),
    ('✅ Done. 2 ➕ 3','Done. 2 plus 3'),
    ('60% and 2 + 3 = 5','60 percent and 2 plus 3 equals 5'),
    ('2026/11/26 and -3.14','2026 slash 11 slash 26 and -3.14'),
    ('Use the API and GPU.','Use the A P I and G P U.'),
    ('**CPU**: `cache`','C P U: cache'),
    ('[Manual](https://example.test/a).','Manual.'),
    ('```python\nprint(1)\n```','Code is available in the text response.'),
    ('{"tool":"launch","arguments":{}}','structured data in the text response'),
    ('अच्छा। CPU का cache तेज है।','अच्छा। C P U का cache तेज है।'),
    ('Range [0, 1] and x² ≥ 0','Range [0, 1] and x² greater than or equal to 0'),
])
def test_spoken_normalization(source, expected):
    assert normalize_speech(source) == expected


def test_incremental_boundaries_and_hindi_splitting_preserve_order():
    segmenter = Segmenter()
    output = []
    for token in ['Dr. Rao uses 3.', '14. ', 'See https://example.com/docs. ', 'नमस्ते। ', 'Final fragment']:
        output.extend(segmenter.feed(token))
    output.extend(segmenter.feed('',final=True))
    assert output[0] == 'Dr. Rao uses 3.14.'
    assert output[1] == 'See link in the text response'
    assert output[2:] == ['नमस्ते।','Final fragment']
    pieces = Segmenter().feed(('यह CPU के cache के बारे में है। '*30), final=True)
    assert all(len(piece) <= 160 for piece in pieces)
    assert len(pieces) > 10
    assert len(Segmenter().feed('नमस्ते।ठीक है।',final=True))==2


def test_code_fences_and_json_are_not_emitted_mid_stream():
    segmenter = Segmenter()
    assert segmenter.feed('```python\nprint("secret. ")\n') == []
    result = segmenter.feed('```\nGood. ', final=True)
    assert result == ['Code is available in the text response.', 'Good.']
    segmenter = Segmenter()
    assert segmenter.feed('{"name": "launch. ') == []


@pytest.mark.parametrize('text,preference,detected,expected',[
    ('Hello there','auto','hi','en'),('यह CPU तेज है।','auto','en','hinglish'),
    ('नमस्ते।','auto','en','hi'),('aap ka code sahi hai','auto','en','hinglish'),
    ('English words','hinglish','en','hinglish'),('English words','en','hi','en'),
])
def test_response_language_routing(text,preference,detected,expected):
    assert language_for(text,preference,detected) == expected


@pytest.fixture
def fake_worker(monkeypatch,tmp_path):
    model = tmp_path/'cached'
    for name in ['config.json','kokoro-v1_0.safetensors','voices/af_bella.safetensors','voices/hf_alpha.safetensors']:
        file = model/name
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text('{}')
    spawned=[]
    class Child:
        returncode = None
        pid = 12345
        def __init__(self):
            self.queue=asyncio.Queue()
            self.queue.put_nowait(json.dumps({'version':1,'state':'ready','warmed':True}).encode()+b'\n')
            self.stdout=SimpleNamespace(readline=self.queue.get)
            self.stdin=SimpleNamespace(write=self.write,drain=AsyncMock())
            self.packets=[]
            self.respond=True
            self.bad=False
        def write(self,packet):
            request=json.loads(packet)
            self.packets.append(request)
            if self.respond:
                value={'id':request['id']+(1 if self.bad else 0),'audio':base64.b64encode(WAV).decode(),
                       'metrics':{'sample_rate':16000,'synthesis_seconds':.1}}
                self.queue.put_nowait(json.dumps(value).encode()+b'\n')
        def kill(self):
            self.returncode=-9
            self.queue.put_nowait(b'')
        async def wait(self):return self.returncode
    async def spawn(*args,**kwargs):
        assert kwargs['env']['HF_HUB_OFFLINE']=='1'
        assert 'MOSAIC_API_TOKEN' not in kwargs['env']
        child=Child()
        child.queue.get_nowait()
        child.queue.put_nowait(json.dumps({'version':1,'state':'ready','warmed':kwargs['env']['MOSAIC_NEURAL_WARMUP']=='1'}).encode()+b'\n')
        spawned.append(child);return child
    monkeypatch.setattr('app.voice.neural.asyncio.create_subprocess_exec',spawn)
    monkeypatch.setattr('app.voice.neural.psutil.virtual_memory',lambda:SimpleNamespace(available=8*1024**3))
    monkeypatch.setenv('MOSAIC_API_TOKEN','private-credential-not-forwarded')
    return model,spawned


def test_worker_readiness_model_reuse_order_shutdown(fake_worker):
    model,spawned=fake_worker
    async def check():
        worker=KokoroWorker(sys.executable,str(model))
        assert not worker.status()['ready']
        await worker.warm()
        assert worker.status()['warmed']
        outputs=await asyncio.gather(*[worker.request({'text':str(i),'voice':'af_bella','speed':1}) for i in range(3)])
        assert outputs==[WAV]*3 and len(spawned)==1
        assert [p['text'] for p in spawned[0].packets]==['0','1','2']
        await worker.close()
        assert not worker.status()['ready'] and spawned[0].returncode==-9
    asyncio.run(check())


def test_missing_assets_are_not_downloaded(tmp_path):
    with pytest.raises(VoiceError,match='missing'):
        cached_model(str(tmp_path))


def test_worker_cancel_invalid_ipc_restart_and_bounded_queue(fake_worker):
    model,spawned=fake_worker
    async def check():
        worker=KokoroWorker(sys.executable,str(model),queue_size=1,timeout=.2)
        await worker.warm()
        spawned[0].respond=False
        task=asyncio.create_task(worker.request({'text':'hello','voice':'af_bella','speed':1}))
        await asyncio.sleep(0)
        with pytest.raises(VoiceError,match='full'):
            await worker.request({'text':'second','voice':'af_bella','speed':1})
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert spawned[0].returncode==-9
        await worker.warm()
        assert len(spawned)==2
        spawned[1].bad=True
        with pytest.raises(VoiceError):await worker.request({'text':'bad id','voice':'af_bella','speed':1})
        await worker.warm()
        assert len(spawned)==3
        await worker._stop()
        with pytest.raises(VoiceError):await worker.warm()
        await worker.close()
    asyncio.run(check())


def test_fallback_is_explicit_and_hindi_direct_input_is_bounded():
    worker=SimpleNamespace(request=AsyncMock(side_effect=VoiceError('offline')))
    engine=VoiceEngine(worker,fallback=True)
    engine.macos.synthesize=AsyncMock(return_value=WAV)
    async def check():
        assert await engine.synthesize('Hello',None,1)==WAV
        assert engine.last['fallback'] and engine.last['provider']=='macos'
        with pytest.raises(VoiceError):await engine.synthesize('नमस्ते '*100,None,1)
        strict=VoiceEngine(worker,fallback=False)
        with pytest.raises(VoiceError):await strict.synthesize('Hello',None,1)
    asyncio.run(check())


class Ollama:
    async def list_models(self):return [{'name':'gpt-oss:20b'}]
    async def running_models(self):return []
    async def thinking_levels(self,model):return ['low','medium','high']
    async def stream_chat(self,model,messages,keep_alive,tools=None,think=None):
        from app.models.ollama_client import StreamEvent
        self.tools=tools
        self.think=think
        yield StreamEvent(content='First sentence. ')
        yield StreamEvent(content='Final fragment')
        yield StreamEvent(done=True,metrics={'eval_count':4})


def test_voice_stream_contract_preserves_history_and_explicit_reasoning():
    ollama=Ollama()
    with TestClient(create_app(Settings(api_token='n'*40),ollama)) as client:
        response=client.post('/chat/stream',headers=AUTH,json={'message':'hello','voice_mode':True,'voice_tools':False,'reasoning':'low'})
        assert response.status_code==200
        events=[(s.split('\n')[0],json.loads(s.split('data: ')[1])) for s in response.text.strip().split('\n\n')]
        speech=[value for name,value in events if name=='event: speech_segment']
        assert [v['text'] for v in speech]==['First sentence.','Final fragment']
        assert all(v['safety']=='tool_free' for v in speech)
        assert ollama.tools==[] and ollama.think=='low'
        cid=events[0][1]['conversation_id']
        history=client.get('/conversations/'+cid,headers=AUTH).json()['messages']
        assert history[-1]['content']=='First sentence. Final fragment'
        assert 'thinking' not in response.text


def test_tool_mode_speech_waits_until_completed_orchestration():
    with TestClient(create_app(Settings(api_token='n'*40),Ollama())) as client:
        response=client.post('/chat/stream',headers=AUTH,json={'message':'hello','voice_mode':True})
        assert response.text.index('event: speech_segment')>response.text.rindex('event: token')
        assert 'completed_orchestration' in response.text
        assert client.post('/voice/warmup').status_code==401
        assert client.post('/voice/cancel/00000000-0000-0000-0000-000000000000').status_code==401


@pytest.mark.parametrize('value',[
    {}, {'id':1,'text':'x','voice':'../../file','speed':1},
    {'id':1,'text':'x','voice':'af_bella','speed':float('nan')},
    {'id':True,'text':'x','voice':'af_bella','speed':1},
    {'id':1,'text':'x'*501,'voice':'af_bella','speed':1},
    {'id':1,'text':'x','voice':'af_bella','speed':1,'command':'shell'},
])
def test_worker_ipc_rejects_invalid_inputs(value):
    from app.voice.neural_worker import validate_request
    with pytest.raises(ValueError):validate_request(value)


def test_idle_retention_and_memory_admission(fake_worker,monkeypatch):
    model,spawned=fake_worker
    async def check():
        worker=KokoroWorker(sys.executable,str(model),idle_seconds=.02)
        await worker.warm()
        await asyncio.sleep(.07)
        assert not worker.status()['ready']
        await worker.close()
        monkeypatch.setattr('app.voice.neural.psutil.virtual_memory',lambda:SimpleNamespace(available=0))
        worker=KokoroWorker(sys.executable,str(model))
        with pytest.raises(VoiceError):await worker.warm()
        assert len(spawned)==1
        await worker.close()
    asyncio.run(check())


def test_stream_tool_preface_is_never_eligible_for_speech():
    from app.models.ollama_client import StreamEvent
    class ToolOllama(Ollama):
        async def stream_chat(self,model,messages,keep_alive,tools=None,think=None):
            if messages[-1]['role']=='tool':
                yield StreamEvent(content='The requested application is not allowed.')
                yield StreamEvent(done=True)
            else:
                call={'function':{'name':'applications_launch','arguments':{'application':'Not allowed'}}}
                yield StreamEvent(content='I have launched the application. ')
                yield StreamEvent(done=True,tool_calls=[call],assistant_message={'role':'assistant','tool_calls':[call]})
    with TestClient(create_app(Settings(api_token='n'*40),ToolOllama())) as client:
        response=client.post('/chat/stream',headers=AUTH,json={'message':'open app','voice_mode':True})
        speech=[json.loads(event.split('data: ')[1])['text'] for event in response.text.strip().split('\n\n') if event.startswith('event: speech_segment')]
        assert speech==['The requested action was not completed.', 'Details are available in the text response.']


def test_bounded_streaming_pipeline_orders_audio_and_cancels_playback():
    import threading,time
    from scripts.voice import VoiceSession
    class Response:
        content=WAV
        headers={}
        def raise_for_status(self):pass
    class Client:
        def post(self,*args,**kwargs):return Response()
    class CLI:
        backend_url='http://localhost'
        client=Client()
        def output(self,text):pass
        def _auth_headers(self):return AUTH
        def send_message(self,text,**kwargs):
            for index in range(10):
                if kwargs['cancelled'].is_set():break
                kwargs['speech_sink']({'sequence':index+1,'text':str(index)})
            return ''
    class Device:
        def __init__(self):self.calls=0
        def play(self,audio,emit):
            self.calls+=1
            assert self.calls<=10
            time.sleep(.001)
    device=Device()
    session=VoiceSession(CLI(),device)
    session.tools=False
    session.eos=time.monotonic()
    session._reply('hello','en')
    assert device.calls==10
    class Interrupt(Device):
        def play(self,audio,emit):raise KeyboardInterrupt()
    events=[]
    session=VoiceSession(CLI(),Interrupt(),event_sink=events.append)
    session.tools=False;session.eos=time.monotonic()
    with pytest.raises(KeyboardInterrupt):session._reply('hello','en')
    assert session.cancelled.is_set()
    assert any(event.kind=='cancellation' for event in events)


def test_worker_warmup_can_be_disabled(fake_worker):
    model,spawned=fake_worker
    async def check():
        worker=KokoroWorker(sys.executable,str(model),warmup=False)
        await worker.warm()
        assert worker.status()['ready'] and not worker.status()['warmed']
        await worker.close()
    asyncio.run(check())


@pytest.mark.integration
@pytest.mark.skipif(__import__('os').getenv('MOSAIC_TEST_NEURAL') != '1',reason='Explicit cached real-model integration only')
def test_real_cached_neural_worker_reuses_model_offline():
    from app.voice.audio import decode_wav
    async def check():
        worker=KokoroWorker('/opt/anaconda3/envs/mosaic-voice/bin/python',timeout=90)
        try:
            await worker.warm()
            pid=worker.status()['pid']
            assert worker.status()['warmed'] and worker.info['parameter_dtypes']
            for text,voice in [('MOSAIC is ready.','af_bella'),('नमस्ते। MOSAIC तैयार है।','hf_alpha')]:
                data=await worker.request({'text':text,'voice':voice,'speed':1})
                assert decode_wav(data).rate==24000
                assert worker.status()['pid']==pid
        finally:
            await worker.close()
    asyncio.run(check())


def test_cancellation_before_synthesis_registration_prevents_late_work():
    import uuid
    from app.api.voice import _connected
    from fastapi import HTTPException
    from starlette.requests import Request
    async def check():
        app=create_app(Settings(api_token='n'*40))
        async with app.router.lifespan_context(app):
            session=str(uuid.uuid4())
            app.state.voice_cancelled_sessions[session]=__import__('time').monotonic()+60
            request=Request({'type':'http','app':app,'headers':[(b'x-voice-session',session.encode())]})
            request.is_disconnected=AsyncMock(return_value=False)
            entered=[]
            async def operation():
                entered.append(True)
                return WAV
            with pytest.raises(HTTPException) as exc:
                await _connected(request,operation())
            assert exc.value.status_code==409 and entered==[]
    asyncio.run(check())


def test_launch_request_does_not_claim_verified_gui_success():
    from app.models.ollama_client import StreamEvent
    from app.tools.executor import ToolInvocation
    class LaunchOllama(Ollama):
        async def stream_chat(self,model,messages,keep_alive,tools=None,think=None):
            if messages[-1]['role']=='tool':
                yield StreamEvent(content='I opened the application successfully.')
                yield StreamEvent(done=True)
            else:
                call={'function':{'name':'applications_launch','arguments':{'application':'Finder'}}}
                yield StreamEvent(done=True,tool_calls=[call],assistant_message={'role':'assistant','tool_calls':[call]})
    with TestClient(create_app(Settings(api_token='n'*40),LaunchOllama())) as client:
        client.app.state.tool_executor.invoke=AsyncMock(return_value=ToolInvocation(
            state='completed',tool_id='applications_launch',result={'result':{'status':'launch_requested'}}))
        response=client.post('/chat/stream',headers=AUTH,json={'message':'Open app','voice_mode':True})
        speech=[json.loads(event.split('data: ')[1])['text'] for event in response.text.strip().split('\n\n') if event.startswith('event: speech_segment')]
        assert speech==['The application launch request was sent.','Check the application on your computer.']


def test_chunks_of_one_mixed_sentence_keep_the_same_voice_language():
    sentence='यह CPU का विवरण है ' + 'cache locality and memory performance '*12 + 'समझिए।'
    chunks=Segmenter(limit=80).feed_segments(sentence,final=True)
    assert len(chunks)>3
    assert all(chunk.language=='hinglish' for chunk in chunks)
    assert any(not any('\u0900'<=c<='\u097f' for c in chunk.text) for chunk in chunks)
