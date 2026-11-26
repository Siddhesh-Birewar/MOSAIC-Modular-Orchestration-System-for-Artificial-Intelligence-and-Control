"""Opt-in real-model component benchmark; silent, synthetic input, no persisted chats.

Ollama concurrency is opt-in with --llm. No microphone or playback is opened.
"""
import argparse
from array import array
import asyncio
import json
from pathlib import Path
import sys
import time

if __package__ in {None,''}:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import psutil
from app.models.ollama_client import OllamaClient
from app.voice.audio import decode_wav, encode_wav
from app.voice.neural import KokoroWorker
from app.voice.providers import MacOSTTS, WhisperCpp
from app.voice.language import language_issue, script_counts


def snapshot():
    return {'available_bytes':psutil.virtual_memory().available,'swap_used_bytes':psutil.swap_memory().used}


def microphone_wav(data):
    audio=decode_wav(data)
    samples=array('h',audio.pcm)
    resampled=array('h',(samples[min(int(i*audio.rate/16000),len(samples)-1)]
                       for i in range(int(len(samples)*16000/audio.rate))))
    return encode_wav(resampled.tobytes())


async def benchmark(args):
    result={'before':snapshot(),'playback_started_seconds':None,'end_to_end_audible_seconds':None}
    worker=KokoroWorker(args.python,warmup=not args.cold_start,timeout=90)
    try:
        start=time.monotonic()
        await worker.warm()
        result['worker_initialization_seconds']=time.monotonic()-start
        result['worker_load_seconds']=worker.info.get('model_load_seconds')
        result['worker_pid']=worker.status()['pid']
        result['synthesis_runs']=[]
        for voice,text in [('af_bella','MOSAIC is ready.'),('hf_alpha','नमस्ते। MOSAIC तैयार है।'),('af_bella','Local speech is ready.')]:
            started=time.monotonic()
            data=await worker.request({'text':text,'voice':voice,'speed':1})
            elapsed=time.monotonic()-started
            result['synthesis_runs'].append({'voice':voice,'seconds':elapsed,'rtf':elapsed/decode_wav(data).duration,**worker.metrics})
        if not args.skip_stt:
            # Synthetic disposable local native speech -> 16k PCM, never retained.
            data=decode_wav(await MacOSTTS().synthesize('Explain cache locality in two sentences.',None,1))
            samples=array('h',data.pcm)
            resampled=array('h',(samples[min(int(i*data.rate/16000),len(samples)-1)] for i in range(int(len(samples)*16000/data.rate))))
            wav=encode_wav(resampled.tobytes())
            stt=WhisperCpp('/opt/homebrew/bin/whisper-cli',str(Path.home()/'AI-Models/Whisper/ggml-base.bin'))
            timings=[]
            for _ in range(2):
                started=time.monotonic()
                transcript=await stt.transcribe(wav,'en')
                timings.append({'seconds':time.monotonic()-started,'nonempty':bool(transcript.text)})
            result['transcription_cold_then_warm']=timings
        if args.language_check:
            # Known synthetic Hindi, not a user's microphone sample or an accuracy score.
            data=await worker.request({'text':'मुझे बताइए कि कृत्रिम बुद्धिमत्ता कैसे काम करती है।','voice':'hf_alpha','speed':1})
            wav=microphone_wav(data)
            stt=WhisperCpp('/opt/homebrew/bin/whisper-cli',str(Path.home()/'AI-Models/Whisper/ggml-base.bin'))
            result['synthetic_hindi_stt']=[]
            for language in ('hi','auto'):
                started=time.monotonic()
                transcript=await stt.transcribe(wav,language)
                result['synthetic_hindi_stt'].append({'requested_language':language,
                    'reported_language':transcript.language,'seconds':time.monotonic()-started,
                    'scripts':script_counts(transcript.text),'issue':language_issue(transcript.text,language,transcript.language)})
        if args.llm:
            client=OllamaClient('http://127.0.0.1:11434',timeout=180)
            levels=await client.thinking_levels('gpt-oss:20b')
            if 'low' not in levels:raise RuntimeError('Installed model does not advertise low reasoning')
            async def llm():
                started=time.monotonic();first=None;metrics={}
                async for chunk in client.stream_chat('gpt-oss:20b',[
                    {'role':'system','content':'Answer concisely. No tools or actions are available.'},
                    {'role':'user','content':'Explain cache locality in two sentences.'}],think='low'):
                    if chunk.content and first is None:first=time.monotonic()-started
                    if chunk.done:metrics=chunk.metrics or {}
                return {'first_answer_token_seconds':first,'total_seconds':time.monotonic()-started,
                    'tokens_per_second':metrics.get('eval_count',0)/(metrics.get('eval_duration',1)/1e9),
                    'load_seconds':metrics.get('load_duration',0)/1e9}
            result['llm_without_tts']=await llm()
            async def tts_load():
                rows=[]
                samples=[('af_bella','Local neural speech and model generation can share the machine.'),
                         ('hf_alpha','कृत्रिम बुद्धिमत्ता उदाहरणों से सीखकर प्रश्नों के उत्तर देती है।'),
                         ('hf_alpha','यह CPU और memory का उदाहरण है। छोटे भागों में काम करना उपयोगी है।')]
                for index in range(args.stress_rounds*3 if args.stress_rounds else 6):
                    started=time.monotonic()
                    voice,text=samples[index%3] if args.stress_rounds else samples[0]
                    data=await worker.request({'text':text,'voice':voice,'speed':1})
                    elapsed=time.monotonic()-started
                    rows.append({'voice':voice,'seconds':elapsed,'audio_seconds':decode_wav(data).duration,
                                 'rtf':elapsed/decode_wav(data).duration})
                return rows
            result['llm_with_tts'],result['concurrent_synthesis']=await asyncio.gather(llm(),tts_load())
        result['worker_status']=worker.status()
        result['after']=snapshot()
    finally:
        await worker.close()
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',default='/opt/anaconda3/envs/mosaic-voice/bin/python')
    parser.add_argument('--skip-stt',action='store_true')
    parser.add_argument('--cold-start',action='store_true',help='Skip pre-readiness warm-up to measure first language pipeline invocations')
    parser.add_argument('--llm',action='store_true',help='Run two synthetic gpt-oss:20b requests, one concurrent with TTS')
    parser.add_argument('--language-check',action='store_true',help='Synthetic cached Kokoro Hindi -> existing Whisper Base; no mic or transcripts printed')
    parser.add_argument('--stress-rounds',type=int,choices=range(1,5),default=0,
                        help='With --llm, run 1–4 English/Hindi/Hinglish synthesis cycles instead of six English requests')
    args=parser.parse_args()
    if args.stress_rounds and not args.llm:
        parser.error('--stress-rounds requires --llm')
    asyncio.run(benchmark(args))
