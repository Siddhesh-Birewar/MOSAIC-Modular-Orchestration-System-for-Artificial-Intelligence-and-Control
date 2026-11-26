import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.ollama_client import StreamEvent
from app.voice.audio import VoiceError, VoiceInputError, decode_wav, encode_wav
from app.voice.diagnostics import VoiceDiagnosticError
from app.voice.language import language_issue, script_counts
from app.voice.neural import VoiceEngine
from app.voice.neural import KokoroWorker
from app.voice.providers import Transcript, WhisperCpp
from scripts.chat import MosaicCLI
from scripts.voice import AudioDevice, VoiceSession

AUTH={'Authorization':'Bearer '+'r'*40}
WAV=encode_wav(b'\0\x10'*1600)


@pytest.mark.parametrize('value',[0,-1])
def test_nonpositive_memory_floor_cannot_disable_admission(monkeypatch,value):
    monkeypatch.setenv('MOSAIC_NEURAL_MIN_AVAILABLE_MB',str(value))
    with pytest.raises(ValueError,match='positive'):Settings.from_env()
    with pytest.raises(ValueError,match='positive'):KokoroWorker('/trusted/python',min_available_mb=value)


@pytest.mark.parametrize('language,script,detected,issue',[
    ('hi','नमस्ते दुनिया।','hi',None), ('hinglish','यह CPU तेज है।','hi',None),
    ('hi','mujhe batao kya hai','hi','script_mismatch'),
    ('hi','یہ کیا ہے','hi','unsupported_script'),('auto','یہ کیا ہے','ur','unsupported_script'),
    ('en','नमस्ते','hi','language_mismatch'),('auto','bonjour','fr','language_mismatch'),
])
def test_transcript_language_script_checks(language,script,detected,issue):
    assert language_issue(script,language,detected)==issue


@pytest.mark.parametrize('language',['auto','en','hi'])
def test_selected_language_reaches_real_whisper_argument_without_translation(monkeypatch,tmp_path,language):
    executable=tmp_path/'whisper-cli'; executable.touch(); executable.chmod(0o700)
    model=tmp_path/'ggml-base.bin';model.touch()
    async def run(*args,**kwargs):
        assert args[args.index('-l')+1]==language and '-tr' not in args
        Path(args[args.index('-of')+1]+'.json').write_text(json.dumps({
            'transcription':[{'text':'नमस्ते'}],'result':{'language':'hi'}}))
    monkeypatch.setattr('app.voice.providers.run_local',run)
    assert asyncio.run(WhisperCpp(str(executable),str(model)).transcribe(WAV,language)).text=='नमस्ते'


@pytest.mark.parametrize('language',['hi','hinglish'])
def test_cli_hindi_language_propagation_and_optional_preview_prevents_unconfirmed_turn(language):
    def request(req):
        assert req.url.path=='/voice/transcribe' and req.url.params['language']=='hi'
        import httpx
        return httpx.Response(200,json={'text':'नमस्ते।','language':'hi','language_source':'selected'})
    import httpx
    outputs=[]
    cli=MosaicCLI('http://localhost',client=httpx.Client(transport=httpx.MockTransport(request)),
                  output_fn=outputs.append,input_fn=lambda p:'no')
    cli.send_message=lambda *a,**k:pytest.fail('Unconfirmed transcript must not reach chat')
    device=SimpleNamespace(record=lambda emit:WAV)
    session=VoiceSession(cli,device,language=language)
    assert session.transcript_preview is False
    session.transcript_preview=True;session.once()
    assert any('Transcript preview:' in line and 'नमस्ते' in line for line in outputs)
    assert session.state=='idle'


@pytest.mark.parametrize('text',['یہ کیا ہے','mujhe batao kya hai'])
def test_wrong_hindi_transcript_never_creates_chat_turn_or_extra_logs(text):
    import httpx
    outputs=[]
    cli=MosaicCLI('http://localhost',client=httpx.Client(transport=httpx.MockTransport(
        lambda req:httpx.Response(200,json={'text':text,'language':'hi'}))),output_fn=outputs.append)
    cli.send_message=lambda *a,**k:pytest.fail('Invalid transcript reached chat')
    session=VoiceSession(cli,SimpleNamespace(record=lambda emit:WAV),language='hi')
    with pytest.raises(VoiceError,match='Transcription rejected'):session.once()
    assert outputs==[]


def test_transcribe_endpoint_exposes_content_free_validation_metadata():
    with TestClient(create_app(Settings(api_token='r'*40))) as client:
        client.app.state.stt=SimpleNamespace(transcribe=AsyncMock(return_value=Transcript('یہ کیا ہے','ur')))
        response=client.post('/voice/transcribe?language=hi',content=WAV,headers={**AUTH,'Content-Type':'audio/wav'})
        assert response.json()['validation']['category']=='unsupported_script'
        assert response.json()['language_source']=='selected'
        assert response.headers['cache-control']=='no-store'


def events(response):
    return [(item.split('\n')[0][7:],json.loads(item.split('data: ')[1]))
            for item in response.text.strip().split('\n\n')]


class LanguageModel:
    def __init__(self,first='یہ غلط زبان ہے۔',repair='यह सही भाषा में उत्तर है।'):
        self.first,self.repair=first,repair;self.requests=[]
    async def list_models(self):return [{'name':'gpt-oss:20b'}]
    async def running_models(self):return []
    async def stream_chat(self,model,messages,keep_alive,tools=None):
        self.requests.append((messages.copy(),tools))
        yield StreamEvent(content=self.first if len(self.requests)==1 else self.repair)
        yield StreamEvent(done=True)


@pytest.mark.parametrize('language',['hi','hinglish'])
def test_response_language_repair_is_bounded_tool_free_and_one_persisted_turn(language):
    model=LanguageModel()
    with TestClient(create_app(Settings(api_token='r'*40),model)) as client:
        response=client.post('/chat/stream',headers=AUTH,json={'message':'Explain AI','voice_mode':True,
            'voice_tools':False,'voice_language':language})
        values=events(response)
        speech=[v for k,v in values if k=='speech_segment']
        assert speech and all(script_counts(v['text'])['unsupported']==0 for v in speech)
        assert all(v['language']==language for v in speech)
        assert len(model.requests)==2 and model.requests[1][1]==[]
        assert 'Devanagari' in model.requests[0][0][0]['content']
        cid=values[0][1]['conversation_id']
        history=client.get('/conversations/'+cid,headers=AUTH).json()['messages']
        assert len(history)==2 and history[-1]['content']==model.first


def test_failed_language_repair_uses_safe_notice_and_never_executes_returned_tools():
    model=LanguageModel(repair='یہ اب بھی غلط ہے۔')
    with TestClient(create_app(Settings(api_token='r'*40),model)) as client:
        executor=client.app.state.tool_executor.invoke=AsyncMock()
        response=client.post('/chat/stream',headers=AUTH,json={'message':'समझाइए','voice_mode':True,'voice_tools':False,'voice_language':'hi'})
        spoken=' '.join(v['text'] for k,v in events(response) if k=='speech_segment')
        assert 'कृपया लिखित उत्तर देखें' in spoken and len(model.requests)==2
        executor.assert_not_awaited()


def test_language_setting_overrides_previous_urdu_history_and_valid_answer_still_streams():
    model=LanguageModel(first='Artificial intelligence learns patterns. More detail.')
    with TestClient(create_app(Settings(api_token='r'*40),model)) as client:
        cid=client.post('/conversations',headers=AUTH,json={}).json()['id']
        store=client.app.state.conversations
        store.append_turn(store.get(cid),'پچھلا سوال','پچھلا جواب')
        response=client.post('/chat/stream',headers=AUTH,json={'conversation_id':cid,'message':'Explain AI',
            'voice_mode':True,'voice_tools':False,'voice_language':'en'})
        sequence=events(response)
        assert next(i for i,(k,v) in enumerate(sequence) if k=='speech_segment') < next(i for i,(k,v) in enumerate(sequence) if k=='done')
        assert len(model.requests)==1
        assert 'overrides older' in model.requests[0][0][0]['content']


def test_repair_never_repeats_already_eligible_sentences():
    model=LanguageModel(first='This sentence is already safe. یہ غلط زبان ہے۔',repair='This is the remaining answer.')
    with TestClient(create_app(Settings(api_token='r'*40),model)) as client:
        response=client.post('/chat/stream',headers=AUTH,json={'message':'hello','voice_mode':True,
            'voice_tools':False,'voice_language':'en'})
        speech=[v['text'] for k,v in events(response) if k=='speech_segment']
        assert speech==['This sentence is already safe.','This is the remaining answer.']
        assert 'already safe' not in model.requests[1][0][-1]['content']
        metrics=next(v['metrics'] for k,v in events(response) if k=='done')
        assert metrics['voice_language_repair_attempts']==1 and metrics['voice_language_repair_seconds']>=0


def test_repair_rejects_structured_tool_calls_instead_of_orchestrating_them():
    from app.voice.response import repair_response
    class Model:
        async def stream_chat(self,*a,**k):
            assert k['tools']==[]
            yield StreamEvent(content='Some answer',tool_calls=[{'function':{'name':'applications_launch'}}],done=True)
    assert asyncio.run(repair_response(Model(),'gpt-oss:20b','synthetic','en','5m',1)) is None


def test_repair_timeout_is_bounded_and_closes_upstream():
    from app.voice.response import repair_response
    closed=[]
    class Model:
        async def stream_chat(self,*a,**k):
            try:
                await asyncio.Event().wait()
                yield StreamEvent(done=True)
            finally:closed.append(True)
    assert asyncio.run(repair_response(Model(),'gpt-oss:20b','synthetic','en','5m',.01)) is None
    assert closed==[True]


def test_long_mixed_hindi_sentence_keeps_technical_chunks_without_rewrite():
    answer='यह CPU का विवरण है ' + 'cache locality and memory performance '*8 + 'समझिए।'
    model=LanguageModel(first=answer)
    with TestClient(create_app(Settings(api_token='r'*40),model)) as client:
        response=client.post('/chat/stream',headers=AUTH,json={'message':'समझाइए','voice_mode':True,
            'voice_tools':False,'voice_language':'hi'})
        assert len(model.requests)==1 and 'voice_warning' not in response.text
        assert len([v for k,v in events(response) if k=='speech_segment'])>1


def test_language_repair_does_not_repeat_completed_tool():
    class ToolModel(LanguageModel):
        async def stream_chat(self,model,messages,keep_alive,tools=None):
            self.requests.append((messages.copy(),tools))
            if len(self.requests)==1:
                call={'function':{'name':'system_memory','arguments':{}}}
                yield StreamEvent(tool_calls=[call],assistant_message={'role':'assistant','tool_calls':[call]},done=True)
            elif len(self.requests)==2:
                yield StreamEvent(content='یہ معلومات ہے۔');yield StreamEvent(done=True)
            else:
                assert tools==[]
                yield StreamEvent(content='यह सिस्टम की जानकारी है।');yield StreamEvent(done=True)
    model=ToolModel()
    with TestClient(create_app(Settings(api_token='r'*40),model)) as client:
        original=client.app.state.tool_executor.invoke
        executor=client.app.state.tool_executor.invoke=AsyncMock(wraps=original)
        response=client.post('/chat/stream',headers=AUTH,json={'message':'memory','voice_mode':True,'voice_language':'hi'})
        assert 'speech_segment' in response.text and len(model.requests)==3
        assert executor.await_count==1


def test_kokoro_rejects_unsupported_scripts_before_worker_invocation():
    worker=SimpleNamespace(request=AsyncMock())
    with pytest.raises(VoiceInputError):asyncio.run(VoiceEngine(worker).synthesize('یہ کیا ہے',None,1))
    worker.request.assert_not_awaited()


def test_structured_diagnostic_api_never_returns_private_exception_contents():
    with TestClient(create_app(Settings(api_token='r'*40))) as client:
        client.app.state.voice_engine.synthesize=AsyncMock(side_effect=VoiceDiagnosticError('memory_limit','admission',available_bytes=123,required_bytes=456,private='do not emit'))
        response=client.post('/voice/synthesize',headers=AUTH,json={'text':'test','provider':'kokoro'})
        assert response.status_code==503 and response.json()['diagnostic']=={
            'category':'memory_limit','stage':'admission','available_bytes':123,'required_bytes':456}
        assert 'private' not in response.text


def test_successful_playback_populates_first_audio_metric_and_failed_start_does_not():
    session=VoiceSession(SimpleNamespace(backend_url='http://localhost'),SimpleNamespace())
    session.metrics={'time_to_first_audio_seconds':None}; session.eos=time.monotonic()-.1
    session.emit('playback_started',playback_seconds=0)
    first=session.metrics['time_to_first_audio_seconds']
    session.emit('playback_started',playback_seconds=0)
    assert first is not None and first==session.metrics['time_to_first_audio_seconds']==session.metrics['playback_started_seconds']
    session.metrics={'time_to_first_audio_seconds':None}
    session.emit('speech_start')
    assert session.metrics['time_to_first_audio_seconds'] is None


def capture(monkeypatch,blocks,**settings):
    class Input:
        def __init__(self):self.calls=0;self.closed=False
        def start(self):pass
        def read(self,frames):
            self.calls+=1
            level=blocks[self.calls-1] if self.calls<=len(blocks) else 0
            return int(level).to_bytes(2,'little',signed=True)*frames,False
        def abort(self):pass
        def close(self):self.closed=True
    stream=Input()
    monkeypatch.setattr(AudioDevice,'_driver',staticmethod(lambda:SimpleNamespace(RawInputStream=lambda **kw:stream)))
    device=AudioDevice(**settings)
    return stream,device


def test_vad_keeps_quiet_speech_and_natural_pause_then_trims_endpoint_wait(monkeypatch):
    # 400/32768 RMS exceeds new .010 threshold but was below the old .015.
    stream,device=capture(monkeypatch,[0]*20+[400]*10+[0]*60+[400]*10+[0]*100)
    result=decode_wav(device.record(lambda *a,**k:None),microphone=True)
    assert stream.calls==200 and stream.closed
    assert result.duration==pytest.approx(1.96)  # Includes onset pre-roll; excludes 1.8s endpoint wait.
    assert device.last_speech_end_at is not None


def test_vad_ignores_noise_spikes_and_initial_silence_is_bounded(monkeypatch):
    stream,device=capture(monkeypatch,[0,0,600,0]*125)
    with pytest.raises(VoiceError,match='No speech detected'):device.record(lambda *a,**k:None)
    assert stream.calls==500 and stream.closed


def test_vad_continuous_background_is_still_hard_capped(monkeypatch):
    stream,device=capture(monkeypatch,[500]*1500)
    result=decode_wav(device.record(lambda *a,**k:None),microphone=True)
    assert stream.calls==1500 and result.duration==30 and stream.closed
